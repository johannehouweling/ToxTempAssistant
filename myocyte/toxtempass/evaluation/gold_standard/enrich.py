"""Local cosine enrichment for a ``--no-cosine`` gold CSV (the second half of the split).

``extract_gold_answers --no-cosine`` runs pure-DB on prod (no OpenAI key) and emits the
gold + recovered baseline (draft) text with the semantic columns left blank. This step
fills them on your machine, where the OpenAI key + SHA embedding cache live: it computes
cosine(baseline, gold) and the full edit type for every row that has a recovered baseline.
Reproducible and cheap on re-run (embeddings are SHA-cached in ``output/_embeddings``).

    cd myocyte && poetry run python manage.py enrich_gold_cosines \
        --in gold_no_cosine.csv --out gold_typed.csv
"""

from __future__ import annotations

import csv
from collections import Counter

from toxtempass import config
from toxtempass.evaluation.gold_standard import audit
from toxtempass.evaluation.gold_standard.edit_analysis import classify_edit

NOT_FOUND = config.not_found_string


def _is_exact(row: dict) -> bool:
    """Return True when the delta is exact (baseline = recovered model draft)."""
    return str(row.get("delta_exact")).strip().lower() == "true"


def run_enrich(in_path: str, out_path: str) -> dict:
    """Fill cosine + edit type per baseline→gold row of a --no-cosine CSV; write it out.

    Reuses the same SHA-cached embedding cosine and the same ``classify_edit`` taxonomy as
    the inline (with-cosine) extract, so the typed output is identical to a direct run —
    just computed locally. Rows without a recovered baseline are passed through untouched.
    """
    with open(in_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    cosine_fn, cache = audit._make_cosine_fn()
    typed = 0
    try:
        for r in rows:
            baseline = r.get("baseline_answer") or ""
            if (r.get("baseline_kind") or "none") == "none" or not baseline.strip():
                continue
            gold = r.get("gold_answer") or ""
            c = classify_edit(baseline, gold, cosine_fn(baseline, gold), NOT_FOUND)
            r["change_type"] = c["edit_type"]
            r["cosine_baseline_final"] = c["cosine"]
            r["lexical_ratio_baseline_final"] = c["lexical_ratio"]
            r["chars_added"] = c["chars_added"]
            r["chars_removed"] = c["chars_removed"]
            typed += 1
    finally:
        cache.save()

    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=audit.CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return {
        "n_rows": len(rows),
        "n_typed": typed,
        "change_type_counts_all": dict(
            Counter(r.get("change_type") or "n/a" for r in rows)
        ),
        "change_type_counts_exact": dict(
            Counter(r.get("change_type") or "n/a" for r in rows if _is_exact(r))
        ),
    }
