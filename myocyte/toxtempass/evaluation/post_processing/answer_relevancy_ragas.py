"""RAGAS-based answer (response) relevancy for the Tier 3 (real-world) evaluation.

Response relevancy asks the *inverse* of correctness: it never compares the answer to a
ground truth. Instead the judge LLM reverse-generates ``strictness`` questions *from the
answer*, embeds each generated question and the original question, and scores the mean
cosine similarity — a relevant answer lets you reconstruct the question that was asked.
A binary ``noncommittal`` flag (evasive / "not specified" answers) gates the score to 0
when **every** generated question is flagged (RAGAS uses ``np.all``, not ``np.any``).

Unlike faithfulness, this needs BOTH a judge LLM (question generation + noncommittal) AND
an embeddings model (the cosine). Reference-free; the answer's context is NOT used by the
0.4.x metric (required columns are ``user_input`` + ``response`` only).

Uses an injected judge LLM and embeddings client (LangChain objects, e.g. from
``resolve_eval_llm`` / ``embeddings.get_client``) wrapped for RAGAS.
"""

import asyncio
import logging
import random

logger = logging.getLogger("llm")

# Substrings marking a transient (retryable) judge error vs a deterministic
# parse/validation failure (which should fail fast, no retry). Mirrors faithfulness_ragas.
_TRANSIENT_MARKERS = (
    "rate limit", "ratelimit", "429", "quota", "overloaded", "timeout",
    "timed out", "temporarily", "unavailable", "503", "502", "500",
    "connection", "reset",
)
# Permanent failures (billing/credits) override the transient check so a partial run
# stops fast when credits run out instead of retrying every remaining task.
_PERMANENT_MARKERS = ("credit", "depleted", "billing", "prepayment", "insufficient")


def make_relevancy_metric(
    judge_llm: object, embeddings: object, strictness: int = 3
) -> object:
    """Build a RAGAS ``ResponseRelevancy`` metric bound to a judge LLM + embeddings.

    ``strictness`` is the number of questions reverse-generated per answer (RAGAS
    recommends 3-5). Imported lazily so the heavy RAGAS import only happens on use.
    """
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import ResponseRelevancy

    # bypass_n=True makes RAGAS issue ``strictness`` SEPARATE single-completion calls
    # instead of one n-completion request. Required for providers whose OpenAI-compat
    # endpoint rejects n>1 — e.g. Gemini returns 400 "Multiple candidates is not enabled
    # for this model". Costs strictness× the calls, but works on every provider.
    return ResponseRelevancy(
        llm=LangchainLLMWrapper(judge_llm, bypass_n=True),
        embeddings=LangchainEmbeddingsWrapper(embeddings),
        strictness=strictness,
    )


async def _aexplain(metric: object, question: str, response: str) -> dict:
    """Replicate RAGAS ``_ascore`` but KEEP the generated questions + noncommittal flag.

    One LLM call (the question generation); the embedding cosine is sync inside RAGAS, so
    it is pushed to a worker thread to avoid stalling the shared event loop.
    """
    import numpy as np
    from ragas.metrics._answer_relevance import ResponseRelevanceInput

    prompt_input = ResponseRelevanceInput(response=str(response))
    answers = await metric.question_generation.generate_multiple(
        data=prompt_input, llm=metric.llm, callbacks=None, n=metric.strictness
    )
    gen_questions = [a.question for a in answers]
    noncommittal = bool(np.all([a.noncommittal for a in answers]))
    if all(q == "" for q in gen_questions):
        return {"score": None, "noncommittal": noncommittal,
                "n_questions": 0, "questions": []}

    # calculate_similarity hits the embeddings endpoint synchronously — off the loop.
    cosine = await asyncio.to_thread(
        metric.calculate_similarity, str(question), gen_questions
    )
    cosine = [float(c) for c in cosine]
    score = (sum(cosine) / len(cosine)) * int(not noncommittal)
    return {
        "score": float(score),
        "noncommittal": noncommittal,
        "n_questions": len(gen_questions),
        "questions": [
            {"question": q, "cosine": c} for q, c in zip(gen_questions, cosine)
        ],
    }


async def relevancy_aexplain(
    question: str,
    answer: str,
    metric: object,
    max_retries: int = 4,
    base_delay: float = 2.0,
) -> dict | None:
    """Async response relevancy WITH the per-question breakdown (one LLM call).

    The async form enables true concurrency: a caller runs many of these in ONE event loop
    (``asyncio.gather`` + a semaphore) so the LLM I/O overlaps. Returns
    ``{score, noncommittal, n_questions, questions}`` (``questions`` =
    ``{question, cosine}``); the empty-answer breakdown (score 0.0) for a blank answer;
    ``None`` after exhausting retries or when the judge returns no parseable question.
    Transient judge errors (rate limits, timeouts, 5xx, connection) retry with backoff +
    jitter; deterministic/billing errors fail fast.
    """
    if not answer or not str(answer).strip():
        return {"score": 0.0, "noncommittal": True, "n_questions": 0, "questions": []}

    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await _aexplain(metric, question, answer)
        except Exception as exc:  # network/LLM/parse — decide retry below
            last_exc = exc
            msg = str(exc).lower()
            permanent = any(m in msg for m in _PERMANENT_MARKERS)
            transient = (not permanent) and any(m in msg for m in _TRANSIENT_MARKERS)
            if not transient or attempt == max_retries:
                break
            delay = base_delay * 2 ** attempt + random.uniform(0, base_delay)  # noqa: S311
            logger.warning(
                "RAGAS relevancy transient error (attempt %d/%d); retry in %.1fs: %s",
                attempt + 1, max_retries, delay, exc,
            )
            await asyncio.sleep(delay)
    logger.warning(
        "RAGAS relevancy failed for %r: %s", (question or "")[:60], last_exc
    )
    return None


def relevancy_explain(
    question: str,
    answer: str,
    metric: object,
    max_retries: int = 4,
    base_delay: float = 2.0,
) -> dict | None:
    """Sync wrapper over ``relevancy_aexplain`` (one-off / standalone use)."""
    return asyncio.run(
        relevancy_aexplain(question, answer, metric, max_retries, base_delay)
    )
