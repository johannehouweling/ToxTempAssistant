"""Embedding provider + caching layer (the single place vectors come from).

Separates "where vectors come from" from the similarity math (``similarity.py``) and
the use-case adapters (``cosine_similarities`` / ``pairwise_cosine_similarities``).

Three things live here:

  * ``get_client()``      -- lazily-built shared OpenAIEmbeddings client. Lazy so that
                             importing this module needs no credentials (the old
                             module built the client at import time).
  * ``embed_texts()``     -- embed a list of texts as an ``(n, dim)`` array, with an
                             in-process memo so duplicate texts in one run embed once.
                             If a persistent cache is registered, it is used too.
  * ``EmbeddingCache``    -- disk-backed store (vectors.npy + index.csv) keyed by a
                             SHA-1 of the text, for the deliberate "embed everything
                             once and persist" step. Reusable primitive; the richer
                             per-answer index (experiment/model/assay/question_id) is
                             written by the cache-building script that uses this.

By default ``embed_texts`` only memoises within a process (behaviour identical to the
old code, just no redundant calls). Persisting across runs is opt-in via
``set_persistent_cache`` so a normal analysis run never silently writes files.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

# ── provider ────────────────────────────────────────────────────────────────
_client = None


def get_client():
    """Return the shared embeddings client, building it on first use."""
    global _client
    if _client is None:
        import os

        from langchain_openai import OpenAIEmbeddings

        from toxtempass import LLM_API_KEY, config

        # Embeddings go to OpenAI's own endpoint (the Azure Foundry endpoint does not
        # serve text-embedding-3-large); fall back to the legacy key if unset.
        _client = OpenAIEmbeddings(
            model=config._validation_embedding_model,
            openai_api_key=os.getenv("OPENAI_API_KEY") or LLM_API_KEY,
            chunk_size=1024,
        )
    return _client


def __getattr__(name):  # PEP 562: lazy module-level ``embeddings`` for back-compat
    if name == "embeddings":
        return get_client()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ── hashing ───────────────────────────────────────────────────────────────────
def text_sha1(text: str) -> str:
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()


# ── in-process + optional persistent embedding ───────────────────────────────
_MEMO: dict[str, np.ndarray] = {}
_PERSISTENT: "EmbeddingCache | None" = None


def set_persistent_cache(cache: "EmbeddingCache | None") -> None:
    """Route ``embed_texts`` through a disk-backed cache (opt-in). Pass None to clear."""
    global _PERSISTENT
    _PERSISTENT = cache


def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed ``texts`` -> ``(len(texts), dim)`` float array, de-duplicating by content.

    Order is preserved. Identical strings embed once. If a persistent cache is set,
    misses are read from / written to it; otherwise only an in-process memo is used.
    """
    texts = [t if isinstance(t, str) else str(t) for t in texts]
    keys = [text_sha1(t) for t in texts]

    # Resolve which unique texts still need a live embedding call.
    need: dict[str, str] = {}
    for k, t in zip(keys, texts):
        if k in _MEMO:
            continue
        if _PERSISTENT is not None and k in _PERSISTENT:
            _MEMO[k] = _PERSISTENT[k]
            continue
        need[k] = t

    if need:
        uniq_keys = list(need)
        vecs = get_client().embed_documents([need[k] for k in uniq_keys])
        for k, v in zip(uniq_keys, vecs):
            arr = np.asarray(v, dtype=np.float32)
            _MEMO[k] = arr
            if _PERSISTENT is not None:
                _PERSISTENT.add(k, arr)

    return np.stack([_MEMO[k] for k in keys])


# ── persistent cache ──────────────────────────────────────────────────────────
class EmbeddingCache:
    """SHA-1-keyed vector store persisted as ``vectors.npy`` + ``index.csv``.

    Minimal primitive: maps text hash -> vector, deduplicating identical answers. The
    cache-building script layers the human-readable per-answer index
    (experiment/model/assay/question_id -> vec_row) on top of this.
    """

    def __init__(self, directory: str | Path):
        self.dir = Path(directory)
        self._keys: list[str] = []
        self._rows: dict[str, int] = {}
        self._vectors: list[np.ndarray] = []
        self.load()

    # mapping-style helpers so ``k in cache`` / ``cache[k]`` work
    def __contains__(self, key: str) -> bool:
        return key in self._rows

    def __getitem__(self, key: str) -> np.ndarray:
        return self._vectors[self._rows[key]]

    def __len__(self) -> int:
        return len(self._keys)

    def add(self, key: str, vector: np.ndarray) -> int:
        if key in self._rows:
            return self._rows[key]
        row = len(self._keys)
        self._keys.append(key)
        self._vectors.append(np.asarray(vector, dtype=np.float32))
        self._rows[key] = row
        return row

    def vec_row(self, key: str) -> int | None:
        return self._rows.get(key)

    def load(self) -> None:
        npy = self.dir / "vectors.npy"
        idx = self.dir / "index.csv"
        if npy.exists() and idx.exists():
            mat = np.load(npy)
            import csv

            with idx.open() as f:
                keys = [r["text_sha1"] for r in csv.DictReader(f)]
            self._keys = keys
            self._vectors = [mat[i] for i in range(len(keys))]
            self._rows = {k: i for i, k in enumerate(keys)}

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        np.save(self.dir / "vectors.npy", np.stack(self._vectors) if self._vectors
                else np.zeros((0, 0), dtype=np.float32))
        import csv

        with (self.dir / "index.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["vec_row", "text_sha1"])
            for i, k in enumerate(self._keys):
                w.writerow([i, k])
