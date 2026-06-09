"""RAGAS-based faithfulness for the Tier 3 (real-world) evaluation.

Faithfulness decomposes an answer into atomic claims and verifies each against the
provided context (NLI-style), returning a continuous 0-1 grounding score
(claims supported / total). This is a published, citable method — preferred over a
bespoke prompt for the manuscript evaluation.

Uses an injected judge LLM (a LangChain chat model, e.g. from ``resolve_eval_llm``)
wrapped for RAGAS. **No embeddings required** — faithfulness is LLM-only — so it
works even without an embedding deployment. Reference-free.
"""

import asyncio
import logging
import random
import time

logger = logging.getLogger("llm")

# Substrings marking a transient (retryable) judge error vs a deterministic
# parse/validation failure (which should fail fast, no retry).
_TRANSIENT_MARKERS = (
    "rate limit", "ratelimit", "429", "quota", "overloaded", "timeout",
    "timed out", "temporarily", "unavailable", "503", "502", "500",
    "connection", "reset",
)
# Permanent failures (billing/credits) override the transient check so a partial run
# stops fast when credits run out instead of retrying every remaining task.
_PERMANENT_MARKERS = ("credit", "depleted", "billing", "prepayment", "insufficient")


def make_faithfulness_metric(judge_llm: object) -> object:
    """Build a RAGAS ``Faithfulness`` metric bound to the given LangChain judge LLM.

    Imported lazily so the heavy RAGAS import only happens when faithfulness is used.
    """
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import Faithfulness

    return Faithfulness(llm=LangchainLLMWrapper(judge_llm))


def faithfulness_score(
    question: str,
    answer: str,
    context: str,
    metric: object,
    max_retries: int = 4,
    base_delay: float = 2.0,
) -> float | None:
    """Return RAGAS faithfulness in ``[0, 1]`` for one (question, answer, context).

    1.0 = every claim in the answer is grounded in the context; 0.0 = none are.
    Returns ``0.0`` for an empty answer and ``None`` when there is no context to
    judge against or RAGAS still errors after retries (so callers can distinguish
    "ungrounded" from "not scored"). Transient judge errors (rate limits, timeouts,
    5xx) are retried with exponential backoff + jitter; deterministic errors fail fast.
    """
    from ragas import SingleTurnSample

    if not answer or not str(answer).strip():
        return 0.0
    if not context or not str(context).strip():
        return None

    sample = SingleTurnSample(
        user_input=str(question),
        response=str(answer),
        retrieved_contexts=[str(context)],
    )
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return float(metric.single_turn_score(sample))
        except Exception as exc:  # network/LLM/parse — decide retry below
            last_exc = exc
            msg = str(exc).lower()
            permanent = any(m in msg for m in _PERMANENT_MARKERS)
            transient = (not permanent) and any(m in msg for m in _TRANSIENT_MARKERS)
            if not transient or attempt == max_retries:
                break
            delay = base_delay * 2 ** attempt + random.uniform(0, base_delay)  # noqa: S311
            logger.warning(
                "RAGAS faithfulness transient error (attempt %d/%d); retry in %.1fs: %s",
                attempt + 1, max_retries, delay, exc,
            )
            time.sleep(delay)
    logger.warning(
        "RAGAS faithfulness failed for %r: %s", (question or "")[:60], last_exc
    )
    return None


async def _aexplain(metric: object, row: dict) -> dict:
    """Run RAGAS's two steps and KEEP the per-claim verdicts (claim/verdict/reason)."""
    sg = await metric._create_statements(row, None)
    statements = sg.statements
    if not statements:
        return {"score": None, "n_claims": 0, "n_supported": 0,
                "n_unsupported": 0, "claims": []}
    verdicts = await metric._create_verdicts(row, statements, None)
    claims = [
        {"statement": a.statement, "verdict": int(a.verdict), "reason": a.reason}
        for a in verdicts.statements
    ]
    n = len(claims)
    supported = sum(c["verdict"] for c in claims)
    return {
        "score": supported / n if n else None,
        "n_claims": n,
        "n_supported": supported,
        "n_unsupported": n - supported,
        "claims": claims,
    }


async def faithfulness_aexplain(
    question: str,
    answer: str,
    context: str,
    metric: object,
    max_retries: int = 4,
    base_delay: float = 2.0,
) -> dict | None:
    """Async faithfulness WITH the per-claim breakdown (same 2 LLM calls, no extra cost).

    The async form is what enables true concurrency: a caller runs many of these in ONE
    event loop (``asyncio.gather`` + a semaphore) so the LLM I/O actually overlaps —
    unlike ``asyncio.run`` per task, which serialises. Returns
    ``{score, n_claims, n_supported, n_unsupported, claims}`` (``claims`` =
    ``{statement, verdict (0/1), reason}``); the empty-answer breakdown (score 0.0) for a
    blank answer; ``None`` for no context or after exhausting retries. Transient judge
    errors (rate limits, timeouts, 5xx, connection) are retried with backoff + jitter.
    """
    if not answer or not str(answer).strip():
        return {"score": 0.0, "n_claims": 0, "n_supported": 0,
                "n_unsupported": 0, "claims": []}
    if not context or not str(context).strip():
        return None

    row = {
        "user_input": str(question),
        "response": str(answer),
        "retrieved_contexts": [str(context)],
    }
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await _aexplain(metric, row)
        except Exception as exc:  # network/LLM/parse — decide retry below
            last_exc = exc
            msg = str(exc).lower()
            permanent = any(m in msg for m in _PERMANENT_MARKERS)
            transient = (not permanent) and any(m in msg for m in _TRANSIENT_MARKERS)
            if not transient or attempt == max_retries:
                break
            delay = base_delay * 2 ** attempt + random.uniform(0, base_delay)  # noqa: S311
            logger.warning(
                "RAGAS faith_explain transient (attempt %d/%d); retry in %.1fs: %s",
                attempt + 1, max_retries, delay, exc,
            )
            await asyncio.sleep(delay)
    logger.warning(
        "RAGAS faithfulness_explain failed for %r: %s", (question or "")[:60], last_exc
    )
    return None


def faithfulness_explain(
    question: str,
    answer: str,
    context: str,
    metric: object,
    max_retries: int = 4,
    base_delay: float = 2.0,
) -> dict | None:
    """Sync wrapper over ``faithfulness_aexplain`` (one-off / standalone use)."""
    return asyncio.run(
        faithfulness_aexplain(question, answer, context, metric, max_retries, base_delay)
    )
