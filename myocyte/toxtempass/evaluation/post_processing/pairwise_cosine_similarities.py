from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from myocyte.settings import PROJECT_ROOT

from toxtempass.evaluation.post_processing.cosine_similarities import (
    cosine_similarity,
    embeddings,
)

ROOT = PROJECT_ROOT
INPUT_CSV = ROOT / 'myocyte/toxtempass/evaluation/data_analysis_plotting/christophe_data_analysis/results/tables/completeness_tier3/v2_description/combined_doctype_summary_completeness_v2_+description.csv'
OUTPUT_DIR = ROOT / 'myocyte/toxtempass/evaluation/data_analysis_plotting/christophe_data_analysis/results/tables/tier3_cos_sim'
OUTPUT_CSV = OUTPUT_DIR / 'tier3_cos_sim_v2_vs_gpt4o_mini_temp0.csv'
SUMMARY_CSV = OUTPUT_DIR / 'tier3_cos_sim_v2_summary.csv'

REFERENCE_MODEL = 'gpt-4o-mini_temp0'
NOT_FOUND = 'Answer not found in documents.'
JOIN_KEYS = ['question', 'doc_name', 'assay', 'doc_type', 'Question_ID2', 'qID']

def load_input_data(input_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(input_csv)
    required = {'model', 'llm_answer', 'is_empty'}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f'Input CSV missing columns: {missing}')
    df = df.loc[~df['is_empty'] & (df['llm_answer'] != NOT_FOUND)]
    return df

def enrich_with_embeddings(df: pd.DataFrame,colname:str) -> pd.DataFrame:
    df[colname+"_embeddings"] = df[colname].apply(lambda x: embeddings.embed_documents([x])[0])
    return df

def pairwise_embeddings_by_model(df: pd.DataFrame) -> pd.DataFrame:
    # Ensure uniqueness key exists
    key_cols = ["model", "question", "assay"]
    
    # Optional: keep an id per row so you can trace pairs back
    dfx = df.reset_index(names="row_id")

    rows = []
    for (model, question, assay), g in dfx.groupby(key_cols, sort=False):
        # If you have exactly 1 row per group, there are no pairs
        if len(g) < 2:
            continue
        
        # Build unordered pairs i<j
        for (id_a, emb_a), (id_b, emb_b) in combinations(zip(g["row_id"], g["embeddings"]), 2):
            rows.append({
                "model": model,
                "question": question,
                "assay": assay,
                "row_id_a": id_a,
                "row_id_b": id_b,
                "embedding_a": emb_a,
                "embedding_b": emb_b,
            })

    return pd.DataFrame(rows)


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


# if __name__ == '__main__':
    df = load_input_data(INPUT_CSV)
    df_embedded = enrich_with_embeddings(df, 'llm_answer')
    pairs_df = pairwise_embeddings_by_model(df_embedded)
    A = np.stack(pairs_df["embeddings_A"].to_numpy())  # shape (n, d)
    B = np.stack(df["embeddings_B"].to_numpy())    # shape (n, d)

    # cosine similarity row-wise: sum(A*B)/(|A|*|B|)
    num = np.sum(A * B, axis=1)
    den = np.linalg.norm(A, axis=1) * np.linalg.norm(B, axis=1)
    pairs_df["cos_sim"] = num / den
    save_results(pairs_df, OUTPUT_CSV, SUMMARY_CSV)
