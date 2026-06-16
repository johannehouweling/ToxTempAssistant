"""Calibrate the cheap faithfulness judge against a stronger reference judge.

Does the Gemini-Flash faithfulness judge (``eval_config.judge_model``) agree with a
stronger neutral reference (claude-sonnet-4-6)? This scores a SMALL stratified sample of
non-trivial cross_provider answers — the same citation/abstention-stripped substantive
text ``tier3_metrics`` scores — with both judges, reporting correlation + mean diff,
overall and PER ASSAY. The per-assay view is the point: if Flash systematically
under-scores groundedness on big-context assays (a long-context recall miss, not real
hallucination), it shows up as a negative mean diff that grows with context size.

Read-only on the eval outputs; writes a small CSV under ``_analysis/``. Needs BOTH judges
deployed (the Gemini E9 endpoint + the Anthropic E5 Sonnet).

    cd myocyte && USE_POSTGRES=false DJANGO_DEBUG=true poetry run python \
        toxtempass/evaluation/real_world/calibrate_faithfulness_judge.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myocyte.settings")
django.setup()

import logging  # noqa: E402
import random  # noqa: E402
from concurrent.futures import ThreadPoolExecutor, as_completed  # noqa: E402
from datetime import datetime  # noqa: E402

import pandas as pd  # noqa: E402
from django.core.management.color import make_style  # noqa: E402
from tqdm.auto import tqdm  # noqa: E402

from toxtempass.evaluation.config import config as eval_config  # noqa: E402
from toxtempass.evaluation.post_processing.faithfulness_ragas import (  # noqa: E402
    faithfulness_score,
    make_faithfulness_metric,
)
from toxtempass.evaluation.real_world.answer_utils import parse_answer  # noqa: E402
from toxtempass.evaluation.utils import resolve_eval_llm  # noqa: E402

style = make_style()
logging.getLogger("llm").setLevel(logging.ERROR)  # quiet per-call retry warnings

EXPERIMENT = "cross_provider"
REF_JUDGE = "claude-sonnet-4-6"     # stronger neutral reference judge
N_PER_ASSAY = 4                     # small: ~4 × 9 assays ≈ 36 answers × 2 judges
SEED = 0
MAX_WORKERS = 4
CONTEXT_CHARS = 400_000             # mirrors tier3_metrics.FAITHFULNESS_CONTEXT_CHARS
OUT = eval_config.real_world_output

_ctx_cache: dict[str, str] = {}


def _load_ctx(assay: str) -> str:
    """Return the (truncated) assembled context for an assay, cached."""
    if assay not in _ctx_cache:
        path = OUT / EXPERIMENT / "_context" / f"{assay}.txt"
        text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        _ctx_cache[assay] = text[:CONTEXT_CHARS]
    return _ctx_cache[assay]


def collect_sample() -> list[dict]:
    """Stratified seeded sample of non-trivial answers (~N_PER_ASSAY per assay)."""
    pool: dict[str, list[dict]] = {}
    exp_root = OUT / EXPERIMENT
    model_dirs = sorted(
        p for p in exp_root.iterdir() if p.is_dir() and not p.name.startswith("_")
    )
    for model_dir in model_dirs:
        for csv in sorted(model_dir.glob("tier3_answers_*.csv")):
            assay = csv.stem[len("tier3_answers_"):]
            df = pd.read_csv(csv).fillna("")
            for row in df.itertuples():
                parsed = parse_answer(str(getattr(row, "answer", "")))
                if parsed["is_trivial"]:
                    continue
                pool.setdefault(assay, []).append(
                    {
                        "assay": assay,
                        "model": model_dir.name,
                        "question_id": getattr(row, "question_id", ""),
                        "question": str(getattr(row, "question", "")),
                        "text": parsed["substantive_text"],
                    }
                )
    sample: list[dict] = []
    for assay in sorted(pool):
        rng = random.Random(f"{SEED}|{assay}")  # noqa: S311
        items = pool[assay]
        sample.extend(rng.sample(items, min(N_PER_ASSAY, len(items))))
    return sample


def score_all(sample: list[dict], metric: object, label: str) -> list[float | None]:
    """Concurrently score every sampled answer's faithfulness with one judge."""
    scores: list[float | None] = [None] * len(sample)

    def _one(i: int) -> tuple[int, float | None]:
        """Score sample[i] and return (index, score)."""
        s = sample[i]
        ctx = _load_ctx(s["assay"])
        return i, faithfulness_score(s["question"], s["text"], ctx, metric)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(_one, i) for i in range(len(sample))]
        for fut in tqdm(as_completed(futures), total=len(futures), desc=label):
            i, val = fut.result()
            scores[i] = val
    return scores


def main() -> None:
    """Score the sample with both judges and report agreement (overall + per assay)."""
    flash_llm, info_f, _ = resolve_eval_llm(eval_config.judge_model, 0)
    ref_llm, info_r, _ = resolve_eval_llm(REF_JUDGE, 0)
    if flash_llm is None or ref_llm is None:
        raise SystemExit(f"Judge not resolvable: flash={info_f!r} ref={info_r!r}")
    print(style.SUCCESS(f"Flash judge: {eval_config.judge_model} via {info_f}"))
    print(style.SUCCESS(f"Ref judge:   {REF_JUDGE} via {info_r}"))

    sample = collect_sample()
    if not sample:
        raise SystemExit("No non-trivial cross_provider answers found.")
    print(style.HTTP_INFO(
        f"Calibrating on {len(sample)} answers (~{N_PER_ASSAY}/assay) × 2 judges."
    ))
    flash = score_all(sample, make_faithfulness_metric(flash_llm), "flash")
    ref = score_all(sample, make_faithfulness_metric(ref_llm), "ref ")

    df = pd.DataFrame(sample)
    df["score_flash"] = flash
    df["score_ref"] = ref
    both = df.dropna(subset=["score_flash", "score_ref"]).copy()
    both["diff"] = both["score_flash"] - both["score_ref"]

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out_csv = OUT / "_analysis" / f"faithfulness_calibration_{ts}.csv"
    df.to_csv(out_csv, index=False)

    n = len(both)
    if n < 2:
        print(style.ERROR(f"Only {n} scored by both judges — cannot correlate."))
        print(f"CSV → {out_csv}")
        return
    pearson = both["score_flash"].corr(both["score_ref"])
    spearman = both["score_flash"].corr(both["score_ref"], method="spearman")
    print(style.SUCCESS(f"\n=== Faithfulness judge calibration (n={n}) ==="))
    print(f"  mean Flash = {both['score_flash'].mean():.3f}   "
          f"mean Ref = {both['score_ref'].mean():.3f}   "
          f"mean diff (Flash−Ref) = {both['diff'].mean():+.3f}")
    print(f"  mean|diff| = {both['diff'].abs().mean():.3f}   "
          f"|diff|>0.3: {(both['diff'].abs() > 0.3).sum()}/{n}")
    print(f"  Pearson r = {pearson:.3f}   Spearman r = {spearman:.3f}")
    print("  per-assay mean diff (Flash−Ref), sorted (watch the big-context assays):")
    per = both.groupby("assay")["diff"].agg(["mean", "count"]).sort_values("mean")
    for assay, r in per.iterrows():
        print(f"    {assay:22.22s} {r['mean']:+.3f}  (n={int(r['count'])})")
    print(f"\nCSV → {out_csv}")


if __name__ == "__main__":
    main()
