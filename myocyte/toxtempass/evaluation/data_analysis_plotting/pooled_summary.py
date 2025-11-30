from pathlib import Path

import pandas as pd
from myocyte.settings import BASE_DIR

# Directory containing Tier1 results organized by model subfolder
base_dir_tier1 = BASE_DIR/"toxtempass/evaluation/positive_control/output"

base_dir_tier2 = BASE_DIR/"toxtempass/evaluation/negative_control/output"
# List of model subfolders
model_dirs = ["gpt-4.1-nano", "gpt-4o-mini", "o3-mini"]

tau = 0.6

# Function to load and concatenate all CSV files for a given model
def load_model_csvs_tier1(model_name):
    model_folder = base_dir_tier1 / model_name
    csv_paths = sorted(model_folder.glob("*.csv"))
    df_list = [pd.read_csv(path) for path in csv_paths]
    # Concatenate CSVs
    combined_df = pd.concat(df_list, ignore_index=True)
    # Filter out rows where 'gtruth_answers' is empty or NaN
    combined_df = combined_df[
        combined_df["gtruth_answer"].notna() & (combined_df["gtruth_answer"] != "")
    ]
    combined_df['total_tier1'] = len(combined_df)
    return combined_df


# Load combined DataFrames for each model
model_dfs = {model: load_model_csvs_tier1(model) for model in model_dirs}

# Optionally, unpack into individual DataFrame variables:
df_gpt_4_1_nano = model_dfs["gpt-4.1-nano"]
df_gpt_4o_mini = model_dfs["gpt-4o-mini"]
df_o3_mini = model_dfs["o3-mini"]

### Completeness ###


# Function to compute completeness: non-trivial responses over total questions
def calculate_completeness(
    df, answer_col="llm_answer", standard_string="Answer not found in documents."
):
    total_questions = len(df)
    # Count answers that differ from the standard "no answer" string
    non_trivial = df[df[answer_col] != standard_string].shape[0]
    return non_trivial / total_questions if total_questions > 0 else 0


# Compute completeness for each model DataFrame
completeness_scores = {
    model: calculate_completeness(df, answer_col="llm_answer")
    for model, df in model_dfs.items()
}

# Print out completeness percentages
for model, score in completeness_scores.items():
    print(f"Completeness for {model}: {score:.2%}")

### True Positive Rate (TPR) ###


# Function to compute TPR at a given cosine-similarity threshold tau
def calculate_tpr(
    df,
    similarity_col="cos_similarity",
    answer_col="llm_answer",
    standard_string="Answer not found in documents.",
    tau=tau,
):
    total_questions = len(df)
    # Count non-trivial responses with similarity above tau
    hits = df[(df[answer_col] != standard_string) & (df[similarity_col] > tau)].shape[0]
    return hits / total_questions if total_questions > 0 else 0


# Compute and print TPR for each model at tau = 0.6
tpr_scores = {model: calculate_tpr(df, tau=tau) for model, df in model_dfs.items()}

for model, score in tpr_scores.items():
    print(f"TPR at tau={tau} for {model}: {score:.2%}")


### Precision ###


# Function to compute Precision at a given cosine-similarity threshold tau
def calculate_precision(
    df,
    similarity_col="cos_similarity",
    answer_col="llm_answer",
    standard_string="Answer not found in documents.",
    tau=tau,
):
    # Count non-trivial responses
    non_trivial = df[df[answer_col] != standard_string].shape[0]
    # Count non-trivial responses with similarity above tau
    hits = df[(df[answer_col] != standard_string) & (df[similarity_col] > tau)].shape[0]
    return hits / non_trivial if non_trivial > 0 else 0


# Compute and print Precision for each model at the same tau as TPR
precision_scores = {
    model: calculate_precision(df, tau=tau) for model, df in model_dfs.items()
}

for model, score in precision_scores.items():
    print(f"Precision at tau={tau} for {model}: {score:.2%}")

# Compute F1 scores for each model at tau
f1_scores = {}
for model in model_dfs:
    prec = precision_scores[model]
    rec = tpr_scores[model]
    f1_scores[model] = 2 * (prec * rec) / (prec + rec) if (prec + rec) > 0 else 0

# Additional summary stats: mean/median cosine similarity and non-trivial counts
std_str = "Answer not found in documents."
additional_stats = {}
for model, df in model_dfs.items():
    non_trivial_df = df[df["llm_answer"] != std_str]
    additional_stats[model] = {
        "mean_cosine_similarity": non_trivial_df["cos_similarity"].mean(),
        "median_cosine_similarity": non_trivial_df["cos_similarity"].median(),
        "non_trivial_count": len(non_trivial_df),
        "total_tier1": df['total_tier1'].iloc[0]  # Assuming total_tier1 is constant per model"
    }

# Print a consolidated summary table
print(f"\nConsolidated Summary (tau = {tau:.2f}):")
print("Model\tCompleteness\tTPR\tPrecision\tF1\tMeanCos\tMedianCos\tNonTrivialCount")
for model in model_dfs:
    stats = additional_stats[model]
    print(
        f"{model}\t"
        f"{completeness_scores[model]:.2%}\t"
        f"{tpr_scores[model]:.2%}\t"
        f"{precision_scores[model]:.2%}\t"
        f"{f1_scores[model]:.2%}\t"
        f"{stats['mean_cosine_similarity']:.3f}\t"
        f"{stats['median_cosine_similarity']:.3f}\t"
        f"{stats['non_trivial_count']}"
    )

# Create a summary DataFrame for export
summary_df = pd.DataFrame(
    [
        {
            "Model": model,
            "Completeness": completeness_scores[model],
            "TPR": tpr_scores[model],
            "Precision": precision_scores[model],
            "F1": f1_scores[model],
            "MeanCos": additional_stats[model]["mean_cosine_similarity"],
            "MedianCos": additional_stats[model]["median_cosine_similarity"],
            "NonTrivialCount": additional_stats[model]["non_trivial_count"],
            "Total_Tier1": additional_stats[model]['total_tier1'],
        }
        for model in model_dfs
    ]
)

# tier2 

def load_model_json_tier2(model_name):
    model_folder = base_dir_tier2 / model_name
    json_path = list(model_folder.glob("*.json"))[0]  # Assuming one JSON file per model
    # unpack the "records" field from each JSON file
    with open(json_path, 'r') as f:
        data = pd.read_json(f)
        if 'records' in data.columns:
            df = data['records'].apply(pd.Series)
        else:
            df = pd.DataFrame(data)
    return df

load_model_json_tier2(model_dirs[2],)

def get_specificty_per_model(model_name):
    df = load_model_json_tier2(model_name)
    # Calculate specificity as the proportion of true negatives
    # Assuming 'passes' is the count of correct answers and 'total' is the total questions
    specificity = (df['passes'].sum()) / df['total'].sum()
    return specificity

def get_total_tier2_count(model_name):
    df = load_model_json_tier2(model_name)
    return df['total'].sum()

summary_df['Total_Tier2'] = summary_df['Model'].apply(get_total_tier2_count)
summary_df['Specificity'] = summary_df['Model'].apply(get_specificty_per_model)
# weight bey # nonTrivial count
#summary_df["weight_factor"] =  summary_df["NonTrivialCount"] / (616 + summary_df["NonTrivialCount"] )
summary_df["Weighing_Factor_Pi"] = summary_df['Total_Tier1'] / (summary_df['Total_Tier2'] + summary_df['Total_Tier1'])
summary_df['Accuracy'] = summary_df["Weighing_Factor_Pi"] * summary_df["TPR"] + (1-summary_df["Weighing_Factor_Pi"])*  summary_df['Specificity']

from plotly import express as px
import plotly.graph_objects as go

shape_dict = {"o3-mini": "square", "gpt-4.1-nano": "circle", "gpt-4o-mini": "diamond"}

# Accuracy Plot
fig = px.bar(
    summary_df,
    x="Model",
    y="Accuracy",
    text="Accuracy",
    title="Overall Accuracy",
    color="Model",
    # symbol_map=shape_dict,
    color_discrete_sequence=px.colors.qualitative.Plotly,
)
fig.update_traces(
    texttemplate="",
    textposition="none",
    # Plotly does not support direct background color for bar text annotations,
    # so we add annotation overlays for background color below.
)

# Add annotation overlays for background color behind bar text
for i, row in summary_df.iterrows():
    fig.add_annotation(
        x=row["Model"],
        y=row["Accuracy"],
        text=f"{row['Accuracy']:.1%}",
        showarrow=False,
        font=dict(color="black", size=14),
        bgcolor="rgba(255,255,255,0.7)",  # Change this to your desired background color
        yshift=10,
    )
fig.update_layout(
    yaxis=dict(title=r"$A|_{\cos\theta>0.6} \,\big/\,{\%}$", showgrid=True, gridcolor="lightgrey", zeroline=False),
    xaxis=dict(title="Model", showgrid=False),
    title_x=0.5,
    title_y=0.96,
    margin=dict(t=35, b=50, l=50, r=50),
)            
fig.update_layout(
    showlegend=False,
    legend=dict(
        title_text="",
        orientation="h",
        xref ="paper",
        yref ="paper",
        x=0.5,
        xanchor="center",
        y=1.02,
        yanchor="bottom",
    ),
    yaxis_range=[0,0.85],
    paper_bgcolor='white',
    plot_bgcolor='white',
)   


output_file_300px = (
    Path("/Users/johannehouweling/Desktop/ToxTempAssistant_Validation/Accuracy")
    /"modelsummary.png"
)

fig.write_image(
    str(output_file_300px.with_name("tier1_summary_combined_fig.png")),
    format="png",
    width=300,
    height=300,
    scale=6,
    engine="kaleido",
)

print(f"Saved 300px summary plot to {output_file_300px.with_name("tier1_summary_combined_fig.png")}")


# fig.update_traces(marker=dict(size=10))


# print("\nConsolidated Summary:")
# print(summary_df.to_string(index=False))

# # Export summary table for download
# output_dir = Path(
#     "/Users/johannehouweling/Desktop/ToxTempAssistant_Validation/Tier1_results/summary"
# )
# csv_path = output_dir / "summary.csv"
# html_path = output_dir / "summary.html"

# # Save CSV
# summary_df.to_csv(csv_path, index=False)
# # Save styled HTML
# styled = summary_df.style.format(
#     {"Completeness": "{:.2%}", "TPR": "{:.2%}", "Precision": "{:.2%}", "F1": "{:.2%}"}
# )
# styled.to_html(html_path, index=False)

# print(f"\nSummary files written:\n - CSV: {csv_path}\n - HTML: {html_path}")

# # Export summary as a LaTeX table
# formatted_df = summary_df.copy()
# for col in ["Completeness", "TPR", "Precision", "F1"]:
#     formatted_df[col] = formatted_df[col].map(lambda x: f"{x:.2%}")
# latex_path = output_dir / "summary.tex"
# with open(latex_path, "w") as f:
#     f.write(formatted_df.to_latex(index=False, escape=False))
# print(f" - LaTeX: {latex_path}")
