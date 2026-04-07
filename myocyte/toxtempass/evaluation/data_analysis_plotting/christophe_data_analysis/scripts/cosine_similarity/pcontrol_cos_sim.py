#visualise cosine similarity between different models for positive control files
# metrics: cosine_similarity
# models: o3-mini, gpt-4o-mini, gpt-5-mini, gpt-5.4-mini, gpt-5-nano, gpt-5.4-nano
# experiment: input_type_comparison

# imports
from pathlib import Path
import pandas as pd
import glob

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

