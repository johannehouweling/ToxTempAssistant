"""Tier-3 adapter: cross-model pairwise cosine agreement ("intermodelsim").

Given several models' answers to the *same* question, measure how much they agree by
averaging the cosine similarity of their answer embeddings over every unordered model
pair. High agreement is a reference-free proxy for a convergent, defensible answer when
no ground truth exists.

Thin shim over the modular layers:
  * ``embeddings.embed_texts`` -- embeds each answer once (cached/memoised) and reuses
    the vectors for all pairs.
  * ``similarity``             -- pure cosine matrix + pairwise/per-item means.

Public surface unchanged: ``pairwise_cosine_breakdown`` and ``mean_pairwise_cosine``.
"""

from __future__ import annotations

import numpy as np

from toxtempass.evaluation.post_processing import embeddings as _emb
from toxtempass.evaluation.post_processing import similarity as _sim


def pairwise_cosine_breakdown(
    answers_by_model: dict[str, str],
) -> tuple[float | None, dict[str, float]]:
    """Cross-model agreement for one question.

    Args:
        answers_by_model: ``{model_name: answer_text}``. Empty/blank answers are
            dropped before comparison.

    Returns:
        ``(overall_mean, per_model_mean)`` where ``overall_mean`` is the mean cosine
        over all model pairs and ``per_model_mean`` maps each model to its mean cosine
        against the other models. Returns ``(None, {})`` when fewer than two non-empty
        answers are present (no pair to compare).
    """
    items = [(m, a) for m, a in answers_by_model.items() if a and a.strip()]
    if len(items) < 2:
        return None, {}

    names = [m for m, _ in items]
    vectors = _emb.embed_texts([a for _, a in items])
    sim = _sim.cosine_matrix(vectors)

    overall = _sim.pairwise_mean(sim)
    per_item = _sim.per_item_means(sim)
    per_model = {names[i]: float(per_item[i]) for i in range(len(names))}
    return overall, per_model


def mean_pairwise_cosine(answers_by_model: dict[str, str]) -> float | None:
    """Mean cosine over all model pairs for one question (or ``None`` if < 2)."""
    overall, _ = pairwise_cosine_breakdown(answers_by_model)
    return overall


def pairwise_cosine_from_vectors(
    vectors_by_model: dict[str, np.ndarray],
) -> tuple[float | None, dict[str, float]]:
    """Cross-model agreement for one question from PRECOMPUTED vectors.

    Like ``pairwise_cosine_breakdown`` but takes ``{model_name: vector}`` (e.g. loaded
    from the embedding cache) instead of text, so no embedding call happens. Models with
    a ``None``/empty vector are dropped. Returns ``(overall_mean, per_model_mean)`` as
    above, or ``(None, {})`` when fewer than two vectors remain.
    """
    items = [(m, v) for m, v in vectors_by_model.items() if v is not None and len(v)]
    if len(items) < 2:
        return None, {}

    names = [m for m, _ in items]
    vectors = np.stack([np.asarray(v, dtype=float) for _, v in items])
    sim = _sim.cosine_matrix(vectors)

    overall = _sim.pairwise_mean(sim)
    per_item = _sim.per_item_means(sim)
    per_model = {names[i]: float(per_item[i]) for i in range(len(names))}
    return overall, per_model
