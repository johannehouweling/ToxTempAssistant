"""Build the persistent embedding cache + per-answer index for cross-model agreement.

Embeds every NON-TRIVIAL answer (``answered`` + ``hedged``; skips ``abstained`` +
``empty``) **twice** — the raw ``answer`` and ``normalize_for_embedding(answer)`` — into
the shared ``EmbeddingCache`` (``output/_embeddings/{vectors.npy,index.csv}``), and writes
a per-answer index (``output/_embeddings/answer_index.csv``) mapping each
``(experiment, model, assay, question_id)`` to its scenario, raw_sha1 and norm_sha1.
The agreement step (``tier3_metrics``) then looks vectors up by SHA-1 and computes the
per-(assay, question) cosine both ways (raw vs normalized) without re-embedding.

Idempotent: the SHA-1 cache means a re-run only embeds texts not already stored.

    cd myocyte && USE_POSTGRES=false DJANGO_DEBUG=true \
        poetry run python toxtempass/evaluation/real_world/build_embeddings.py

The core (``collect``) takes the parser / normalizer / hasher as arguments and does no
embedding, so it is unit-testable without API credentials; only ``main()`` bootstraps
Django and performs the embedding.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd

_INDEX_COLS = [
    "experiment", "model", "assay", "question_id", "scenario", "raw_sha1", "norm_sha1",
]


def collect(
    root: Path,
    parse: Callable[[str], dict],
    normalize: Callable[[str], str],
    sha1: Callable[[str], str],
) -> tuple[list[dict], list[str]]:
    """Walk answer CSVs; return ``(index_rows, texts_to_embed)`` for non-trivial answers.

    Only answers with substantive content (``not is_trivial`` → answered + hedged) are
    included; clean abstentions and empties are skipped. ``texts_to_embed`` contains both
    the raw and normalized text of every kept answer (de-duplication is handled by the
    SHA-1 cache downstream).
    """
    # Imported here (not at module top) so the module loads without `toxtempass`
    # on sys.path; the CSV-walker is Django-free.
    from toxtempass.evaluation.real_world.enrich_answer_status import iter_answer_csvs

    index_rows: list[dict] = []
    texts: list[str] = []
    for experiment, model, csv_path in iter_answer_csvs(root):
        assay = csv_path.stem[len("tier3_answers_"):]
        df = pd.read_csv(csv_path).fillna("")
        for row in df.itertuples():
            raw = str(getattr(row, "answer", ""))
            parsed = parse(raw)
            if parsed["is_trivial"]:
                continue
            norm = normalize(raw)
            index_rows.append(
                {
                    "experiment": experiment,
                    "model": model,
                    "assay": assay,
                    "question_id": getattr(row, "question_id", ""),
                    "scenario": parsed["answer_scenario"],
                    "raw_sha1": sha1(raw),
                    "norm_sha1": sha1(norm),
                }
            )
            texts.extend([raw, norm])
    return index_rows, texts


def main() -> None:
    """Embed non-trivial answers (raw + normalized) into the cache; write the index."""
    import os
    import sys

    import django

    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myocyte.settings")
    django.setup()

    from django.core.management.color import make_style

    from toxtempass.evaluation.config import config as eval_config
    from toxtempass.evaluation.post_processing import embeddings as emb
    from toxtempass.evaluation.real_world.answer_utils import (
        normalize_for_embedding,
        parse_answer,
    )

    style = make_style()
    root = eval_config.real_world_output
    emb_dir = root / "_embeddings"

    cache = emb.EmbeddingCache(emb_dir)
    emb.set_persistent_cache(cache)

    index_rows, texts = collect(
        root, parse_answer, normalize_for_embedding, emb.text_sha1
    )
    before = len(cache)
    if texts:
        emb.embed_texts(texts)  # de-dups + writes misses into the persistent cache
    cache.save()

    emb_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(index_rows, columns=_INDEX_COLS).to_csv(
        emb_dir / "answer_index.csv", index=False
    )

    n_new = len(cache) - before
    n_unique = len(set(texts))
    print(
        style.SUCCESS(
            f"Indexed {len(index_rows)} non-trivial answers; {len(texts)} texts "
            f"({n_unique} unique); cache holds {len(cache)} vectors (+{n_new} new). "
            f"Index -> {emb_dir / 'answer_index.csv'}"
        )
    )


if __name__ == "__main__":
    main()
