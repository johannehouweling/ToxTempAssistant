from pathlib import Path
import pandas as pd

base_dir = Path(
    "/Users/johannehouweling/Desktop/ToxTempAssistant_Validation_FAIR/experiments/positive/per_doc"
)
model_dirs = ["gpt-4.1-nano", "gpt-4o-mini", "o3-mini"]

# Step 1: Get all unique assay names from all CSVs
assay_files = {}
for model in model_dirs:
    model_path = base_dir / model
    for file in model_path.glob("tier1_comparison_*.csv"):
        assay_name = file.stem.replace("tier1_comparison_", "")
        assay_files.setdefault(assay_name, {})[model] = file

# Check how many assays detected
print(f"Detected assays: {list(assay_files.keys())}")  # should be 8 assays

# Step 2: For each assay, merge the data from all available models
combined_per_assay = {}

for assay, files in assay_files.items():
    dfs = []
    for model, path in files.items():
        df = pd.read_csv(path)

        # Rename model-specific columns
        df = df.rename(
            columns={
                "llm_answer": f"llm_answer_{model}",
                "cos_similarity": f"llm_answer_{model}_cos_similarity",
            }
        )

        # Drop duplicate columns for merging (except question and ground truth info)
        keep_cols = [
            "question",
            "gtruth_answer",
            "gtruth_answer_quality_score",
            "gtruth_answer_quality_justification",
        ]
        model_cols = [
            col
            for col in df.columns
            if col.startswith("llm_answer_") or col.endswith("_cos_similarity")
        ]
        cols_to_keep = keep_cols + model_cols
        df = df[cols_to_keep].copy()

        dfs.append(df)

    # Merge on common columns (question assumed to be the merge key)
    from functools import reduce

    merged_df = reduce(
        lambda left, right: pd.merge(
            left,
            right,
            on=[
                "question",
                "gtruth_answer",
                "gtruth_answer_quality_score",
                "gtruth_answer_quality_justification",
            ],
            how="outer",
        ),
        dfs,
    )
    # After merging, remove rows with missing ground truth or any model's trivial response
    merged_df = merged_df[merged_df["gtruth_answer"].notna()]
    llm_answer_cols = [
        col
        for col in merged_df.columns
        if col.startswith("llm_answer_") and not col.endswith("_cos_similarity")
    ]
    for col in llm_answer_cols:
        merged_df = merged_df[merged_df[col] != "Answer not found in documents."]

    merged_df.insert(0, "assay", assay)
    combined_per_assay[assay] = merged_df
    # Calculate and print mean cosine similarity per model for this assay
    import numpy as np

    cosine_stats = {
        col.replace("llm_answer_", "").replace("_cos_similarity", ""): {
            "mean": merged_df[col].mean(),
            "std": merged_df[col].std(),
            "min": merged_df[col].min(),
            "max": merged_df[col].max(),
        }
        for col in merged_df.columns
        if col.endswith("_cos_similarity")
    }
    print(f"Assay: {assay}")
    print(f"Number of questions answered for each model: {len(merged_df)}")
    print(f"Cosine similarity stats:")
    for model, stats in cosine_stats.items():
        print(
            f"  {model}: mean = {stats['mean']:.3f}, std = {stats['std']:.3f}, min = {stats['min']:.3f}, max = {stats['max']:.3f}"
        )

    # Export each assay DataFrame as a CSV file
    output_dir = base_dir / "combined_assays_answered_by_all_models"
    output_dir.mkdir(exist_ok=True)
    merged_df.to_csv(output_dir / f"{assay}_combined.csv", index=False)

    # Store summary statistics for later export
    if "summary_stats" not in locals():
        summary_stats = []

    for model, stats in cosine_stats.items():
        summary_stats.append(
            {
                "assay": assay,
                "model": model,
                "n": len(merged_df),
                "mean": f"{stats['mean']:.3f}",
                "std": f"{stats['std']:.3f}",
                "min": f"{stats['min']:.3f}",
                "max": f"{stats['max']:.3f}",
            }
        )


# Export all cosine similarity statistics to a CSV file
summary_df = pd.DataFrame(summary_stats)
summary_df.to_csv(output_dir / "summary_cosine_similarity_stats.csv", index=False)

# Recalculate grouped summary directly from *_combined.csv files
grouped_stats = {}
for file in output_dir.glob("*_combined.csv"):
    df = pd.read_csv(file)
    for col in df.columns:
        if col.endswith("_cos_similarity"):
            model = col.replace("llm_answer_", "").replace("_cos_similarity", "")
            values = df[col].dropna()
            if model not in grouped_stats:
                grouped_stats[model] = []
            grouped_stats[model].extend(values.tolist())

# Now compute fresh stats per model
grouped_summary_df = pd.DataFrame(
    [
        {
            "model": model,
            "n_total": len(vals),
            "mean_cosine": f"{np.mean(vals):.3f}",
            "std_cosine": f"{np.std(vals, ddof=1):.3f}",
            "min_cosine": f"{np.min(vals):.3f}",
            "max_cosine": f"{np.max(vals):.3f}",
            "pct_above_0.60": f"{(np.sum(np.array(vals) > 0.60) / len(vals)) * 100:.1f}%",
        }
        for model, vals in grouped_stats.items()
    ]
)

print("\nRecomputed cosine similarity summary across all assays (from combined files):")
print(grouped_summary_df)

# Export updated summary
grouped_summary_df.to_csv(
    output_dir / "summary_cosine_similarity_stats_per_model.csv", index=False
)
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import plotly.express as px

# Prepare data
grouped_summary_df["mean_cosine"] = grouped_summary_df["mean_cosine"].astype(float)
grouped_summary_df["std_cosine"] = grouped_summary_df["std_cosine"].astype(float)
grouped_summary_df["min_cosine"] = grouped_summary_df["min_cosine"].astype(float)
grouped_summary_df["max_cosine"] = grouped_summary_df["max_cosine"].astype(float)
grouped_summary_df["pct_above_0.60"] = (
    grouped_summary_df["pct_above_0.60"].str.replace("%", "").astype(float)
)

models = grouped_summary_df["model"]

# Expand grouped_stats into a DataFrame for individual points
all_cosine_df = pd.DataFrame(
    [
        {"model": model, "cosine": val}
        for model, vals in grouped_stats.items()
        for val in vals
    ]
)

model_to_num = {model: i for i, model in enumerate(grouped_summary_df["model"])}

color_map = {"gpt-4.1-nano": "#6A8DFF", "gpt-4o-mini": "#FF7660", "o3-mini": "#50D2A0"}

# Create subplot layout
fig = go.Figure()

# ─────────────────────────────
# 1. Violin Plot of Cosine Similarities per Model
# ─────────────────────────────
for model in grouped_summary_df["model"]:
    model_values = all_cosine_df[all_cosine_df["model"] == model]["cosine"]
    fig.add_trace(
        go.Violin(
            y=model_values,
            x=[model] * len(model_values),
            name=model,
            box_visible=True,
            meanline_visible=True,
            points="all",
            scalemode="count",
            jitter=0.4,
            marker=dict(size=4, opacity=0.5, color=color_map[model]),
            line_color=color_map[model],
            showlegend=False,
        ),
    )

# Add horizontal threshold line at 0.60
fig.add_shape(
    type="line",
    x0=-0.5,
    x1=2.5,
    y0=0.60,
    y1=0.60,
    line=dict(color="grey", width=2, dash="dot"),
)


# Add percentage above threshold as text just to the right of each violin
for i, row in grouped_summary_df.iterrows():
    fig.add_annotation(
        x=i + 0.17,
        y=0.64,
        text=f"{row['pct_above_0.60']:.1f}%",
        showarrow=False,
        font=dict(size=10),
        xanchor="left",
        yanchor="middle",
    )

# ─────────────────────────────
# Layout and Show
# ─────────────────────────────
fig.update_layout(
    height=400,
    width=600,
    title_text=r"$\cos\theta$ for questions (n = 206) answered by all models",
    showlegend=True,
    template="plotly_white",
)

fig.update_yaxes(title_text=r"$\cos\theta$", range=[0.01, 1])
fig.update_xaxes(
    title_text="Model",
    categoryorder="array",
    categoryarray=list(grouped_summary_df["model"]),
)

fig.show()

# Save image output
output_file_300px = (
    Path(
        "/Users/johannehouweling/Desktop/ToxTempAssistant_Validation/Tier1_results/combined_assays_answered_by_all_models/"
    )
    / "modelsummary_corrected.png"
)

fig.write_image(
    str(output_file_300px.with_name("tier1_summary_combined_fig_corrected.png")),
    format="png",
    width=700,
    height=500,
    scale=6,
    engine="kaleido",
)

print(
    f"Saved corrected 300px summary plot to {output_file_300px.with_name('tier1_summary_combined_fig_corrected.png')}"
)
