# Data exploration of the answer_frequency of 
# o3-mini, gpt-4o-mini, gpt-4.1-nano and gpt-5-mini
## add plots showing gtruth_answer_quality_score and completeness

# Imports
import pandas as pd
from pathlib import Path
import glob
import plotly.express as px

# Paths and constants
BASE_DIR = Path('myocyte/toxtempass/evaluation/positive_control/output')
OUTPUT_CSV = Path('myocyte/toxtempass/evaluation/data_analysis_plotting/christophe_data_analysis/results/tables/completeness_positive_controls/summary_completeness.csv')
QUESTION_PATH = Path('myocyte/toxtempass/evaluation/data_analysis_plotting/christophe_data_analysis/enriched/sections/dataframes/ToxTemp_v1_questions_short_section_colour.csv')
NOT_FOUND_STRING = "Answer not found in documents."
CURRENT_LOC = Path('myocyte/toxtempass/evaluation/data_analysis_plotting/christophe_data_analysis/scripts/completeness/summary.py')

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

# section lineplot
# Aggregate to section x model
sec_model = (
    summary_df.groupby(["section_short", "model"], as_index=False)
      .agg(
          mean_answer_given=("answer_given", "mean"),
          std_answer_given=("answer_given", "std"),
          mean_cos_similarity=("cos_similarity", "mean"),
          mean_answer_freq_delta=("answer_freq_delta", "mean"),
          n_questions=("Question_ID2", "nunique"),
          n_rows=("Question_ID2", "size"),
      )
)

#section order
section_order = [
    "1. Overview",
    "2. General information",
    "3. Test system source",
    "4. Test system definition",
    "5. Exposure & endpoints",
    "6. Test method handling",
    "7. Data management",
    "8. Prediction & application",
    "9. Publication/validation status",
    "10. Transferability",
    "11. Safety, ethics & requirements"
]

# order the dataframe
sec_model["section_short"] = pd.Categorical(
    sec_model["section_short"],
    categories=section_order,
    ordered=True
)
sec_model = sec_model.sort_values(["model", "section_short"])

# lineplot of x=sections and y= fraction of question answered
section_models_lineplot = px.line(
    sec_model,
    x='section_short',
    y='mean_answer_given',
    color='model',
    title='Completeness of ToxTemp of different models by section',
    category_orders={"section_short": section_order},
    markers=True
)
section_models_lineplot.update_layout(
    xaxis_title="Section",
    yaxis_title="Fraction of questions answered"
)
section_models_lineplot.show()

# heatmap section x model performance
# Pivot sec_model for heatmap
heat = sec_model.pivot(index="section_short", columns="model", values="mean_answer_given")

# Optional: order sections by overall performance (hardest at top)
section_order = (
    sec_model.groupby("section_short")["mean_answer_given"]
    .mean()
    .sort_values(ascending=True)
    .index
)
heat = heat.loc[section_order]

fig_heat = px.imshow(
    heat,
    text_auto=".2f",
    aspect="auto",
    labels=dict(x="Model", y="Section", color="Mean answer_given"),
    title="Section × Model performance (mean completeness)",
)

fig_heat.update_layout(
    xaxis_title="Model",
    yaxis_title="Section",
)

fig_heat.show()

# lineplot of x=sections and y= mean cosine similarity
section_models_lineplot = px.line(
    sec_model,
    x='section_short',
    y='mean_cos_similarity',
    color='model',
    title='Cosine similarity of answers given by different models per section',
    category_orders={"section_short": section_order},
    markers=True
)
section_models_lineplot.update_layout(
    xaxis_title="Section",
    yaxis_title="Mean of cosine similarity"
)
section_models_lineplot.show()

# plotting delta completeness against section
section_models_lineplot = px.line(
    sec_model,
    x='section_short',
    y='mean_answer_freq_delta',
    color='model',
    title='Mean delta completeness of answers given by different models per section',
    category_orders={"section_short": section_order},
    markers=True
)
section_models_lineplot.update_layout(
    xaxis_title="Section",
    yaxis_title="delta completeness"
)
section_models_lineplot.show()

# Comparing completeness with with_gtruth_output
# DataFrame of positive control output: 'with_gtruth_output', 2182 rows
# section DataFrame: 'question_df', 77 rows

# merging dataframes
all_datapoints_df = question_df.merge(with_gtruth_output, on=["question"]) #now there are 2176 rows?

# create an avarage of answered/unanswered & cosine similarity per model
gtruth_quality_summary_df = all_datapoints_df.groupby(["section","gtruth_answer_quality_score", "model"],as_index=False)[["answer_given", "cos_similarity"]].mean() 

# plotting the answer quality against the questions / sections
section_models_scatterplot = px.scatter(
    all_datapoints_df,
    x='Question_ID2',
    y='gtruth_answer_quality_score',
    color='model',
    title='Mean delta completeness of answers given by different models per section',
    #category_orders={"section_short": section_order},
    #markers=True
)
section_models_scatterplot.update_layout(
    xaxis_title="Question",
    yaxis_title="Groundtruth answer quality"
)
section_models_scatterplot.show()
