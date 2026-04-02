# completeness comparison between tier 3 evaluation
# comparison between question, model and document type
from pathlib import Path

import pandas as pd

# Paths and constants
ROOT = Path(r'C:\TTA\VScode\ToxTempAssistant')
BASE_DIR = ROOT / 'myocyte' / 'toxtempass' / 'evaluation' / 'data_analysis_plotting' / 'christophe_data_analysis' / 'results' / 'tables' / 'completeness_tier3'
OUTPUT_CSV = ROOT / 'myocyte' / 'toxtempass' / 'evaluation' / 'data_analysis_plotting' / 'christophe_data_analysis' / 'results' / 'tables' / 'completeness_tier3' / 'comparison_completeness' / 'comparison_summary_completeness.csv'
CURRENT_LOC = ROOT / 'myocyte' / 'toxtempass' / 'evaluation' / 'data_analysis_plotting' / 'christophe_data_analysis' / 'christophe_data_analysis' / 'scripts' / 'tier3' / 'comparison_tier3.py'
V1_CSV = BASE_DIR / 'v1_no_description' / 'summary_completeness_v1_nodescription.csv'
V2_CSV = BASE_DIR / 'v2_description' / 'summary_completeness_v2_+description.csv'
NOT_FOUND_STRING = "Answer not found in documents."

# read csv & create Dataframe of tier 3 output
v1_df = pd.read_csv(V1_CSV)
v1_df['eval_version'] = 'v1_no_description'
v2_df = pd.read_csv(V2_CSV)
v2_df['eval_version'] = 'v2_description'

# add column for description to v1_df
v1_df["used_description_file"] = False

# clean up dataframes: drop rows which the llm_answer is empty, drop redundand columns
v1_df = v1_df.loc[v1_df['is_empty'] == False]
v1_df = v1_df.drop(columns=['Unnamed: 0', 'Unnamed: 0.1'])
v2_df = v2_df.loc[v2_df['is_empty'] == False]
v2_df = v2_df.drop(columns=['Unnamed: 0', 'Unnamed: 0.1'])

# exclude msldt and th_uptake assays as they don't have description files
# also exclude ldh_shy5y as it doesn't have a description file yet
v1_df = v1_df.loc[v1_df['assay'] != "msldt"]
v1_df = v1_df.loc[v1_df['assay'] != "ldh_shy5y"]
v2_df = v2_df.loc[v2_df['assay'] != "msldt"]
v2_df = v2_df.loc[v2_df['assay'] != "ldh_shy5y"]

# calculate average and standarddeviation answer_given for each question, model and document type
v1_summary = v1_df.groupby(['section', 'subsection', 'section_short', 'qID',  'question', 'model', 'doc_type', 'eval_version', 'used_description_file'])['answer_given'].mean().reset_index()
v1_summary['answer_given_std'] = v1_df.groupby(['section', 'subsection', 'section_short', 'qID',  'question', 'model', 'doc_type', 'eval_version', 'used_description_file'])['answer_given'].std().reset_index()['answer_given']
v2_summary = v2_df.groupby(['section', 'subsection', 'section_short', 'qID',  'question', 'model', 'doc_type', 'eval_version', 'used_description_file'])['answer_given'].mean().reset_index()
v2_summary['answer_given_std'] = v2_df.groupby(['section', 'subsection', 'section_short', 'qID',  'question', 'model', 'doc_type', 'eval_version', 'used_description_file'])['answer_given'].std().reset_index()['answer_given']

# create new dataframe substracting v1 from v2 to see the difference in answer_given when using description or not
comparison_df = v1_summary.merge(v2_summary, on=['section', 'subsection', 'section_short', 'qID',  'question', 'model', 'doc_type'], suffixes=('_v1', '_v2'))
comparison_df['answer_given_diff'] = comparison_df['answer_given_v2'] - comparison_df['answer_given_v1']

# save comparison_df as csv
comparison_csv = OUTPUT_CSV.with_name("comparison_tier3_v1_vs_v2.csv")
comparison_csv.parent.mkdir(parents=True, exist_ok=True)
comparison_df.to_csv(comparison_csv, index=False)
print(f"Comparison results saved to: {comparison_csv}")

# create average of completeness per doc_type per section

