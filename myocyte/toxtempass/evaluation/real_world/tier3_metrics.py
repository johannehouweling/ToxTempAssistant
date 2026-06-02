"""Tier 3 (real-world) reference-free metrics.

Consumes the per-assay CSVs written by ``real_world.run()`` (via ``run_evals``) and
scores model performance *without* a ground-truth ToxTemp, using four reference-free
signals:

  1. Completeness     — share of questions answered (parsed not-found, prose OR
                         structured ``answerable:no`` / ``answer:null``).
  2. Cross-model      — mean pairwise cosine similarity between models' answers to
     agreement           the same question, computed *within an experiment*.
  3. LLM-judge quality— High/Medium/Low: does the answer address the question?
  4. Faithfulness     — Grounded/Partial/Unsupported: are the answer's claims
                         supported by the context the model was given? For the
                         structured experiment, also checks ``supporting_quotes``
                         are verbatim in the context (cheap, no LLM).

It is **experiment-aware**: it walks ``output/<experiment>/<model>/`` and tags every
row with its ``experiment`` so the cross-provider run and the structured run are both
captured, and ``gpt-4o-mini`` can be compared across prompt strategies.

Run *after* generation has produced answers (judge = ``eval_config.judge_model``):
    cd myocyte && USE_POSTGRES=false DJANGO_DEBUG=true \
        poetry run python toxtempass/evaluation/real_world/tier3_metrics.py

Outputs (under ``real_world/output/_analysis/``):
  * ``tier3_metrics_<ts>.csv``        — one row per (experiment, assay, question, model).
  * ``tier3_agreement_<ts>.csv``      — per (experiment, assay, question) agreement.
  * ``tier3_model_summary_<ts>.csv``  — per (experiment, model) aggregates.
"""

import os
import sys
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myocyte.settings")
django.setup()

# ── Django configured; safe to import the rest ──
import logging  # noqa: E402
import re  # noqa: E402
from datetime import datetime  # noqa: E402

import pandas as pd  # noqa: E402
from django.core.management.color import make_style  # noqa: E402
from tqdm.auto import tqdm  # noqa: E402

from toxtempass.evaluation.config import config as eval_config  # noqa: E402
from toxtempass.evaluation.post_processing.faithfulness_ragas import (  # noqa: E402
    faithfulness_score,
    make_faithfulness_metric,
)
from toxtempass.evaluation.pre_evaluation.answer_quality_scorer import (  # noqa: E402
    score_answer_with_llm,
)
from toxtempass.evaluation.real_world.answer_utils import parse_answer  # noqa: E402
from toxtempass.evaluation.utils import resolve_eval_llm  # noqa: E402

logger = logging.getLogger("llm")
style = make_style()

# ════════════════════════ configuration (edit here) ════════════════════════
DO_AGREEMENT: bool = True       # cross-model cosine (needs an embedding deployment)
DO_QUALITY: bool = True         # LLM-judge quality (needs the judge model)
DO_FAITHFULNESS: bool = True    # RAGAS faithfulness (needs the judge model)

# Max characters of context handed to the faithfulness judge (~4 chars/token).
FAITHFULNESS_CONTEXT_CHARS: int = 400_000
# ════════════════════════════════════════════════════════════════════════════

OUTPUT_ROOT = eval_config.real_world_output
ANALYSIS_DIR = OUTPUT_ROOT / "_analysis"

QUALITY_NUMERIC = {"High": 1.0, "Medium": 0.5, "Low": 0.0}


def resolve_judge() -> object:
    """Resolve the configured judge model via the shared resolver."""
    llm, info, _ = resolve_eval_llm(eval_config.judge_model, 0)
    if llm is None:
        raise SystemExit(
            f"Judge model {eval_config.judge_model!r} not resolvable: {info}. "
            "Deploy it and set eval_config.judge_model to its model id."
        )
    print(style.SUCCESS(f"Judge: {eval_config.judge_model} via {info}."))
    return llm


def _norm(text: str) -> str:
    """Whitespace-normalize for robust verbatim substring matching."""
    return re.sub(r"\s+", " ", text or "").strip().lower()


def quotes_verbatim_fraction(quotes: list[str], context: str) -> float | None:
    """Fraction of supporting_quotes that appear verbatim in the context.

    Returns None when there are no quotes (n/a). Whitespace-normalized so trivial
    spacing differences don't count as misses.
    """
    quotes = [q for q in (quotes or []) if q and q.strip()]
    if not quotes:
        return None
    ctx = _norm(context)
    hits = sum(1 for q in quotes if _norm(q) in ctx)
    return round(hits / len(quotes), 3)


def load_answers() -> dict:
    """Walk ``output/<experiment>/<model>/tier3_answers_<assay>.csv``.

    Returns ``{(experiment, assay, question): {model: parsed_answer_dict}}``.
    """
    index: dict = {}
    experiment_dirs = [
        d for d in sorted(OUTPUT_ROOT.iterdir())
        if d.is_dir() and not d.name.startswith("_")
    ]
    if not experiment_dirs:
        raise SystemExit(
            f"No experiment output dirs under {OUTPUT_ROOT}; run generation first."
        )
    n_models = 0
    for exp_dir in experiment_dirs:
        for model_dir in sorted(p for p in exp_dir.iterdir() if p.is_dir()):
            n_models += 1
            model = model_dir.name
            for csv_path in sorted(model_dir.glob("tier3_answers_*.csv")):
                assay = csv_path.stem[len("tier3_answers_"):]
                df = pd.read_csv(csv_path).fillna("")
                for _, row in df.iterrows():
                    parsed = parse_answer(str(row.get("answer", "")))
                    key = (exp_dir.name, assay, str(row.get("question", "")))
                    index.setdefault(key, {})[model] = parsed
    print(
        style.HTTP_INFO(
            f"Loaded {len(experiment_dirs)} experiment(s), {n_models} model dir(s), "
            f"{len(index)} (experiment, assay, question) rows."
        )
    )
    return index


def load_context(experiment: str, assay: str, cache: dict) -> str:
    """Return the (truncated) experiment-scoped context for an assay, cached.

    Context lives at ``output/<experiment>/_context/<assay>.txt`` because it can
    differ per experiment (e.g. when ``extract_images`` differs).
    """
    cache_key = (experiment, assay)
    if cache_key not in cache:
        path = OUTPUT_ROOT / experiment / "_context" / f"{assay}.txt"
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        if not text:
            logger.warning("No context file for %r/%r at %s", experiment, assay, path)
        cache[cache_key] = text[:FAITHFULNESS_CONTEXT_CHARS]
    return cache[cache_key]


def main() -> None:
    """Compute the four reference-free metrics and write the analysis CSVs."""
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    index = load_answers()

    judge = resolve_judge() if (DO_QUALITY or DO_FAITHFULNESS) else None
    faith_metric = make_faithfulness_metric(judge) if DO_FAITHFULNESS else None
    breakdown = None
    if DO_AGREEMENT:
        # Lazy import: the embeddings client needs credentials, so only pull it in
        # when agreement is requested.
        from toxtempass.evaluation.post_processing.pairwise_cosine_similarities import (
            pairwise_cosine_breakdown,
        )

        breakdown = pairwise_cosine_breakdown

    context_cache: dict = {}
    metric_rows: list[dict] = []
    agreement_rows: list[dict] = []

    for (experiment, assay, question), models in tqdm(
        sorted(index.items()), desc="Scoring", position=0, leave=True
    ):
        per_model_agreement: dict = {}
        if breakdown is not None:
            answered = {
                m: p["answer"] for m, p in models.items() if not p["not_found"]
            }
            overall, per_model_agreement = breakdown(answered)
            agreement_rows.append(
                {
                    "experiment": experiment,
                    "assay": assay,
                    "question": question,
                    "n_models_answered": len(answered),
                    "mean_pairwise_cosine": overall,
                }
            )

        for model, parsed in models.items():
            quality_score = ""
            faith_score: float | str = ""
            quotes_verbatim = ""
            if not parsed["not_found"]:
                answer_text = parsed["answer"]
                if DO_QUALITY:
                    quality_score = score_answer_with_llm(
                        question, answer_text, judge_llm=judge
                    )[0]
                if DO_FAITHFULNESS:
                    val = faithfulness_score(
                        question,
                        answer_text,
                        load_context(experiment, assay, context_cache),
                        faith_metric,
                    )
                    faith_score = "" if val is None else val
                if parsed["is_structured"]:
                    frac = quotes_verbatim_fraction(
                        parsed["supporting_quotes"],
                        load_context(experiment, assay, context_cache),
                    )
                    quotes_verbatim = "" if frac is None else frac
            metric_rows.append(
                {
                    "experiment": experiment,
                    "assay": assay,
                    "question": question,
                    "model": model,
                    "answerable": parsed["answerable"],
                    "answer": parsed["answer"],
                    "confidence": parsed["confidence"],
                    "source": parsed["source"],
                    "not_found": parsed["not_found"],
                    "quality_score": quality_score,
                    "faithfulness_score": faith_score,
                    "quotes_verbatim": quotes_verbatim,
                    "model_agreement": per_model_agreement.get(model, ""),
                }
            )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    metrics_df = pd.DataFrame(metric_rows)
    metrics_path = ANALYSIS_DIR / f"tier3_metrics_{timestamp}.csv"
    metrics_df.to_csv(metrics_path, index=False)
    print(style.SUCCESS(f"Per-answer metrics → {metrics_path}"))

    if agreement_rows:
        agreement_path = ANALYSIS_DIR / f"tier3_agreement_{timestamp}.csv"
        pd.DataFrame(agreement_rows).to_csv(agreement_path, index=False)
        print(style.SUCCESS(f"Cross-model agreement → {agreement_path}"))

    # ── Per-(experiment, model) aggregates ──────────────────────────────────
    # Denominator = the full set of (assay, question) seen across all models in an
    # experiment, so a model that skipped an assay is penalized rather than credited
    # with an inflated completeness rate.
    expected_per_exp = {
        exp: g[["assay", "question"]].drop_duplicates().shape[0]
        for exp, g in metrics_df.groupby("experiment")
    }
    summary_rows = []
    for (experiment, model), grp in metrics_df.groupby(["experiment", "model"]):
        answered = grp[~grp["not_found"].astype(bool)]
        quality_num = answered["quality_score"].map(QUALITY_NUMERIC).dropna()
        # RAGAS faithfulness is already a 0-1 float.
        faith_num = pd.to_numeric(
            answered["faithfulness_score"], errors="coerce"
        ).dropna()
        agreement_vals = pd.to_numeric(grp["model_agreement"], errors="coerce").dropna()
        verbatim_vals = pd.to_numeric(grp["quotes_verbatim"], errors="coerce").dropna()
        expected = expected_per_exp.get(experiment) or len(grp)
        summary_rows.append(
            {
                "experiment": experiment,
                "model": model,
                "n_answered": int(len(answered)),
                "n_scored": int(len(grp)),
                "n_expected": int(expected),
                "completeness_rate": round(100 * len(answered) / expected, 2)
                if expected else 0.0,
                "mean_quality": round(float(quality_num.mean()), 4)
                if len(quality_num) else None,
                "mean_faithfulness": round(float(faith_num.mean()), 4)
                if len(faith_num) else None,
                "mean_agreement": round(float(agreement_vals.mean()), 4)
                if len(agreement_vals) else None,
                "mean_quotes_verbatim": round(float(verbatim_vals.mean()), 4)
                if len(verbatim_vals) else None,
            }
        )
    summary_df = pd.DataFrame(summary_rows)
    summary_path = ANALYSIS_DIR / f"tier3_model_summary_{timestamp}.csv"
    summary_df.to_csv(summary_path, index=False)
    print(style.SUCCESS(f"Per-model summary → {summary_path}"))
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
