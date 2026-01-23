# Analysing if and which questions are frequently unanswered by the ToxTempAssistant

# imports
import pandas as pd
import glob
import matplotlib.pyplot as plt
from pathlib import Path

#TTA question file location
TTAquestions_path = 'myocyte/toxtempass/evaluation/data_analysis_plotting/christophe_data_analysis/enriched/sections/dataframes/ToxTemp_v1_questions_short_section.csv'
question_df = pd.read_csv(TTAquestions_path)

# Configuration (put paths, constants) at the top
BASE_DIR = Path("myocyte/toxtempass/evaluation/positive_control/output/gpt-5-mini")
OUTPUT_CSV = Path("myocyte/toxtempass/evaluation/data_analysis_plotting/christophe_data_analysis/results/tables/answer_frequency_positive_controls/answer_freq_5-mini.csv")
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

# adding a column classifying ability to answer low, medium, high
bins = [0, 0.4, 0.7, 1]
labels = ["low", "medium", "high"]

summary["answer_ability"] = pd.cut(
    summary["answer_given"],
    bins=bins,
    labels=labels,
    include_lowest=True
)

# merging evaluation & section dataframes
merged_df = summary.merge(question_df, on=["question"])

# making temporary index --> needs to be adjusted when section dataframe is added
merged_df = merged_df.reset_index(drop=True)
merged_df.index = merged_df.index + 1
merged_df.index.name = "Question_ID"

# making lists of 3 answer abilities
low_list = merged_df.index[merged_df["answer_ability"] == "low",].tolist()
medium_list = merged_df.loc[merged_df["answer_ability"] == "medium", "question"].tolist()
high_list = merged_df.loc[merged_df["answer_ability"] == "high", "question"].tolist()

# making an ascending list questions based on "answer_given"
difficulty_list_index = merged_df.sort_values("answer_given", ascending=True).index.tolist()
difficulty_list_question = merged_df.sort_values("answer_given", ascending=True)["question"].tolist()

# barplot based on question ID
plt.bar(merged_df.index, merged_df['answer_given'])
plt.xlabel('Question_ID')
plt.ylabel('Frequency of question answered')
plt.title ("gpt-5-mini question answer frequency")
plt.xticks(rotation=90)

plt.show()

#save DataFrame as csv
OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True) # to avoid folder not found errors
merged_df.to_csv(OUTPUT_CSV)

print(f"Saved merged_df to: {OUTPUT_CSV}")

# barplot based on section
plt.bar(merged_df['section_short'], merged_df['answer_given'])
plt.xlabel('section')
plt.ylabel('Frequency of question answered')
plt.title ("gpt-5-mini question answer frequency per section")
plt.xticks(rotation=90)

plt.show()
