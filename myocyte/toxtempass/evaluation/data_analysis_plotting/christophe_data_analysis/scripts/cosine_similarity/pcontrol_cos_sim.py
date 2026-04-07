#visualise cosine similarity between different models for positive control files
# metrics: cosine_similarity
# models: o3-mini, gpt-4o-mini, gpt-5-mini, gpt-5.4-mini, gpt-5-nano, gpt-5.4-nano
# experiment: input_type_comparison

# imports
from pathlib import Path

import pandas as pd
import plotly.express as px

# Paths and constants
ROOT = Path(r'C:\TTA\VScode\ToxTempAssistant')
BASE_DIR = ROOT / 'myocyte' / 'toxtempass' / 'evaluation' / 'positive_control' / 'output'
OUTPUT_CSV = ROOT / 'myocyte' / 'toxtempass' / 'evaluation' / 'data_analysis_plotting' / 'christophe_data_analysis' / 'results' / 'tables' / 'cosine_similarity_positive_controls' / 'pc_cos_sim_comparison.csv'
QUESTION_PATH = ROOT / 'myocyte' / 'toxtempass' / 'evaluation' / 'data_analysis_plotting' / 'christophe_data_analysis' / 'enriched' / 'sections' / 'dataframes' / 'ToxTemp_v1_questions_short_section_colour.csv'
NOT_FOUND_STRING = "Answer not found in documents."

# read question DataFrame
question_df = pd.read_csv(QUESTION_PATH)
question_df.set_index('Question_ID', inplace=True)

# read positive control csv files & create DataFrame
csv_files = sorted(BASE_DIR.rglob("*.csv"))
print(f"Found {len(csv_files)} CSV files in {BASE_DIR}")
if not csv_files:
    raise FileNotFoundError(f"No CSV files found in: {BASE_DIR}")

df = []
for file in csv_files:
    df_output = pd.read_csv(file)
    df_output["doc_name"] = file.name
    df_output["model"] = file.parent.name
    df.append(df_output)
df = pd.concat(df, ignore_index=True)

# exclude rows which have no gtruth_answer
df_tidy = df.dropna(subset=['gtruth_answer'])

# merge question and output DataFrame
merged_df = question_df.merge(df_tidy, on=["question"])

#drop columns which are not needed for cosine similarity analysis
merged_df = merged_df.drop(columns=['Unnamed: 0', 'bert_precision', 'bert_recall', 'bert_f1'])

# save all datapoints DataFrame as csv
OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
merged_df.to_csv(OUTPUT_CSV)
print(f"Saved Analysis to: {OUTPUT_CSV}")

# calculate average cosine similarity per question per model
question_cos_sim_summary = merged_df.groupby(['section#', 'section', 'subsection', 'section_short', 'Question_ID2', 'question', 'model'])['cos_similarity'].mean().reset_index()

# save question summary DataFrame as csv
question_summary_csv = OUTPUT_CSV.with_name("question_summary_pc_cos_sim.csv")
question_summary_csv.parent.mkdir(parents=True, exist_ok=True)
question_cos_sim_summary.to_csv(question_summary_csv, index=False)
print(f"Saved question Summary to: {question_summary_csv}")

# calculate average cosine similarity per section per model
section_cos_sim_summary = merged_df.groupby(['section#', 'section', 'section_short', 'model'])['cos_similarity'].mean().reset_index()

# save question summary DataFrame as csv
section_summary_csv = OUTPUT_CSV.with_name("section_summary_pc_cos_sim.csv")
section_summary_csv.parent.mkdir(parents=True, exist_ok=True)
section_cos_sim_summary.to_csv(section_summary_csv, index=False)
print(f"Saved Section Summary to: {section_summary_csv}")


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
# order dataframe by section order
section_cos_sim_summary["section_short"] = pd.Categorical(
    section_cos_sim_summary["section_short"],
    categories=section_order,
    ordered=True
)

# plot cosine similarity per section per model
cos_sim_line = px.line(
    section_cos_sim_summary,
    x='section_short',
    y='cos_similarity',
    color='model',
    title='Cosine similarity of ToxTemp per section per model',
    category_orders={"section_short": section_order},
    markers=True
)
cos_sim_line.update_layout(
    xaxis_title="Section",
    yaxis_title="Cosine similarity",
    yaxis_range=[0, 1.1]
)
cos_sim_line.show()
