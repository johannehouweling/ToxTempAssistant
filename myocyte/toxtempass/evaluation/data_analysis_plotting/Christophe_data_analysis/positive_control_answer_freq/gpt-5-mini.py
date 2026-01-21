# Analysing if and which questions are frequently unanswered by the ToxTempAssistant

# imports
import pandas as pd
import glob
import matplotlib.pyplot as plt
from pathlib import Path

# Configuration (put paths, constants) at the top
BASE_DIR = Path("myocyte/toxtempass/evaluation/positive_control/output/gpt-5-mini")
OUTPUT_CSV = Path("myocyte/toxtempass/evaluation/data_analysis_plotting/Christophe_data_analysis/positive_control_answer_freq/summary_answer_freq_5-mini.csv")
NOT_FOUND_STRING = "Answer not found in documents."

# read csv & create DataFrame with the individual files combined
csv_files = sorted(BASE_DIR.glob("*.csv"))
if not csv_files:
    raise FileNotFoundError(f"No CSV files found in: {BASE_DIR}")

df = []
for file in csv_files:
    df_pc5mini = pd.read_csv(file)
    df_pc5mini["source_file"] = file.name
    df.append(df_pc5mini)

combined_5mini_df = pd.concat(df)

print(combined_5mini_df.head())
print(combined_5mini_df.shape)
print(combined_5mini_df.columns)

# add a column giving a value of 1 to answered questions and 0 to unanswered questions by the LLM
combined_5mini_df["answer_given"] = (
    ~combined_5mini_df['llm_answer']
    .str.contains(NOT_FOUND_STRING, regex=False)
    ).astype(int)

print(combined_5mini_df['answer_given'])

# removing the rows which have no ground truth
with_gtruth_5mini = combined_5mini_df.dropna(subset=['gtruth_answer'])

print(with_gtruth_5mini.shape)

# create an average of answered/unanswered over the documents per question
summary = with_gtruth_5mini.groupby("question", as_index=False)["answer_given"].mean()

print(summary)
print(summary.shape) #there is only 1 question which has no gtruth in every positive control (somewhere after question 53)

# adding a column with short versions of the questions
summary["question_short"] = (
    summary["question"]
    .fillna("")
    .astype(str)
    .str.split()
    .str[:10]
    .str.join(" ")
)

# adding a column classifying ability to answer low, medium, high
bins = [0, 0.4, 0.7, 1]
labels = ["low", "medium", "high"]

summary["answer_ability"] = pd.cut(
    summary["answer_given"],
    bins=bins,
    labels=labels,
    include_lowest=True
)

# making temporary index --> needs to be adjusted when section dataframe is added
summary = summary.reset_index(drop=True)
summary.index = summary.index + 1
summary.index.name = "Question_ID"

# making lists of 3 answer abilities
low_list = summary.index[summary["answer_ability"] == "low",].tolist()
medium_list = summary.loc[summary["answer_ability"] == "medium", "question"].tolist()
high_list = summary.loc[summary["answer_ability"] == "high", "question"].tolist()

# making an ascending list questions based on "answer_given"
difficulty_list_index = summary.sort_values("answer_given", ascending=True).index.tolist()
difficulty_list_question = summary.sort_values("answer_given", ascending=True)["question_short"].tolist()

# barplot
plt.bar(summary.index, summary['answer_given'])
plt.xlabel('Question_ID')
plt.ylabel('Frequency of question answered')
plt.title ("gpt-5-mini question answer frequency")
plt.xticks(rotation=90)

plt.show()

#save DataFrame as csv
OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True) # to avoid folder not found errors
summary.to_csv(OUTPUT_CSV)

print(f"Saved summary to: {OUTPUT_CSV}")