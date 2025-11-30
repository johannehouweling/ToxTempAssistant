from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from myocyte.settings import BASE_DIR

base_dir = Path(BASE_DIR / "toxtempass/evaluation/positive_control/input_files/processed")


def flatten_toxjson(
    data: Dict[str, Any], source_file: Optional[str] = None
) -> pd.DataFrame:
    """Flatten the ToxTemp-style JSON into a tabular DataFrame.

    Rows include both main subsection questions and nested subquestions.
     Columns:
       - source_file, reference
       - section_index, section_title
       - subsection_index, subsection_title
       - is_subquestion, subquestion_index
       - parent_question (for subquestions)
       - question, answer
       - answer_quality_score, answer_quality_justification.
    """
    rows: List[Dict[str, Any]] = []
    ref = data.get("reference", "")

    for si, section in enumerate(data.get("sections", []), start=1):
        s_title = section.get("title", "")
        for ssi, sub in enumerate(section.get("subsections", []), start=1):
            base = {
                "source_file": source_file,
                "reference": ref,
                "section_index": si,
                "section_title": s_title,
                "subsection_index": ssi,
                "subsection_title": sub.get("title", ""),
            }

            # Main subsection Q/A
            rows.append(
                {
                    **base,
                    "is_subquestion": False,
                    "subquestion_index": None,
                    "parent_question": None,
                    "question": sub.get("question", ""),
                    "answer": sub.get("answer", ""),
                    "answer_quality_score": sub.get("answer_quality_score", ""),
                    "answer_quality_justification": sub.get(
                        "answer_quality_justification", ""
                    ),
                }
            )

            # Nested subquestions (if any)
            for qi, sq in enumerate(sub.get("subquestions", []), start=1):
                rows.append(
                    {
                        **base,
                        "is_subquestion": True,
                        "subquestion_index": qi,
                        "parent_question": sub.get("question", ""),
                        "question": sq.get("question", ""),
                        "answer": sq.get("answer", ""),
                        "answer_quality_score": sq.get("answer_quality_score", ""),
                        "answer_quality_justification": sq.get(
                            "answer_quality_justification", ""
                        ),
                    }
                )

    return pd.DataFrame(rows)


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def flatten_folder(folder: Path) -> pd.DataFrame:
    """Flatten all *.json files in a folder and concatenates the results.

    Adds 'source_file' to trace origin.
    """
    dfs: List[pd.DataFrame] = []
    for p in folder.glob("*.json"):
        data = load_json(p)
        df = flatten_toxjson(data, source_file=str(p))
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


# --- Usage examples ---

# 1) From a Python dict named `data` (your pasted JSON):
# df = flatten_toxjson(data)

# 2) From a single file:
# df = flatten_toxjson(load_json(Path("/path/to/file.json")), source_file="file.json")

# 3) From a folder of JSON files:
# df = flatten_folder(Path("/Users/johannehouweling/Desktop/ToxTempAssistant_Validation/Tier1/processed"))

# Inspect
# df.head()

df = flatten_folder(base_dir)
(df["answer"] != "").value_counts(True) * 616
df = df[df["answer"] != ""]
high = df[df["answer_quality_score"] == "High"]["answer_quality_score"].count()
medium = df[df["answer_quality_score"] == "Medium"]["answer_quality_score"].count()
low = df[df["answer_quality_score"] == "Low"]["answer_quality_score"].count()
high + medium + low
