# Create a questions DataFrame/CSV from the toxtemp JSON file.

#imports
import json
import pandas as pd
from pathlib import Path

# toxtem question file location
TTAQUESTIONS_PATH = Path("myocyte/ToxTemp_v1.json")
OUTPUT_PATH = Path("myocyte/toxtempass/evaluation/data_analysis_plotting/christophe_data_analysis/enriched/sections/dataframes/ToxTemp_questions.csv")

## Load toxtemp questions JSON and return a DataFrame of questions.
def toxtemp_questions_df(json_path: Path) -> pd.DataFrame:
    ### Accept a JSON path so this function can be reused with other files
    with json_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    rows = []

    for section in data.get("sections", []):
        section_title = section.get("title")
        for subsection in section.get("subsections", []):
            subsection_title = subsection.get("title")
            if "question" in subsection:
                rows.append(
                    {
                        "section": section_title,
                        "subsection": subsection_title,
                        "question": subsection.get("question")
                    }
                )
            for sq in subsection.get("subquestions", []):
                rows.append(
                    {
                        "section": section_title,
                        "subsection": subsection_title,
                        "question": sq.get("question")
                    }
                )
    # Starting the index at 1
    df = pd.DataFrame(rows).reset_index(drop=True)
    df.index = df.index + 1
    df.index.name = "Question_ID"
    # Adding a column with only section number
    df["section#"] = (
        df["section"]
        .fillna("")
        .astype(str)
        .str.split()
        .str[:1]
        .str.join(" ")
    )
    return pd.DataFrame(df)

def main() -> None:
    # This function runs the steps of the script in order.
    # Putting those steps here means you can import this file in a notebook
    # withoud it automatically reading files or writing a CSV.
    df = toxtemp_questions_df(TTAQUESTIONS_PATH)
    print(df.head())
    output_csv = OUTPUT_PATH.with_name(
        f"{TTAQUESTIONS_PATH.stem}_questions.csv"
    )
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv)
    print(f"Saved dataframe to: {output_csv}")

# Only run this block when the file is executed directly (not when imported).
if __name__ == "__main__":
    main()