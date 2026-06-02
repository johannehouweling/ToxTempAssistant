import os

import numpy as np
from langchain_openai import OpenAIEmbeddings

from toxtempass import LLM_API_KEY, config

# Embeddings (used for cosine similarity in tier1 + tier3 cross-model agreement) go
# to OpenAI's own endpoint via OPENAI_API_KEY — the Azure Foundry endpoint in
# `config.url` does not serve `text-embedding-3-large`. Falls back to the legacy
# key if OPENAI_API_KEY is unset.
embeddings = OpenAIEmbeddings(
    model=config._validation_embedding_model,
    openai_api_key=os.getenv("OPENAI_API_KEY") or LLM_API_KEY,
    chunk_size=1024,
)


def cosine_similarity(text1: str, text2: str) -> float:
    """Compute the cosine similarity between two texts using their embeddings."""
    # embed both texts in one call for efficiency
    vec1, vec2 = embeddings.embed_documents([text1, text2])
    # compute cosine similarity
    return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))
