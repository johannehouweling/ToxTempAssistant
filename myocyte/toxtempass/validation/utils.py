import json
from pathlib import Path

import pandas as pd
from tqdm.auto import tqdm
from toxtempass import config
from django.db.models.query import QuerySet

from toxtempass.validation.embeddings import cosine_similarity, bert_score
import warnings

def has_answer_not_found(answer_text: str) -> bool:
    """Check if LLM was not able to find an Answer from the context in document."""
    return config.not_found_string in answer_text


def generate_comparison_csv(
    json_file: Path, answers: QuerySet, output_dir: Path, pdf_file: str
) -> None:
    """
    Generate a CSV comparing ground-truth answers with LLM-generated answers.

    :param data: Ground-truth data as a dictionary.
    :param answers: QuerySet of Answer objects.
    :param output_dir: Directory to save the CSV file.
    :param pdf_file: Name of the PDF file being processed.
    """
    # Load the ground-truth JSON file with error handling
    try:
        with json_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON from {json_file}: {e}") from e
    # 1. Build a mapping from question → ground-truth answer
    qa_list = extract_qa(data)
    gtruth_map = {item["question"]: item["answer"] for item in qa_list}
    gtruth_score_map = {item["question"]: item.get("answer_quality_score", "") for item in qa_list}
    gtruth_justification_map = {item["question"]: item.get("answer_quality_justification", "") for item in qa_list}

    # 2. Assemble one dict per answer
    rows = []
    for ans in answers:
        q_text = (
            ans.question.question_text
        )  # or ans.question.text, depending on your object
        llm_ans = ans.answer_text
        gtruth = gtruth_map.get(q_text, "")
        gtruth_score = gtruth_score_map.get(q_text, "")
        gtruth_justification = gtruth_justification_map.get(q_text, "")
        rows.append({
            "question": q_text,
            "gtruth_answer": gtruth,
            "gtruth_answer_quality_score": gtruth_score,
            "gtruth_answer_quality_justification": gtruth_justification,
            "llm_answer": llm_ans
        })

    # 3. Create DataFrame
    df = pd.DataFrame(rows)
    # Replace any missing answers with empty strings to avoid NoneType errors
    df['gtruth_answer'] = df['gtruth_answer'].fillna('')
    df['llm_answer'] = df['llm_answer'].fillna('')

    # 4 append cosine similarity
    tqdm.pandas(desc="Calculating cosine similarity", position=1, leave=True)
    df["cos_similarity"] = df.progress_apply(
        lambda row: cosine_similarity(row["gtruth_answer"], row["llm_answer"]),
        axis=1,
    )
    # Compute BERT scores and append as separate columns
    warnings.filterwarnings("ignore", message="Empty candidate sentence detected") # Ignore warnings from bert_score
    tqdm.pandas(desc="Calculating BERT scores", position=1, leave=True)
    scores = df.progress_apply(
        lambda row: bert_score(row['gtruth_answer'], row['llm_answer']),
        axis=1,
    ).tolist()
    warnings.resetwarnings()
    scores_df = pd.DataFrame(
        scores,
        columns=["bert_precision", "bert_recall", "bert_f1"],
        index=df.index
    )
    df = pd.concat([df, scores_df], axis=1)

    # Save DataFrame to CSV
    output_file = output_dir / f"tier1_comparison_{Path(pdf_file).stem}_{model}.csv"
    df.to_csv(output_file, index=False)
    print(f"Comparison CSV saved to {output_file}")
    return df


def extract_qa(data: dict) -> list[dict]:
    """
    Recursively search through nested dicts and lists, extracting
    all dicts that have both 'question' and 'answer' keys.

    :param data: The input data (dict, list, or any).
    :return: A list of dicts each containing 'question' and 'answer'.
    """
    results: list[dict] = []

    def _recurse(obj: dict):
        # If it's a dict, check for keys and dive deeper
        if isinstance(obj, dict):
            if "question" in obj and "answer" in obj:
                results.append(obj)
            for value in obj.values():
                _recurse(value)

        # If it's a list or tuple, recurse into each item
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                _recurse(item)
        # Otherwise, nothing to do (primitives, etc.)

    _recurse(data)
    return results
