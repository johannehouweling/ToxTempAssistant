"""Unit tests for ``pairwise_cosine_from_vectors`` (cache-backed agreement).

Pure-vector math: no embedding calls, no API credentials, no Django needed beyond the
package import. Verifies the agreement number, the per-model breakdown, the <2 guard,
and that empty/None vectors are dropped.
"""

import numpy as np
import pytest

from toxtempass.evaluation.post_processing.pairwise_cosine_similarities import (
    pairwise_cosine_from_vectors,
)


def test_identical_vectors_full_agreement():
    v = np.ones(8)
    overall, per = pairwise_cosine_from_vectors({"a": v, "b": v, "c": v})
    assert overall == pytest.approx(1.0, abs=1e-9)
    assert all(abs(x - 1.0) < 1e-9 for x in per.values())


def test_outlier_has_lowest_agreement():
    a = np.array([1.0, 0.0, 0.0, 0.0])
    b = np.array([1.0, 0.0, 0.0, 0.0])
    c = np.array([0.0, 1.0, 0.0, 0.0])  # orthogonal outlier
    overall, per = pairwise_cosine_from_vectors({"a": a, "b": b, "c": c})
    assert per["c"] < per["a"]
    assert per["a"] == pytest.approx(per["b"], abs=1e-9)


def test_fewer_than_two_returns_none():
    assert pairwise_cosine_from_vectors({"a": np.ones(4)}) == (None, {})
    assert pairwise_cosine_from_vectors({}) == (None, {})


def test_empty_vectors_are_dropped():
    overall, per = pairwise_cosine_from_vectors(
        {"a": np.ones(4), "b": np.ones(4), "c": np.array([])}
    )
    assert "c" not in per
    assert overall is not None
