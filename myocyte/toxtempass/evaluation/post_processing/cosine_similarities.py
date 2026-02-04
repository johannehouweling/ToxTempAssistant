import numpy as np
from bert_score import score as bert_score_score
from langchain_openai import OpenAIEmbeddings

from toxtempass import LLM_API_KEY, config

embeddings = OpenAIEmbeddings(
    model=config._validation_embedding_model,
    base_url=config.url,
    default_headers=config.extra_headers,
    openai_api_key=LLM_API_KEY,
    chunk_size=1024,
)


def cosine_similarity(text1: str, text2: str) -> float:
    """Compute the cosine similarity between two texts using their embeddings."""
    # embed both texts in one call for efficiency
    vec1, vec2 = embeddings.embed_documents([text1, text2])
    # compute cosine similarity
    return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))


def bert_score(text1: str, text2: str) -> tuple[float, float, float]:
    """Compute the BERTScore F1 between two texts."""
    # compute BERTScore (using rescaling to baseline)
    P, R, F1 = bert_score_score(
        [text1],
        [text2],
        lang="en",
        model_type=config._validation_bert_score_model,
        rescale_with_baseline=True,
    )
    return float(P[0]), float(R[0]), float(F1[0])
