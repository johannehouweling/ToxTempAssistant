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
import asyncio  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import random  # noqa: E402
import re  # noqa: E402
from datetime import datetime  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from django.core.management.color import make_style  # noqa: E402
from tqdm.auto import tqdm  # noqa: E402

from toxtempass.evaluation.config import config as eval_config  # noqa: E402
from toxtempass.evaluation.post_processing.faithfulness_ragas import (  # noqa: E402
    faithfulness_aexplain,
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

# Faithfulness cost controls ----------------------------------------------------
# Score only K questions per (experiment, assay); None = score every answered one.
# The SAME sampled question_ids are used across all models in an assay so per-model
# means stay comparable; seeded → reproducible across re-runs and models.
FAITHFULNESS_SAMPLE_PER_ASSAY: int | None = None
FAITHFULNESS_SAMPLE_SEED: int = 0
# Concurrent judge calls for the faithfulness pass. The Gemini (E9 OpenAI-compat)
# endpoint isn't in eval_config.endpoint_concurrency; tune here. Lower if 429s.
FAITHFULNESS_MAX_WORKERS: int = 8
# Restrict faithfulness scoring to these experiments (skips self_consistency
# reruns); empty set = all experiments. Quality/agreement are unaffected.
FAITHFULNESS_EXPERIMENTS: set[str] = {"cross_provider"}
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
                    # Key by question_id (stable join across models); fall back to
                    # question text for older CSVs that predate the id column.
                    qid = str(row.get("question_id", "")) or str(row.get("question", ""))
                    key = (exp_dir.name, assay, qid)
                    entry = index.setdefault(
                        key,
                        {
                            "question_id": row.get("question_id", ""),
                            "question": str(row.get("question", "")),
                            "section": str(row.get("section", "")),
                            "subsection": str(row.get("subsection", "")),
                            "models": {},
                        },
                    )
                    entry["models"][model] = parsed
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


N_BOOTSTRAP = 2000  # resamples for the cluster-bootstrap CI (fixed seed → reproducible)


def _cluster_bootstrap_ci(
    values_by_assay: list[np.ndarray], n_boot: int = N_BOOTSTRAP, seed: int = 0
) -> tuple[float | None, float | None]:
    """95% CI for a per-model mean via resampling whole ASSAYS with replacement.

    The assay is the independent unit (questions within an assay are correlated), so we
    resample assays (not questions) to avoid a fakely narrow interval.
    ``values_by_assay`` is one array of per-question metric values per assay. Returns
    ``(lo, hi)`` (the 2.5/97.5 percentiles of the resampled means), or ``(None, None)``
    if fewer than 2 assays have values. Seeded so re-runs are reproducible.
    """
    clusters = [np.asarray(v, dtype=float) for v in values_by_assay if len(v)]
    if len(clusters) < 2:
        return None, None
    rng = np.random.default_rng(seed)
    k = len(clusters)
    means = np.empty(n_boot)
    for b in range(n_boot):
        pooled = np.concatenate([clusters[i] for i in rng.integers(0, k, size=k)])
        means[b] = pooled.mean()
    lo, hi = np.percentile(means, [2.5, 97.5])
    return round(float(lo), 4), round(float(hi), 4)


def _dispersion(
    grp: pd.DataFrame, col: str
) -> tuple[int, float | None, float | None, float | None]:
    """Return ``(n, sd, ci_lo, ci_hi)`` for a numeric metric column of ``grp``.

    Reusable across agreement / faithfulness / quality: ``n`` = non-null values, ``sd`` =
    sample std, ``(ci_lo, ci_hi)`` = cluster-bootstrap-by-assay 95% CI of the mean.
    """
    s = pd.to_numeric(grp[col], errors="coerce")
    vals = s.dropna()
    n = int(len(vals))
    sd = round(float(vals.std(ddof=1)), 4) if n > 1 else None
    by_assay = [
        pd.to_numeric(sub[col], errors="coerce").dropna().to_numpy()
        for _, sub in grp.groupby("assay")
    ]
    ci_lo, ci_hi = _cluster_bootstrap_ci(by_assay)
    return n, sd, ci_lo, ci_hi


def _load_checkpoint(path: Path, judge: str) -> dict:
    """Load prior faithfulness results for ``judge`` from the JSONL checkpoint.

    Returns ``{(experiment, assay, question_id, model): record}`` so a re-run skips
    already-scored answers (resume). Records for a different judge are ignored; later
    writes win. A missing file or a corrupt line is skipped, never fatal.
    """
    done: dict = {}
    if not path.exists():
        return done
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("judge") != judge:
                continue
            done[(r["experiment"], r["assay"], str(r["question_id"]), r["model"])] = r
    return done


def _load_checkpoint(path: Path, judge: str) -> dict:
    """Load prior faithfulness results for ``judge`` from the JSONL checkpoint.

    Returns ``{(experiment, assay, question_id, model): record}`` so a re-run skips
    already-scored answers (resume). Records for a different judge are ignored; later
    writes win. A missing file or a corrupt line is skipped, never fatal.
    """
    done: dict = {}
    if not path.exists():
        return done
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("judge") != judge:
                continue
            done[(r["experiment"], r["assay"], str(r["question_id"]), r["model"])] = r
    return done


def main() -> None:
    """Compute the four reference-free metrics and write the analysis CSVs."""
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    index = load_answers()

    judge = resolve_judge() if (DO_QUALITY or DO_FAITHFULNESS) else None
    faith_metric = make_faithfulness_metric(judge) if DO_FAITHFULNESS else None

    # Agreement reads precomputed vectors from the embedding cache (built by
    # build_embeddings.py) and scores both the raw and the normalized embedding of
    # each answer — no inline embedding here.
    cache = None
    vec_index: dict = {}
    pairwise_cosine_from_vectors = None
    if DO_AGREEMENT:
        from toxtempass.evaluation.post_processing.embeddings import EmbeddingCache
        from toxtempass.evaluation.post_processing.pairwise_cosine_similarities import (
            pairwise_cosine_from_vectors,
        )

        emb_dir = OUTPUT_ROOT / "_embeddings"
        idx_path = emb_dir / "answer_index.csv"
        cache = EmbeddingCache(emb_dir)
        if len(cache) == 0 or not idx_path.exists():
            raise SystemExit(
                f"No embedding cache at {emb_dir}. Run build_embeddings.py first."
            )
        for r in pd.read_csv(idx_path).fillna("").itertuples():
            vec_index[(r.experiment, r.model, r.assay, str(r.question_id))] = (
                str(r.raw_sha1),
                str(r.norm_sha1),
            )

    context_cache: dict = {}
    metric_rows: list[dict] = []
    agreement_rows: list[dict] = []

    # Faithfulness is scored in a separate concurrent pass (after this loop): collect
    # tasks here, merge score + claim counts back by row index, and accumulate the
    # per-claim breakdown into faith_detail for the detail CSV.
    faith_tasks: list[tuple] = []
    faith_detail: list[dict] = []
    qids_by_assay: dict[tuple[str, str], list[str]] = {}
    sec_qids_by_assay: dict[tuple[str, str], dict[str, list[str]]] = {}
    for (_ek, _ak, _qk), _entry in index.items():
        qids_by_assay.setdefault((_ek, _ak), []).append(_qk)
        sec_qids_by_assay.setdefault((_ek, _ak), {}).setdefault(
            str(_entry["section"]), []
        ).append(_qk)
    for _k in qids_by_assay:
        qids_by_assay[_k].sort()

    # Resume + nesting source: questions already scored for THIS judge, so a larger-K
    # re-sample keeps them (and the checkpoint reuses them instead of re-scoring).
    faith_ckpt_path = ANALYSIS_DIR / "faithfulness_checkpoint.jsonl"
    faith_done = (
        _load_checkpoint(faith_ckpt_path, eval_config.judge_model)
        if DO_FAITHFULNESS else {}
    )
    prior_qids_by_assay: dict[tuple[str, str], set[str]] = {}
    for (_pe, _pa, _pq, _pm) in faith_done:
        prior_qids_by_assay.setdefault((_pe, _pa), set()).add(_pq)

    _sampled_cache: dict[tuple[str, str], set[str] | None] = {}

    def _sampled_qids(exp: str, assay: str) -> set[str] | None:
        """Section-stratified (proportional, >=1/section), seeded, nested over prior.

        Keeps every question already scored for this judge (so re-sampling at a larger K
        reuses them, no re-scoring) and fills each section to its proportional quota.
        ``None`` = score every answer.
        """
        if FAITHFULNESS_SAMPLE_PER_ASSAY is None:
            return None
        key = (exp, assay)
        if key not in _sampled_cache:
            sections = sec_qids_by_assay.get(key, {})
            total = sum(len(v) for v in sections.values()) or 1
            k = FAITHFULNESS_SAMPLE_PER_ASSAY
            rng = random.Random(f"{FAITHFULNESS_SAMPLE_SEED}|{exp}|{assay}")  # noqa: S311
            selected = set(prior_qids_by_assay.get(key, set()))  # nest: keep prior
            for sec in sorted(sections):
                sec_qs = sorted(sections[sec])
                quota = max(1, round(k * len(sec_qs) / total))
                need = quota - len(selected.intersection(sec_qs))
                if need > 0:
                    pool = [q for q in sec_qs if q not in selected]
                    rng.shuffle(pool)
                    selected.update(pool[:need])
            _sampled_cache[key] = selected
        return _sampled_cache[key]

    for (experiment, assay, _qid), entry in tqdm(
        sorted(index.items()), desc="Scoring", position=0, leave=True
    ):
        question = entry["question"]
        question_id = entry["question_id"]
        section = entry["section"]
        subsection = entry["subsection"]
        models = entry["models"]

        per_raw: dict = {}
        per_norm: dict = {}
        if DO_AGREEMENT:
            # Pull each participating (non-trivial) model's raw + normalized vectors
            # from the cache; models with a trivial answer aren't in the index.
            raw_vecs: dict = {}
            norm_vecs: dict = {}
            for model in models:
                shas = vec_index.get((experiment, model, assay, str(question_id)))
                if not shas:
                    continue
                raw_sha, norm_sha = shas
                if raw_sha in cache:
                    raw_vecs[model] = cache[raw_sha]
                if norm_sha in cache:
                    norm_vecs[model] = cache[norm_sha]
            overall_raw, per_raw = pairwise_cosine_from_vectors(raw_vecs)
            overall_norm, per_norm = pairwise_cosine_from_vectors(norm_vecs)
            agreement_rows.append(
                {
                    "experiment": experiment,
                    "assay": assay,
                    "question_id": question_id,
                    "section": section,
                    "subsection": subsection,
                    "question": question,
                    "n_models": len(raw_vecs),
                    "mean_cosine_raw": overall_raw,
                    "mean_cosine_normalized": overall_norm,
                }
            )

        for model, parsed in models.items():
            quality_score = ""
            quotes_verbatim = ""
            if not parsed["not_found"]:
                answer_text = parsed["answer"]
                if DO_QUALITY:
                    quality_score = score_answer_with_llm(
                        question, answer_text, judge_llm=judge
                    )[0]
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
                    "question_id": question_id,
                    "section": section,
                    "subsection": subsection,
                    "question": question,
                    "model": model,
                    "answerable": parsed["answerable"],
                    "answer": parsed["answer"],
                    "confidence": parsed["confidence"],
                    "source": parsed["source"],
                    "not_found": parsed["not_found"],
                    "quality_score": quality_score,
                    "faithfulness_score": "",  # filled by the concurrent pass below
                    "faithfulness_n_claims": "",
                    "faithfulness_n_supported": "",
                    "faithfulness_n_unsupported": "",
                    "quotes_verbatim": quotes_verbatim,
                    "model_agreement_raw": per_raw.get(model, ""),
                    "model_agreement_normalized": per_norm.get(model, ""),
                }
            )
            # Queue NON-TRIVIAL answers (answered + hedged) for the concurrent
            # faithfulness pass, scoring the citation/abstention-stripped substantive
            # text so a hedge sentence doesn't count as an unsupported claim. The row
            # index merges the score back without re-sorting.
            if (
                DO_FAITHFULNESS
                and not parsed["is_trivial"]
                and (
                    not FAITHFULNESS_EXPERIMENTS
                    or experiment in FAITHFULNESS_EXPERIMENTS
                )
            ):
                sampled = _sampled_qids(experiment, assay)
                if sampled is None or str(question_id) in sampled:
                    faith_tasks.append(
                        (
                            len(metric_rows) - 1,
                            experiment,
                            assay,
                            str(question_id),
                            model,
                            question,
                            parsed["substantive_text"],
                            load_context(experiment, assay, context_cache),
                        )
                    )

    # Concurrent faithfulness pass with a DURABLE checkpoint. Each score is appended to a
    # JSONL the instant it's computed (so out-of-credits/crash mid-run loses at most the
    # in-flight handful), and a re-run RESUMES — answers already scored for this judge are
    # loaded from the checkpoint, not re-scored. Scoring runs in one event loop (asyncio +
    # semaphore) so the LLM I/O truly overlaps; the per-claim breakdown is kept (free).
    if DO_FAITHFULNESS and faith_tasks:
        judge_id = eval_config.judge_model
        ckpt_path = faith_ckpt_path
        done = faith_done

        def _merge(idx: int, exp: str, asy: str, qid: str, mdl: str, res: dict) -> None:
            row = metric_rows[idx]
            row["faithfulness_score"] = res["score"]
            row["faithfulness_n_claims"] = res["n_claims"]
            row["faithfulness_n_supported"] = res["n_supported"]
            row["faithfulness_n_unsupported"] = res["n_unsupported"]
            for c in res.get("claims", []):
                faith_detail.append(
                    {
                        "experiment": exp, "assay": asy, "question_id": qid,
                        "model": mdl, "verdict": c["verdict"],
                        "statement": c["statement"], "reason": c["reason"],
                    }
                )

        # Resume: merge already-scored answers from the checkpoint; queue only the rest.
        todo = []
        for t in faith_tasks:
            key = (t[1], t[2], t[3], t[4])  # (experiment, assay, question_id, model)
            if key in done:
                _merge(t[0], t[1], t[2], t[3], t[4], done[key])
            else:
                todo.append(t)
        print(style.HTTP_INFO(
            f"Faithfulness [{judge_id}]: {len(done)} cached, scoring {len(todo)} new "
            f"at concurrency {FAITHFULNESS_MAX_WORKERS}…"
        ))

        n_failed = 0
        if todo:
            ckpt = ckpt_path.open("a", encoding="utf-8")

            async def _run_faith() -> int:
                sem = asyncio.Semaphore(FAITHFULNESS_MAX_WORKERS)

                async def _one(task: tuple) -> tuple:
                    idx, exp, asy, qid, mdl, q, a, ctx = task
                    async with sem:
                        res = await faithfulness_aexplain(q, a, ctx, faith_metric)
                    return idx, exp, asy, qid, mdl, res

                failed = 0
                coros = [_one(t) for t in todo]
                for fut in tqdm(
                    asyncio.as_completed(coros), total=len(coros),
                    desc="Faithfulness", position=0, leave=True,
                ):
                    idx, exp, asy, qid, mdl, res = await fut
                    if res is None or res["score"] is None:
                        failed += 1
                        continue
                    ckpt.write(json.dumps({
                        "judge": judge_id, "experiment": exp, "assay": asy,
                        "question_id": qid, "model": mdl, "score": res["score"],
                        "n_claims": res["n_claims"], "n_supported": res["n_supported"],
                        "n_unsupported": res["n_unsupported"], "claims": res["claims"],
                    }) + "\n")
                    ckpt.flush()
                    _merge(idx, exp, asy, qid, mdl, res)
                return failed

            try:
                n_failed = asyncio.run(_run_faith())
            finally:
                ckpt.close()

        scored = len(todo) - n_failed
        msg = f"Faithfulness: {len(done)} cached + {scored}/{len(todo)} newly scored"
        if n_failed:
            msg += f" — {n_failed} returned None (judge error / no claims; excluded)"
        print((style.WARNING if n_failed else style.SUCCESS)(msg))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    metrics_df = pd.DataFrame(metric_rows)
    metrics_path = ANALYSIS_DIR / f"tier3_metrics_{timestamp}.csv"
    metrics_df.to_csv(metrics_path, index=False)
    print(style.SUCCESS(f"Per-answer metrics → {metrics_path}"))

    if agreement_rows:
        agreement_path = ANALYSIS_DIR / f"tier3_agreement_{timestamp}.csv"
        pd.DataFrame(agreement_rows).to_csv(agreement_path, index=False)
        print(style.SUCCESS(f"Cross-model agreement → {agreement_path}"))

    if faith_detail:
        detail_path = ANALYSIS_DIR / f"tier3_faithfulness_detail_{timestamp}.csv"
        pd.DataFrame(
            faith_detail,
            columns=["experiment", "assay", "question_id", "model",
                     "verdict", "statement", "reason"],
        ).to_csv(detail_path, index=False)
        print(style.SUCCESS(f"Faithfulness per-claim detail → {detail_path}"))

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
        # RAGAS faithfulness is scored over NON-trivial answers (answered + hedged),
        # a superset of ``answered``; aggregate it over ``grp``, not ``answered``.
        faith_num = pd.to_numeric(
            grp["faithfulness_score"], errors="coerce"
        ).dropna()
        agree_raw = pd.to_numeric(grp["model_agreement_raw"], errors="coerce").dropna()
        agree_norm = pd.to_numeric(
            grp["model_agreement_normalized"], errors="coerce"
        ).dropna()
        verbatim_vals = pd.to_numeric(grp["quotes_verbatim"], errors="coerce").dropna()
        # Spread + cluster-bootstrap-by-assay 95% CI for the agreement means. ``n`` is
        # shared across raw/normalized (same participating questions).
        agree_n, agree_raw_sd, agree_raw_lo, agree_raw_hi = _dispersion(
            grp, "model_agreement_raw"
        )
        _, agree_norm_sd, agree_norm_lo, agree_norm_hi = _dispersion(
            grp, "model_agreement_normalized"
        )
        # Faithfulness is a scored subset (non-trivial answers): n/sd/CI over the
        # scored rows, cluster-bootstrap by assay (same machinery as agreement).
        faith_n, faith_sd, faith_lo, faith_hi = _dispersion(
            grp, "faithfulness_score"
        )
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
                "faithfulness_n": faith_n,
                "faithfulness_sd": faith_sd,
                "faithfulness_ci_lo": faith_lo,
                "faithfulness_ci_hi": faith_hi,
                "agreement_n": agree_n,
                "mean_agreement_raw": round(float(agree_raw.mean()), 4)
                if len(agree_raw) else None,
                "agreement_raw_sd": agree_raw_sd,
                "agreement_raw_ci_lo": agree_raw_lo,
                "agreement_raw_ci_hi": agree_raw_hi,
                "mean_agreement_normalized": round(float(agree_norm.mean()), 4)
                if len(agree_norm) else None,
                "agreement_norm_sd": agree_norm_sd,
                "agreement_norm_ci_lo": agree_norm_lo,
                "agreement_norm_ci_hi": agree_norm_hi,
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
