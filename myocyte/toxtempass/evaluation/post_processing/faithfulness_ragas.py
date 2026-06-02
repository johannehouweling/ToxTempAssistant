"""RAGAS-based faithfulness for the Tier 3 (real-world) evaluation.

Faithfulness decomposes an answer into atomic claims and verifies each against the
provided context (NLI-style), returning a continuous 0-1 grounding score
(claims supported / total). This is a published, citable method — preferred over a
bespoke prompt for the manuscript evaluation.

Uses an injected judge LLM (a LangChain chat model, e.g. from ``resolve_eval_llm``)
wrapped for RAGAS. **No embeddings required** — faithfulness is LLM-only — so it
works even without an embedding deployment. Reference-free.
"""

import logging

logger = logging.getLogger("llm")


def make_faithfulness_metric(judge_llm: object) -> object:
    """Build a RAGAS ``Faithfulness`` metric bound to the given LangChain judge LLM.

    Imported lazily so the heavy RAGAS import only happens when faithfulness is used.
    """
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import Faithfulness

    return Faithfulness(llm=LangchainLLMWrapper(judge_llm))


def faithfulness_score(
    question: str, answer: str, context: str, metric: object
) -> float | None:
    """Return RAGAS faithfulness in ``[0, 1]`` for one (question, answer, context).

    1.0 = every claim in the answer is grounded in the context; 0.0 = none are.
    Returns ``0.0`` for an empty answer and ``None`` when there is no context to
    judge against or RAGAS errors (so callers can distinguish "ungrounded" from
    "not scored").
    """
    from ragas import SingleTurnSample

    if not answer or not str(answer).strip():
        return 0.0
    if not context or not str(context).strip():
        return None
    try:
        sample = SingleTurnSample(
            user_input=str(question),
            response=str(answer),
            retrieved_contexts=[str(context)],
        )
        return float(metric.single_turn_score(sample))
    except Exception as exc:  # pragma: no cover - defensive (network/LLM/parse)
        logger.warning(
            "RAGAS faithfulness failed for %r: %s", (question or "")[:60], exc
        )
        return None
