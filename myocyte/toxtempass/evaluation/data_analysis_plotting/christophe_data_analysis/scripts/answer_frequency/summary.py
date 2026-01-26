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

# merge section & ouput DataFrames
summary_df = question_df.merge(average_df, on=["question"]) #now there are 304 rows??

# making temporary index --> needs to be adjusted when section dataframe is added
summary_df = summary_df.reset_index(drop=True)
summary_df.index = summary_df.index + 1

# create average of answer frequency combining all models
question_mean_df = summary_df.groupby(["question"]).mean('answer_given')
question_mean_df = question_mean_df.sort_values('answer_given', ascending=True)

# save mean question dataframe as csv
output_average_summary_csv = OUTPUT_CSV.with_name(
    f"average_{OUTPUT_CSV.stem}.csv"
)
output_average_summary_csv.parent.mkdir(parents=True, exist_ok=True)
question_mean_df.to_csv(output_average_summary_csv)
print(f"Saved average dataframe to:{output_average_summary_csv}")

# calculating difference answering frequency per model per question compared to average
mean_lookup = question_mean_df.set_index("Question_ID2")["answer_given"]
summary_df["answer_freq_delta"] = (
    summary_df["answer_given"] - summary_df["Question_ID2"].map(mean_lookup)
)

# save DataFrame as csv
OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
summary_df.to_csv(OUTPUT_CSV)
print(f"Saved Analysis to: {OUTPUT_CSV}")

# making a list of least answered questions per model
o3_mini_list = summary_df.loc[summary_df["model"] == "o3-mini"].sort_values("answer_given", ascending=True)["Question_ID2"].tolist()
gpt_4o_mini_list = summary_df.loc[summary_df["model"] == "gpt-4o-mini"].sort_values("answer_given", ascending=True)["Question_ID2"].tolist()
gpt_41_nano_list = summary_df.loc[summary_df["model"] == "gpt-4.1-nano"].sort_values("answer_given", ascending=True)["Question_ID2"].tolist()
gpt_5_mini_list = summary_df.loc[summary_df["model"] == "gpt-5-mini"].sort_values("answer_given", ascending=True)["Question_ID2"].tolist()

#plots
section_barplot = px.bar(
    summary_df, 
    x='section_short', 
    y='answer_given',
    color="model",
    barmode = 'group'
)
section_barplot.show()

answerability_cos_similarity_barplot = px.bar(
    summary_df,
    x='answer_ability', 
    y='cos_similarity',
    color="model",
    barmode = 'group'
)
answerability_cos_similarity_barplot.show()

delta_plot = px.scatter(
    summary_df,
    x='answer_freq_delta',
    y='section',
    color='model'
)
delta_plot.show()