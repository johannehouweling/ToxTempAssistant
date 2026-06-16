"""Tier-1 adapter: cosine similarity of an answer against a reference answer.

Thin shim over the modular layers:
  * ``embeddings.py``  -- provider + caching (where vectors come from)
  * ``similarity.py``  -- pure cosine math

The public surface is unchanged for back-compat:
  * ``cosine_similarity(text1, text2)`` -- used by ``post_processing/utils.py``.
  * ``embeddings``                      -- the shared client (lazily built).
"""

from __future__ import annotations

from toxtempass.evaluation.post_processing import embeddings as _emb
from toxtempass.evaluation.post_processing import similarity as _sim


def __getattr__(name):  # back-compat: ``from cosine_similarities import embeddings``
    if name == "embeddings":
        return _emb.get_client()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def cosine_similarity(text1: str, text2: str) -> float:
    """Cosine similarity between two texts (embedded via the shared cached client)."""
    vecs = _emb.embed_texts([text1, text2])
    return _sim.cosine(vecs[0], vecs[1])
