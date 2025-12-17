"""RAGAS-based faithfulness evaluation for ToxTempAssistant.

This module provides faithfulness verification using the RAGAS framework to address
reviewer concerns about hallucinations (#25, #60) in the manuscript evaluation.

Faithfulness measures whether LLM-generated answers are grounded in the provided
evidence/context by decomposing answers into atomic claims and verifying each
claim against the source documents.
"""

import asyncio
import logging
from typing import Any

import pandas as pd
from ragas import SingleTurnSample, evaluate
from ragas.metrics import Faithfulness
from tqdm import tqdm

logger = logging.getLogger(__name__)


async def faithfulness_score_async(
    question: str,
    answer: str,
    evidence: str,
    model: str = "gpt-4o-mini",
) -> dict[str, Any]:
    """Compute RAGAS faithfulness score for a single question/answer pair.

    Args:
        question: The ToxTemp question text
        answer: The LLM-generated answer
        evidence: The evidence/context from source documents
        model: The OpenAI model to use for faithfulness evaluation

    Returns:
        Dictionary containing:
            - faithfulness_score: float (0.0-1.0)
            - faithfulness_statements: int (number of claims decomposed)
            - faithfulness_reason: str (explanation from RAGAS)
    """
    try:
        # Create a SingleTurnSample for RAGAS
        sample = SingleTurnSample(
            user_input=question,
            response=answer,
            retrieved_contexts=[evidence] if evidence else [],
        )

        # Initialize Faithfulness metric with specified model
        faithfulness = Faithfulness(llm=model)

        # Evaluate using RAGAS
        result = await evaluate(
            dataset=[sample],
            metrics=[faithfulness],
        )

        # Extract results
        score = result["faithfulness"]
        
        # Get additional details if available
        statements = getattr(result, "faithfulness_statements", 0)
        reason = getattr(result, "faithfulness_reason", "")

        return {
            "faithfulness_score": float(score),
            "faithfulness_statements": int(statements) if statements else 0,
            "faithfulness_reason": str(reason) if reason else "",
        }

    except Exception as e:
        logger.error(f"Error computing faithfulness: {e}")
        return {
            "faithfulness_score": 0.0,
            "faithfulness_statements": 0,
            "faithfulness_reason": f"Error: {str(e)}",
        }


def faithfulness_score(
    question: str,
    answer: str,
    evidence: str,
    model: str = "gpt-4o-mini",
) -> dict[str, Any]:
    """Synchronous wrapper for faithfulness_score_async.

    Args:
        question: The ToxTemp question text
        answer: The LLM-generated answer
        evidence: The evidence/context from source documents
        model: The OpenAI model to use for faithfulness evaluation

    Returns:
        Dictionary containing faithfulness metrics
    """
    return asyncio.run(
        faithfulness_score_async(question, answer, evidence, model)
    )


def add_faithfulness_columns(
    df: pd.DataFrame,
    model: str = "gpt-4o-mini",
    question_col: str = "question",
    answer_col: str = "llm_answer",
    evidence_col: str = "evidence",
) -> pd.DataFrame:
    """Add faithfulness evaluation columns to a DataFrame.

    Args:
        df: DataFrame with evaluation results
        model: OpenAI model for faithfulness evaluation (default: gpt-4o-mini)
        question_col: Column name for questions
        answer_col: Column name for LLM answers
        evidence_col: Column name for evidence/context

    Returns:
        DataFrame with added faithfulness columns:
            - faithfulness_score
            - faithfulness_statements
            - faithfulness_reason
    """
    logger.info(f"Computing faithfulness for {len(df)} rows using {model}")

    # Initialize progress bar
    tqdm.pandas(desc="Computing faithfulness")

    # Apply faithfulness scoring to each row
    results = df.progress_apply(
        lambda row: faithfulness_score(
            question=row[question_col],
            answer=row[answer_col],
            evidence=row.get(evidence_col, ""),
            model=model,
        ),
        axis=1,
    )

    # Extract individual components into separate columns
    df["faithfulness_score"] = results.apply(lambda x: x["faithfulness_score"])
    df["faithfulness_statements"] = results.apply(
        lambda x: x["faithfulness_statements"]
    )
    df["faithfulness_reason"] = results.apply(lambda x: x["faithfulness_reason"])

    logger.info(
        f"Faithfulness computation complete. Mean score: {df['faithfulness_score'].mean():.3f}"
    )

    return df


def summarize_faithfulness(df: pd.DataFrame) -> dict[str, Any]:
    """Generate summary statistics for faithfulness scores.

    Args:
        df: DataFrame with faithfulness_score column

    Returns:
        Dictionary with summary statistics:
            - mean, median, std, min, max
            - high_count (>=0.95), medium_count (0.75-0.94), low_count (<0.75)
            - high_pct, medium_pct, low_pct
    """
    if "faithfulness_score" not in df.columns:
        logger.warning("No faithfulness_score column found in DataFrame")
        return {}

    scores = df["faithfulness_score"]

    # Basic statistics
    summary = {
        "mean": float(scores.mean()),
        "median": float(scores.median()),
        "std": float(scores.std()),
        "min": float(scores.min()),
        "max": float(scores.max()),
    }

    # Categorize scores
    high = (scores >= 0.95).sum()
    medium = ((scores >= 0.75) & (scores < 0.95)).sum()
    low = (scores < 0.75).sum()
    total = len(scores)

    summary.update(
        {
            "high_count": int(high),
            "medium_count": int(medium),
            "low_count": int(low),
            "high_pct": float(high / total * 100) if total > 0 else 0.0,
            "medium_pct": float(medium / total * 100) if total > 0 else 0.0,
            "low_pct": float(low / total * 100) if total > 0 else 0.0,
        }
    )

    logger.info(
        f"Faithfulness summary: mean={summary['mean']:.3f}, "
        f"high={summary['high_pct']:.1f}%, "
        f"medium={summary['medium_pct']:.1f}%, "
        f"low={summary['low_pct']:.1f}%"
    )

    return summary
