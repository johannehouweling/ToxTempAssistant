"""Calibrate the cheap response-relevancy judge against a stronger reference judge.

Does the Gemini-Flash relevancy judge (``eval_config.judge_model``) agree with a stronger
neutral reference (claude-sonnet-4-6)? Scores a SMALL stratified sample of non-trivial
cross_provider answers — the same citation/abstention-stripped substantive text
``tier3_metrics`` scores — with both judges: correlation + mean diff, overall and
PER ASSAY, plus how often the two judges agree on the ``noncommittal`` (evasive) flag.

What this isolates: response relevancy = mean cosine of the judge's reverse-generated
questions vs the original, gated by ``noncommittal``. The EMBEDDING (and thus the cosine)
is identical for both judges — only the question generation + the evasive flag differ. So
this measures exactly the LLM-dependent part of the metric. NB: this is inter-judge
robustness, NOT calibration against human relevance — a within-spec sanity check only.

Read-only on the eval outputs; writes a small CSV under ``_analysis/``. Needs the Gemini
E9 endpoint (judge), the Anthropic E5 Sonnet (reference), and the OpenAI embeddings key.

    cd myocyte && USE_POSTGRES=false DJANGO_DEBUG=true poetry run python \
        toxtempass/evaluation/real_world/calibrate_relevancy_judge.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myocyte.settings")
django.setup()

import asyncio  # noqa: E402
import logging  # noqa: E402
import random  # noqa: E402
from datetime import datetime  # noqa: E402

import pandas as pd  # noqa: E402
from django.core.management.color import make_style  # noqa: E402
from tqdm.auto import tqdm  # noqa: E402

from toxtempass.evaluation.config import config as eval_config  # noqa: E402
from toxtempass.evaluation.post_processing.answer_relevancy_ragas import (  # noqa: E402
    make_relevancy_metric,
    relevancy_aexplain,
)
from toxtempass.evaluation.post_processing.embeddings import get_client  # noqa: E402
from toxtempass.evaluation.real_world.answer_utils import parse_answer  # noqa: E402
from toxtempass.evaluation.utils import resolve_eval_llm  # noqa: E402

style = make_style()
logging.getLogger("llm").setLevel(logging.ERROR)  # quiet per-call retry warnings

EXPERIMENT = "cross_provider"
REF_JUDGE = "claude-sonnet-4-6"     # stronger reference (matches faithfulness calib)
N_PER_ASSAY = 4                     # small: ~4 × 9 assays ≈ 36 answers × 2 judges
SEED = 0
MAX_WORKERS = 4
STRICTNESS = 3                      # mirrors tier3_metrics.RELEVANCY_STRICTNESS
OUT = eval_config.real_world_output


def collect_sample() -> list[dict]:
    """Stratified seeded sample of non-trivial answers (~N_PER_ASSAY per assay).

    Mirrors the faithfulness calibration's sampling so the two studies are comparable.
    Relevancy needs no context, only the question + substantive answer text.
    """
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


def score_all(
    sample: list[dict], metric: object, label: str
) -> tuple[list[float | None], list[int | None]]:
    """Concurrently score every sampled answer's relevancy with one judge.

    Runs in ONE asyncio event loop with a semaphore (the tier3_metrics pattern) — NOT a
    ThreadPoolExecutor of per-call ``asyncio.run``: that reuses RAGAS's cached
    ``httpx.AsyncClient`` across closed event loops and hangs forever. Returns parallel
    lists ``(scores, noncommittal_flags)``; entries are ``None`` when the judge errored
    after retries (so callers can drop them).
    """
    scores: list[float | None] = [None] * len(sample)
    ncs: list[int | None] = [None] * len(sample)

    async def _run() -> None:
        sem = asyncio.Semaphore(MAX_WORKERS)

        async def _one(i: int) -> tuple[int, dict | None]:
            async with sem:
                res = await relevancy_aexplain(
                    sample[i]["question"], sample[i]["text"], metric
                )
            return i, res

        coros = [_one(i) for i in range(len(sample))]
        for fut in tqdm(asyncio.as_completed(coros), total=len(coros), desc=label):
            i, res = await fut
            if res is not None and res["score"] is not None:
                scores[i] = float(res["score"])
                ncs[i] = int(bool(res["noncommittal"]))

    asyncio.run(_run())
    return scores, ncs


def main() -> None:
    """Score the sample with both judges and report agreement (overall + per assay)."""
    flash_llm, info_f, _ = resolve_eval_llm(eval_config.judge_model, 0)
    ref_llm, info_r, _ = resolve_eval_llm(REF_JUDGE, 0)
    if flash_llm is None or ref_llm is None:
        raise SystemExit(f"Judge not resolvable: flash={info_f!r} ref={info_r!r}")
    print(style.SUCCESS(f"Flash judge: {eval_config.judge_model} via {info_f}"))
    print(style.SUCCESS(f"Ref judge:   {REF_JUDGE} via {info_r}"))

    embeddings = get_client()  # SAME for both judges → isolates the LLM-dependent part
    sample = collect_sample()
    if not sample:
        raise SystemExit("No non-trivial cross_provider answers found.")
    print(style.HTTP_INFO(
        f"Calibrating relevancy on {len(sample)} answers (~{N_PER_ASSAY}/assay) × 2 "
        f"judges (strictness={STRICTNESS}, shared embeddings)."
    ))
    flash, flash_nc = score_all(
        sample, make_relevancy_metric(flash_llm, embeddings, STRICTNESS), "flash"
    )
    ref, ref_nc = score_all(
        sample, make_relevancy_metric(ref_llm, embeddings, STRICTNESS), "ref  "
    )

    df = pd.DataFrame(sample)
    df["score_flash"] = flash
    df["score_ref"] = ref
    df["nc_flash"] = flash_nc
    df["nc_ref"] = ref_nc
    both = df.dropna(subset=["score_flash", "score_ref"]).copy()
    both["diff"] = both["score_flash"] - both["score_ref"]

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out_csv = OUT / "_analysis" / f"relevancy_calibration_{ts}.csv"
    df.to_csv(out_csv, index=False)

    n = len(both)
    if n < 2:
        print(style.ERROR(f"Only {n} scored by both judges — cannot correlate."))
        print(f"CSV → {out_csv}")
        return
    pearson = both["score_flash"].corr(both["score_ref"])
    spearman = both["score_flash"].corr(both["score_ref"], method="spearman")
    print(style.SUCCESS(f"\n=== Relevancy judge calibration (n={n}) ==="))
    print(f"  mean Flash = {both['score_flash'].mean():.3f}   "
          f"mean Ref = {both['score_ref'].mean():.3f}   "
          f"mean diff (Flash−Ref) = {both['diff'].mean():+.3f}")
    print(f"  mean|diff| = {both['diff'].abs().mean():.3f}   "
          f"|diff|>0.2: {(both['diff'].abs() > 0.2).sum()}/{n}")
    print(f"  Pearson r = {pearson:.3f}   Spearman r = {spearman:.3f}")
    # Noncommittal (evasive) flag agreement — the other LLM-dependent output.
    nc_both = df.dropna(subset=["nc_flash", "nc_ref"])
    if len(nc_both):
        agree = int((nc_both["nc_flash"] == nc_both["nc_ref"]).sum())
        print(f"  noncommittal flag agreement: {agree}/{len(nc_both)} "
              f"(Flash evasive={int(nc_both['nc_flash'].sum())}, "
              f"Ref evasive={int(nc_both['nc_ref'].sum())})")
    print("  per-assay mean diff (Flash−Ref), sorted:")
    per = both.groupby("assay")["diff"].agg(["mean", "count"]).sort_values("mean")
    for assay, r in per.iterrows():
        print(f"    {assay:22.22s} {r['mean']:+.3f}  (n={int(r['count'])})")
    print(f"\nCSV → {out_csv}")


if __name__ == "__main__":
    main()
