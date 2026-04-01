# analyzing completness per document type (e.g. SOP, paper, etc.)

#imports
from pathlib import Path

import pandas as pd
import plotly.express as px

# Paths and constants
ROOT = Path(r'C:\TTA\VScode\ToxTempAssistant')
BASE_DIR = ROOT / 'myocyte' / 'toxtempass' / 'evaluation' / 'real_world_files' / 'output'
OUTPUT_CSV = ROOT / 'myocyte' / 'toxtempass' / 'evaluation' / 'data_analysis_plotting' / 'christophe_data_analysis' / 'results' / 'tables' / 'completeness_tier3' / 'summary_completeness.csv'
QUESTION_PATH = ROOT / 'myocyte' / 'toxtempass' / 'evaluation' / 'data_analysis_plotting' / 'christophe_data_analysis' / 'enriched' / 'sections' / 'dataframes' / 'ToxTemp_v1_questions_short_section_colour.csv'
NOT_FOUND_STRING = "Answer not found in documents."
CURRENT_LOC = ROOT / 'myocyte' / 'toxtempass' / 'evaluation' / 'data_analysis_plotting' / 'christophe_data_analysis' / 'scripts' / 'tier3' / 'completeness' / 'summary.py'

# Debug prints
print(f"BASE_DIR: {BASE_DIR}")
print(f"BASE_DIR exists: {BASE_DIR.exists()}")
print(f"OUTPUT_CSV parent exists: {OUTPUT_CSV.parent.exists()}")
print(f"QUESTION_PATH exists: {QUESTION_PATH.exists()}")

# read question DataFrame
question_df = pd.read_csv(QUESTION_PATH)
question_df.set_index('Question_ID', inplace=True)

#read csv & create Dataframe of tier 3 output
csv_files = sorted(BASE_DIR.rglob("*.csv"))
print(f"Found {len(csv_files)} CSV files in {BASE_DIR}")
if not csv_files:
    raise FileNotFoundError(f"No CSV files found in: {BASE_DIR}")

df = []
for file in csv_files:
    df_output = pd.read_csv(file)
    df_output["doc_name"] = file.name
    df_output["assay"] = file.parent.parent.name
    df_output["doc_type"] = file.parent.name
    df_output["model"] = file.parent.parent.parent.name
    df.append(df_output)

combined_output = pd.concat(df)

# add column giving a value of 1 to answered questions and 0 to unanswered questions
combined_output["answer_given"] = (
    ~combined_output['llm_answer']
    .str.contains(NOT_FOUND_STRING, regex=False)
).astype(int)

# merge question and output DataFrame
merged_df = question_df.merge(combined_output, on=["question"])

# drop rows without an assay description (msldt and th_uptake)
# merged_df = merged_df.loc[merged_df['used_description_file'] == True]

# drop rows which the llm_answer is empty
merged_df = merged_df.loc[merged_df['is_empty'] == False]


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

# save all datapoints DataFrame as csv
OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
merged_df.to_csv(OUTPUT_CSV)
print(f"Saved Analysis to: {OUTPUT_CSV}")

# overall comparison


# # create average of completeness per doc_type
doc_type_completeness_df = merged_df.groupby(["section", "section_short","subsection","qID", "question", "doc_type", "colour"], as_index=False)["answer_given"].mean()

# save doc_type completeness Dataframe
doc_type_completeness_csv = OUTPUT_CSV.with_name(
    f"doc_type_{OUTPUT_CSV.stem}.csv"
)
doc_type_completeness_csv.parent.mkdir(parents=True, exist_ok=True)
doc_type_completeness_df.to_csv(doc_type_completeness_csv)
print(f"Saved average dataframe to:{doc_type_completeness_csv}")

# order DataFrame
doc_type_completeness_df["section_short"] = pd.Categorical(
    doc_type_completeness_df["section_short"],
    categories=section_order,
    ordered=True
)
# reduce dataframe to one value per section per doc_type (mean across questions)
doc_type_section_df = (
    doc_type_completeness_df.groupby(["section_short", "doc_type"], as_index=False)
      .agg(
          mean_answer_given=("answer_given", "mean"),
          std_answer_given=("answer_given", "std"),
          n_questions=("qID", "nunique"),
          n_rows=("qID", "size"),
      )
)
# plot of doc_type x section
doc_type_line = px.line(
    doc_type_section_df,
    x='section_short',
    y='mean_answer_given',
    color='doc_type',
    title='Completeness of ToxTemp per section per document type',
    category_orders={"section_short": section_order},
    markers=True
)
doc_type_line.update_layout(
    xaxis_title="Section",
    yaxis_title="Fraction of questions answered",
    yaxis_range=[0, 1.1]
)
doc_type_line.show()

# completeness per Assay
assay_completeness_df = merged_df.groupby(["section", "section_short","subsection","qID", "question", "assay", "colour"], as_index=False)["answer_given"].mean()

# save assay completeness Dataframe
assay_completeness_csv = OUTPUT_CSV.with_name(
    f"assay_{OUTPUT_CSV.stem}.csv"
)
assay_completeness_csv.parent.mkdir(parents=True, exist_ok=True)
assay_completeness_df.to_csv(assay_completeness_csv)
print(f"Saved average dataframe to:{assay_completeness_csv}")

# order DataFrame
assay_completeness_df["section_short"] = pd.Categorical(
    assay_completeness_df["section_short"],
    categories=section_order,
    ordered=True
)

# reduce dataframe to one value per section per doc_type (mean across questions)
assay_completeness_df = (
    assay_completeness_df.groupby(["section_short", "assay"], as_index=False)
      .agg(
          mean_answer_given=("answer_given", "mean"),
          std_answer_given=("answer_given", "std"),
          n_questions=("qID", "nunique"),
          n_rows=("qID", "size"),
      )
)

# plot assay x section (not really informative for evaluation TTA, informative for status assay)
assay_line = px.line(
    assay_completeness_df,
    x='section_short',
    y='mean_answer_given',
    color='assay',
    title='Completeness of ToxTemp per section per assay',
    category_orders={"section_short": section_order},
    markers=True
)
assay_line.update_layout(
    xaxis_title="Section",
    yaxis_title="Fraction of questions answered",
    yaxis_range=[0, 1.1]
)
assay_line.show()

# completeness per model
model_completeness_df = merged_df.groupby(["section", "section_short","subsection","qID", "question", "model", "colour"], as_index=False)["answer_given"].mean()

# save model completeness Dataframe
model_completeness_csv = OUTPUT_CSV.with_name(
    f"model_{OUTPUT_CSV.stem}.csv"
)
model_completeness_csv.parent.mkdir(parents=True, exist_ok=True)
model_completeness_df.to_csv(model_completeness_csv)
print(f"Saved average dataframe to:{model_completeness_csv}")

# order DataFrame
model_completeness_df["section_short"] = pd.Categorical(
    model_completeness_df["section_short"],
    categories=section_order,
    ordered=True
)

# reduce dataframe to one value per section per doc_type (mean across questions)
model_completeness_df = (
    model_completeness_df.groupby(["section_short", "model"], as_index=False)
      .agg(
          mean_answer_given=("answer_given", "mean"),
          std_answer_given=("answer_given", "std"),
          n_questions=("qID", "nunique"),
          n_rows=("qID", "size"),
      )
)

# plot model x section
model_line = px.line(
    model_completeness_df,
    x='section_short',
    y='mean_answer_given',
    color='model',
    title='Completeness of ToxTemp per section per LLM model',
    category_orders={"section_short": section_order},
    markers=True
)
model_line.update_layout(
    xaxis_title="Section",
    yaxis_title="Fraction of questions answered",
    yaxis_range=[0, 1.1]
)
model_line.show()

# Make graphs of specific doc types and how well certein models perform
# first create dataframe with doc_type, model, section_short, answer_given
doc_model_completeness_df = merged_df.groupby(["section", "section_short","doc_type", "model", "qID"], as_index=False)["answer_given"].mean()

#order dataframe based on section
doc_model_completeness_df["section_short"] = pd.Categorical(
    doc_model_completeness_df["section_short"],
    categories=section_order,
    ordered=True
)
# reduce dataframe to one value per section per doc_type (mean across questions)
doc_model_completeness_df = (
    doc_model_completeness_df.groupby(["section_short", "doc_type", "model"], as_index=False)
      .agg(
          mean_answer_given=("answer_given", "mean"),
          std_answer_given=("answer_given", "std"),
          n_questions=("qID", "nunique"),
          n_rows=("qID", "size"),
      )
)

# plot model x section for each doc_type
for doc_type in doc_model_completeness_df["doc_type"].unique():
    globals()[f"{doc_type}_model_line"] = px.line(
        doc_model_completeness_df[doc_model_completeness_df["doc_type"] == doc_type],
        x='section_short',
        y='mean_answer_given',
        color='model',
        title=f'Completeness of ToxTemp per section per LLM model for {doc_type}s',
        category_orders={"section_short": section_order},
        markers=True
    )
    globals()[f"{doc_type}_model_line"].update_layout(
        xaxis_title="Section",
        yaxis_title="Fraction of questions answered",
        yaxis_range=[0, 1.1]
    )
    globals()[f"{doc_type}_model_line"].show()
