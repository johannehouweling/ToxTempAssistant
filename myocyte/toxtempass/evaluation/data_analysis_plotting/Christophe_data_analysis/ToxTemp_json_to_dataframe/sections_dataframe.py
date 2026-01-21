# converting the ToxTemp_v1.json to a dataframe in order to use in for data analysis based on sections

#imports
import pandas as pd
import json
from pathlib import Path

# Configuration (put paths, constants) at the top
OUTPUT_CSV = Path("myocyte/toxtempass/evaluation/data_analysis_plotting/Christophe_data_analysis/ToxTemp_json_to_dataframe/ToxTemp_question_df.csv")

#TTA question file location
TTAquestions_path = 'myocyte/ToxTemp_v1.json'

# reading the json
def ToxTemp_questions_df(TTAquestions_path):
    with open(TTAquestions_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    rows = []

    for section in data.get("sections", []):
        section_title = section.get("title")

        for subsection in section.get("subsections", []):
            subsection_title = subsection.get("title")

            # Main question
            if "question" in subsection:
                rows.append({
                    "section": section_title,
                    "subsection": subsection_title,
                    "question": subsection.get("question")
                })

            # Subquestions
            for sq in subsection.get("subquestions", []):
                rows.append({
                    "section": section_title,
                    "subsection": subsection_title,
                    "question": sq.get("question")
                })

    return pd.DataFrame(rows)

# making the dataframe
df = ToxTemp_questions_df(TTAquestions_path)
print(df.head())

# making temporary index --> needs to be adjusted when section dataframe is added
df = df.reset_index(drop=True)
df.index = df.index + 1
df.index.name = "Question_ID"


#save DataFrame as csv
OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True) # to avoid folder not found errors
df.to_csv(OUTPUT_CSV)
print(f"Saved dataframe to: {OUTPUT_CSV}")