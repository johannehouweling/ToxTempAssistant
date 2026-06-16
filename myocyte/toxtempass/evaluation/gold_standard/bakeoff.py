"""Bake-off: score each cross-provider model's answers against the scientist GOLD.

For the assays that appear in BOTH the cross-provider eval and the prod gold set, this
matches answers by question text and measures, per model:

* mean cosine-to-gold over cells where both the model and the scientist gave a substantive
  answer (semantic closeness to what the scientist accepted), and
* abstention agreement (did the model say "not found" exactly where the scientist did).

gpt-4o-mini is highlighted as the deployed baseline. Reuses the cross-provider embedding
cache, so cosine is cheap/reproducible; only the gold answers are newly embedded.

CAVEAT (printed on the plot): the gold answers were edited from gpt-4o-mini drafts, so
gpt-4o-mini has a structural head start on "closeness to gold" — read raw cosine with that
in mind; an LLM content-match judge (follow-up) mitigates it.

    cd myocyte && USE_POSTGRES=false DJANGO_DEBUG=true poetry run python \
        toxtempass/evaluation/gold_standard/bakeoff.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

HERE = Path(__file__).resolve().parent
CROSS = HERE.parent / "real_world" / "output" / "cross_provider"
EMB_DIR = HERE.parent / "real_world" / "output" / "_embeddings"
GOLD_CSV = HERE / "output" / "gold_answers_20260616.csv"
OUT = HERE / "output"

# eval-assay dir name → substring that UNIQUELY identifies the matching gold assay_title.
ASSAY_KEYS = {
    "ABlue_SHSY5Y": "Ablue SH-SY5Y",
    "LDH_SHSY5Y": "LDH SH-SY5Y",          # not "LDH in HepaRG"
    "OATP1C1": "OATP1C1",
    "mSLDT": "mSLDT",
    "TH_Uptake": "Thyroid hormone transport",
}


def _bootstrap_django() -> None:
    """Configure Django so the embedding cache + config import cleanly."""
    import django

    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # myocyte/
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myocyte.settings")
    django.setup()


def _norm(s: object) -> str:
    """Normalise a question string for matching (collapse whitespace, lowercase)."""
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def _display(model_dir: str) -> str:
    """Strip the ``_temp0`` output-dir suffix to the plain model name."""
    return re.sub(r"_temp[0-9.]+$", "", model_dir)


def _collect_pairs(gold: pd.DataFrame, not_found: str) -> pd.DataFrame:
    """Match every model answer to its gold answer by (assay, question text)."""
    rows: list[dict] = []
    model_dirs = sorted(
        p.name for p in CROSS.iterdir() if p.is_dir() and not p.name.startswith("_")
        and p.name != "structured_grounded"
    )
    for model_dir in model_dirs:
        disp = _display(model_dir)
        for ev, key in ASSAY_KEYS.items():
            f = CROSS / model_dir / f"tier3_answers_{ev}.csv"
            if not f.exists():
                continue
            gsub = gold[gold["assay_title"].str.contains(key, case=False, regex=False)]
            gmap = {
                _norm(r.question_text): (str(r.gold_answer or ""), bool(r.is_not_found))
                for r in gsub.itertuples()
            }
            for r in pd.read_csv(f).itertuples():
                q = _norm(r.question)
                if q not in gmap:
                    continue
                gold_ans, gold_nf = gmap[q]
                model_ans = str(getattr(r, "answer", "") or "")
                model_nf = bool(getattr(r, "not_found", False)) or (
                    not_found.lower() in model_ans.lower()
                )
                rows.append(
                    {
                        "model": disp, "assay": ev, "question": q,
                        "gold_answer": gold_ans, "gold_nf": gold_nf,
                        "model_answer": model_ans, "model_nf": model_nf,
                    }
                )
    return pd.DataFrame(rows)


def _score(df: pd.DataFrame, emb, cosine) -> pd.DataFrame:  # noqa: ANN001
    """Add cosine-to-gold (both-substantive cells) + abstention agreement."""
    need = {
        t
        for r in df.itertuples()
        for t, nf in ((r.gold_answer, r.gold_nf), (r.model_answer, r.model_nf))
        if not nf and t.strip()
    }
    if need:
        emb.embed_texts(list(need))  # one batched, cached warm-up

    def vec(t: str):  # noqa: ANN202
        return emb.embed_texts([t])[0]

    cosines = []
    for r in df.itertuples():
        both = (not r.gold_nf) and (not r.model_nf) and r.gold_answer.strip() \
            and r.model_answer.strip()
        cosines.append(
            round(float(cosine(vec(r.gold_answer), vec(r.model_answer))), 4)
            if both else None
        )
    df = df.copy()
    df["cosine_to_gold"] = cosines
    df["abstain_match"] = df["gold_nf"] == df["model_nf"]
    return df


def _make_plot(summary: pd.DataFrame) -> go.Figure:
    """Bar of mean cosine-to-gold per model (gpt-4o-mini = the deployed baseline)."""
    d = summary.sort_values("mean_cosine_to_gold", ascending=False)
    colors = ["#d62728" if m == "gpt-4o-mini" else "#1f77b4" for m in d["model"]]
    fig = go.Figure(
        go.Bar(
            x=d["model"], y=d["mean_cosine_to_gold"], marker_color=colors,
            text=[f"{v:.3f}" for v in d["mean_cosine_to_gold"]], textposition="outside",
        )
    )
    fig.update_layout(
        title=(
            "Bake-off: closeness to scientist-accepted gold (mean cosine), per model"
            "<br><sub>5 shared assays · gpt-4o-mini (red) = deployed baseline · "
            "NOTE gold was edited from gpt-4o-mini drafts, so it has a head start</sub>"
        ),
        yaxis_title="mean cosine to gold answer", xaxis_title="", template="plotly_white",
        width=1000, height=520, xaxis_tickangle=-30, margin=dict(t=90),
    )
    fig.update_yaxes(range=[0, 1])
    return fig


def main() -> None:
    """Run the bake-off: match, score, aggregate, write CSV + plot."""
    _bootstrap_django()
    from toxtempass import config
    from toxtempass.evaluation.post_processing import embeddings as emb
    from toxtempass.evaluation.post_processing.similarity import cosine

    cache = emb.EmbeddingCache(EMB_DIR)
    emb.set_persistent_cache(cache)
    gold = pd.read_csv(GOLD_CSV)

    w = sys.stdout.write
    df = _collect_pairs(gold, config.not_found_string)
    w(f"matched {len(df)} (model, gold-cell) pairs · {df['assay'].nunique()} assays\n")
    try:
        df = _score(df, emb, cosine)
    finally:
        cache.save()

    summary = (
        df.groupby("model")
        .agg(
            n_cells=("question", "size"),
            n_scored=("cosine_to_gold", "count"),
            mean_cosine_to_gold=("cosine_to_gold", "mean"),
            abstain_agreement=("abstain_match", "mean"),
        )
        .reset_index()
        .sort_values("mean_cosine_to_gold", ascending=False)
    )
    summary["mean_cosine_to_gold"] = summary["mean_cosine_to_gold"].round(4)
    summary["abstain_agreement"] = summary["abstain_agreement"].round(3)

    df.to_csv(OUT / "bakeoff_scores.csv", index=False)
    summary.to_csv(OUT / "bakeoff_summary.csv", index=False)
    w("\n=== BAKE-OFF — closeness to scientist gold (higher cosine = closer) ===\n")
    w(summary.to_string(index=False) + "\n")

    fig = _make_plot(summary)
    fig.write_html(OUT / "bakeoff.html")
    try:
        fig.write_image(OUT / "bakeoff.png", scale=2)
        w(f"\nWrote {OUT / 'bakeoff.png'} (+ .html + bakeoff_scores/summary.csv)\n")
    except Exception as exc:  # pragma: no cover - kaleido optional
        w(f"PNG export skipped ({type(exc).__name__}); wrote HTML + CSVs.\n")


if __name__ == "__main__":
    main()
