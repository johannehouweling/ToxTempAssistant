"""Pure cosine-similarity math on embedding vectors.

No embedding, no I/O, no project imports -- just numpy on already-computed vectors,
so it is fully unit-testable without API credentials (``python similarity.py``).

The embedding/caching layer lives in ``embeddings.py``; the Tier-1 / Tier-3 adapters
(``cosine_similarities.py`` / ``pairwise_cosine_similarities.py``) combine the two.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np


def cosine(u: np.ndarray, v: np.ndarray) -> float:
    """Cosine similarity of two vectors. Returns 0.0 if either has zero norm."""
    u = np.asarray(u, dtype=float)
    v = np.asarray(v, dtype=float)
    denom = float(np.linalg.norm(u) * np.linalg.norm(v))
    return float(np.dot(u, v) / denom) if denom else 0.0


def cosine_matrix(vectors: np.ndarray) -> np.ndarray:
    """(n, dim) -> (n, n) cosine-similarity matrix (diagonal = 1, zero-norm rows = 0)."""
    mat = np.asarray(vectors, dtype=float)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    safe = np.where(norms > 0, norms, 1.0)
    unit = mat / safe
    sim = unit @ unit.T
    zero = (norms.ravel() == 0)
    if zero.any():  # zero-norm rows similarity = 0 to everything
        sim[zero, :] = 0.0
        sim[:, zero] = 0.0
    return sim


def pairwise_mean(sim: np.ndarray) -> float | None:
    """Mean similarity over all unordered pairs. Returns None if fewer than 2 items."""
    sim = np.asarray(sim, dtype=float)
    n = sim.shape[0]
    if n < 2:
        return None
    return float(np.mean([sim[i, j] for i, j in combinations(range(n), 2)]))


def per_item_means(sim: np.ndarray) -> np.ndarray:
    """Each item's mean similarity against the *other* items (excludes the diagonal)."""
    sim = np.asarray(sim, dtype=float)
    n = sim.shape[0]
    if n < 2:
        return np.full(n, np.nan)
    return np.array(
        [float(np.mean([sim[i, j] for j in range(n) if j != i])) for i in range(n)]
    )


def _selftest() -> None:
    rng = np.random.default_rng(0)
    v = rng.normal(size=(4, 16))
    sim = cosine_matrix(v)
    assert np.allclose(np.diag(sim), 1.0, atol=1e-9), "diagonal must be 1"
    assert abs(sim[0, 1] - cosine(v[0], v[1])) < 1e-9, "matrix vs pairwise mismatch"
    # identical vectors -> mean 1.0; per-item all 1.0
    same = np.ones((3, 5))
    assert abs(pairwise_mean(cosine_matrix(same)) - 1.0) < 1e-9
    assert np.allclose(per_item_means(cosine_matrix(same)), 1.0)
    assert pairwise_mean(cosine_matrix(np.ones((1, 5)))) is None  # <2 items
    assert cosine(np.zeros(4), v[0]) == 0.0  # zero-norm guard
    print("similarity self-test OK")


if __name__ == "__main__":
    _selftest()
