# Data exploration of the answer_frequency of 
# o3-mini, gpt-4o-mini, gpt-4.1-nano and gpt-5-mini

# Imports
import pandas as pd
from pathlib import Path
import glob
import plotly.express as px

# Paths and constants
BASE_DIR = Path('myocyte/toxtempass/evaluation/positive_control/output')
OUTPUT_CSV = Path('myocyte/toxtempass/evaluation/data_analysis_plotting/christophe_data_analysis/results/tables/answer_frequency_positive_controls/summary_answer_frequency.csv')
QUESTION_PATH = Path('myocyte/toxtempass/evaluation/data_analysis_plotting/christophe_data_analysis/enriched/sections/dataframes/ToxTemp_v1_questions_short_section.csv')
NOT_FOUND_STRING = "Answer not found in documents."
CURRENT_LOC = Path('myocyte/toxtempass/evaluation/data_analysis_plotting/christophe_data_analysis/scripts/answer_frequency/summary.py')
#
#  read section DataFrame
question_df = pd.read_csv(QUESTION_PATH)
question_df.set_index('Question_ID', inplace=True)

# read csv & create Dataframe of positive control output
csv_files = sorted(BASE_DIR.glob("*/*.csv"))
if not csv_files:
    raise FileNotFoundError(f"No CSV files found in: {BASE_DIR}")

df = []
for file in csv_files:
    df_output = pd.read_csv(file)
    df_output["source_file"] = file.name
    df_output["model"] = file.parent.name
    df.append(df_output)

combined_output = pd.concat(df)

# remove the rows which have no ground truth
with_gtruth_output = combined_output.dropna(subset=['gtruth_answer']) #rows: 2464 -> 2182

# add a column giving a value of 1 to answered questions and 0 to unanswered questions
with_gtruth_output["answer_given"] = (
    ~with_gtruth_output['llm_answer']
    .str.contains(NOT_FOUND_STRING, regex=False)
    ).astype(int)

# create an avarage of answered/unanswered & cosine similarity per model
average_df = with_gtruth_output.groupby(["question", "model"],as_index=False)[["answer_given", "cos_similarity"]].mean() # -> 307 rows

# adding a column classifying ability to answer low, medium, high
bins = [0, 0.4, 0.7, 1]
labels = ["low", "medium", "high"]

average_df["answer_ability"] = pd.cut(
    average_df["answer_given"],
    bins=bins,
    labels=labels,
    include_lowest=True
)

# add column classifying cosine similarity, so we can compare answerability & cosine similarity

# merge section & ouput DataFrames
summary_df = question_df.merge(average_df, on=["question"]) #now there are 304 rows??

# making temporary index --> needs to be adjusted when section dataframe is added
summary_df = summary_df.reset_index(drop=True)
summary_df.index = summary_df.index + 1

# save DataFrame as csv
OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
summary_df.to_csv(OUTPUT_CSV)
print(f"Saved Analysis to: {output_csv}")