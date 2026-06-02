"""Cross-model pairwise cosine similarity ("intermodelsim").

Given several models' answers to the *same* question, measure how much they agree
by averaging the cosine similarity of their answer embeddings over every unordered
model pair. High agreement is a reference-free proxy for a convergent, defensible
answer when no ground truth exists (Tier 3 real-world evaluation).

Embeds each answer once (via the shared ``embeddings`` client from
``cosine_similarities``) and reuses the vectors for all pairs — cheaper than
calling ``cosine_similarity`` per pair, which re-embeds both texts each time.
"""

from itertools import combinations

import numpy as np

from toxtempass.evaluation.post_processing.cosine_similarities import embeddings


def pairwise_cosine_breakdown(
    answers_by_model: dict[str, str],
) -> tuple[float | None, dict[str, float]]:
    """Cross-model agreement for one question.

    Args:
        answers_by_model: ``{model_name: answer_text}``. Empty/blank answers are
            dropped before comparison.

    Returns:
        ``(overall_mean, per_model_mean)`` where ``overall_mean`` is the mean
        cosine over all model pairs and ``per_model_mean`` maps each model to its
        mean cosine against the other models. Returns ``(None, {})`` when fewer
        than two non-empty answers are present (no pair to compare).

    """
    items = [(m, a) for m, a in answers_by_model.items() if a and a.strip()]
    if len(items) < 2:
        return None, {}

    names = [m for m, _ in items]
    vectors = [np.asarray(v) for v in embeddings.embed_documents([a for _, a in items])]
    norms = [np.linalg.norm(v) for v in vectors]
    n = len(vectors)

    sim = [[0.0] * n for _ in range(n)]
    for i, j in combinations(range(n), 2):
        denom = norms[i] * norms[j]
        c = float(np.dot(vectors[i], vectors[j]) / denom) if denom else 0.0
        sim[i][j] = sim[j][i] = c

    overall = float(np.mean([sim[i][j] for i, j in combinations(range(n), 2)]))
    per_model = {
        names[i]: float(np.mean([sim[i][j] for j in range(n) if j != i]))
        for i in range(n)
    }
    return overall, per_model


def mean_pairwise_cosine(answers_by_model: dict[str, str]) -> float | None:
    """Mean cosine over all model pairs for one question (or ``None`` if < 2)."""
    overall, _ = pairwise_cosine_breakdown(answers_by_model)
    return overall
