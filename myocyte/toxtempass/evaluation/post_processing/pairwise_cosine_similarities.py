import os
from pathlib import Path

import numpy as np
import pandas as pd
from langchain_openai import OpenAIEmbeddings

ROOT = Path('/Users/johannehouweling/ToxTempAssistant')
INPUT_CSV = ROOT / 'myocyte/toxtempass/evaluation/data_analysis_plotting/christophe_data_analysis/results/tables/completeness_tier3/v2_description/combined_doctype_summary_completeness_v2_+description.csv'
OUTPUT_DIR = ROOT / 'myocyte/toxtempass/evaluation/data_analysis_plotting/christophe_data_analysis/results/tables/tier3_cos_sim'
OUTPUT_CSV = OUTPUT_DIR / 'tier3_cos_sim_v2_vs_gpt4o_mini_temp0.csv'
SUMMARY_CSV = OUTPUT_DIR / 'tier3_cos_sim_v2_summary.csv'

REFERENCE_MODEL = 'gpt-4o-mini_temp0'
NOT_FOUND = 'Answer not found in documents.'
JOIN_KEYS = ['question', 'doc_name', 'assay', 'doc_type', 'Question_ID2', 'qID']

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

if OPENAI_API_KEY:
    LLM_API_KEY = OPENAI_API_KEY
    LLM_ENDPOINT = 'https://api.openai.com/v1'
    EMBEDDING_MODEL = 'text-embedding-3-large'
    EXTRA_HEADERS = {}
elif OPENROUTER_API_KEY:
    LLM_API_KEY = OPENROUTER_API_KEY
    LLM_ENDPOINT = 'https://openrouter.ai/api/v1'
    EMBEDDING_MODEL = 'openai/text-embedding-3-large'
    EXTRA_HEADERS = {'HTTP-Referer': os.getenv('SITE_URL'), 'X-Title': 'ToxTempAssistant'}
else:
    raise RuntimeError('Set OPENAI_API_KEY or OPENROUTER_API_KEY in the environment.')

embeddings = OpenAIEmbeddings(
    model=EMBEDDING_MODEL,
    base_url=LLM_ENDPOINT,
    default_headers=EXTRA_HEADERS,
    openai_api_key=LLM_API_KEY,
    chunk_size=1024,
)


def cosine_similarity(text1: str, text2: str) -> float:
    vec1, vec2 = embeddings.embed_documents([text1, text2])
    return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))


def load_input_data(input_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(input_csv)
    required = {'model', 'llm_answer', 'is_empty'}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f'Input CSV missing columns: {missing}')
    df = df.loc[~df['is_empty'] & (df['llm_answer'] != NOT_FOUND)]
    return df


def build_reference_df(df: pd.DataFrame) -> pd.DataFrame:
    ref = df[df['model'] == REFERENCE_MODEL].copy()
    if ref.empty:
        raise ValueError(f'Reference model {REFERENCE_MODEL} not found in the input CSV.')
    return ref.rename(columns={'llm_answer': 'gtruth_answer'})


def merge_with_reference(df: pd.DataFrame, reference_df: pd.DataFrame) -> pd.DataFrame:
    candidate = df[df['model'] != REFERENCE_MODEL].copy()
    merged = candidate.merge(
        reference_df[JOIN_KEYS + ['gtruth_answer']],
        on=JOIN_KEYS,
        how='left',
        validate='many_to_one',
    )
    missing = merged['gtruth_answer'].isna().sum()
    if missing:
        print(f'Warning: {missing} rows have no matching {REFERENCE_MODEL} reference row.')
    return merged


def compute_cosine_similarities(df: pd.DataFrame) -> pd.DataFrame:
    df['llm_answer'] = df['llm_answer'].fillna('')
    df['gtruth_answer'] = df['gtruth_answer'].fillna('')

    def _row(row: pd.Series) -> float:
        if not row['gtruth_answer'] or not row['llm_answer']:
            return float('nan')
        return cosine_similarity(row['gtruth_answer'], row['llm_answer'])

    df['cos_similarity_to_gpt4o'] = df.apply(_row, axis=1)
    return df


def save_results(df: pd.DataFrame, output_csv: Path, summary_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False)

    summary = (
        df.groupby('model')['cos_similarity_to_gpt4o']
        .agg(mean='mean', median='median', std='std', count='count')
        .reset_index()
    )
    summary.to_csv(summary_csv, index=False)

    print(f'Saved cosine similarity comparison to: {output_csv}')
    print(f'Saved per-model summary to:           {summary_csv}')


if __name__ == '__main__':
    data = load_input_data(INPUT_CSV)
    reference = build_reference_df(data)
    merged = merge_with_reference(data, reference)
    result = compute_cosine_similarities(merged)
    save_results(result, OUTPUT_CSV, SUMMARY_CSV)
