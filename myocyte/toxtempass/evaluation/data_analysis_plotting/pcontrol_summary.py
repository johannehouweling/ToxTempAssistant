import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from IPython.display import display
from myocyte.settings import BASE_DIR
from plotly import express as px
from plotly.subplots import make_subplots


def extract_question_text(failures, n=50) -> str:
    return [
        (
            elem["question_text"][:n] + "<br>"
            if len(elem["question_text"]) > n
            else elem["question_text"]
        )
        for elem in failures
    ]


# Directory and summary files for each model
base_dir = BASE_DIR / "toxtempass/evaluation/positive_control/output"
# Optional: limit to a subset of model folders; set to None to include all found models.
# Example excluding gpt-5: ["gpt-4.1-nano", "gpt-4o-mini", "o3-mini"]
models_to_plot = ["gpt-4.1-nano", "gpt-4o-mini", "o3-mini"]

# Common plot output directory inside the repo
output_dir = BASE_DIR / "toxtempass" / "evaluation" / "plots"
output_dir.mkdir(parents=True, exist_ok=True)

all_summary_files = list(base_dir.glob("*/*summary*.json"))
if models_to_plot:
    summary_files = [
        (path, path.parent.name)
        for path in all_summary_files
        if path.parent.name in set(models_to_plot)
    ]
else:
    summary_files = [(path, path.parent.name) for path in all_summary_files]


trans_dict = {
    "NPC1": "ToxTemp1",
    "NPC2-5": "ToxTemp2",
    "cMINC(UKN2)": "ToxTemp3",
    "NeuriToxassay(UKN4)": "ToxTemp4",
    "MitoMetassay(UKN4b)": "ToxTemp5",
    "MitoStressLUHMESassay(MSL)": "ToxTemp6",
    "MitoComplexesLUHMESassay(MCL)": "ToxTemp7",
    "PeriToxtest(UKN5)": "ToxTemp8",
}
# Load each JSON into a DataFrame and tag with model
dfs = []
for fname, model_label in summary_files:
    file_path = base_dir / fname
    with file_path.open("r") as fp:
        data = json.load(fp)
    df_tmp = pd.DataFrame(data["records"])
    df_tmp["model"] = model_label
    df_tmp["title_dummy"] = df_tmp["file"].map(lambda f: Path(f).stem)
    df_tmp["short_title"] = df_tmp["title_dummy"].apply(lambda x: trans_dict.get(x, x))
    df_tmp["failures_question_texts"] = df_tmp["failures"].map(extract_question_text)
    df_tmp["cosine_similarity"] = df_tmp["stats"].apply(
        lambda x: x["cos_similarity"]["mean"]
    )
    df_tmp=df_tmp.sort_values(by="short_title")
    dfs.append(df_tmp)



# Combine all models' data
df = pd.concat(dfs, ignore_index=True)
# Display the combined DataFrame for inspection
print("Combined DataFrame preview:")
display(df)  # nicely render first few rows


max_cos = np.round(
    df["cosine_similarity"].max(), 2
)  # Ensure the column is created and has values
min_cos = np.round(
    df["cosine_similarity"].min(), 2
)  

shape_dict = {"o3-mini": "square", "gpt-4.1-nano": "circle", "gpt-4o-mini": "diamond"}

fig = px.scatter(
    df,
    x="short_title",
    y="pass_rate",
    hover_data=["file", "failures_question_texts"],
    symbol="model",
    symbol_map=shape_dict,
    color="cosine_similarity",
    color_continuous_scale=px.colors.sequential.Viridis,
    range_color=[min_cos, max_cos],
)
fig.update_layout(
    showlegend=True,
    xaxis=dict(title="Document", tickangle=-45, automargin=True),
    yaxis=dict(title="Completeness (%)", showgrid=True, gridcolor='lightgrey'),
    margin=dict(b=150),
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
    coloraxis_colorbar=dict(
        title=dict(
            text="Mean Cosine Similarity",
            side="right",
            font=dict(size=14),
        ),
        tickvals=np.linspace(min_cos, max_cos, 3),
        ticktext=[f"{val:.2f}" for val in np.linspace(min_cos, max_cos, 3)],
        ticks="inside",
        ticklen=5,
        tickwidth=1,
        len=1,
        yanchor="top",
        y=1.00,
        xanchor="left",
        x=1.02,
    ),
    paper_bgcolor='white',
    plot_bgcolor='white',
)


fig.update_traces(marker=dict(size=10), showlegend=True)

# Add line connecting square markers (model 'o3-mini')
o3_df = df[df["model"] == "o3-mini"]
fig.add_trace(go.Scatter(
    x=o3_df["short_title"],
    y=o3_df["pass_rate"],
    mode="lines",
    name="o3-mini line",
    line=dict(dash="dash",width=1.5, color='lightgray'),
    showlegend=False,
))

# Add line connecting circle markers (model 'gpt-4.1-nano')
nano_df = df[df["model"] == "gpt-4.1-nano"]
fig.add_trace(go.Scatter(
    x=nano_df["short_title"],
    y=nano_df["pass_rate"],
    mode="lines",
    name="gpt-4.1-nano line",
    line=dict(dash="dash", width=1.5, color='lightgray'),
    showlegend=False,
))

# Add line connecting diamond markers (model 'gpt-4o-mini')
o4o_df = df[df["model"] == "gpt-4o-mini"]
fig.add_trace(go.Scatter(
    x=o4o_df["short_title"],
    y=o4o_df["pass_rate"],
    mode="lines",
    name="gpt-4o-mini line",
    line=dict(dash="dash", width=1.5, color='lightgray'),
    showlegend=False,
))

# Draw lines beneath markers to prevent overlap
line_traces = [trace for trace in fig.data if trace.mode == "lines"]
marker_traces = [trace for trace in fig.data if trace.mode == "markers"]
fig.data = tuple(line_traces + marker_traces)


fig.show()
output_file_300px = output_dir / "pcontrol_summary_fig.png"

fig.write_image(
    str(output_file_300px),
    format="png",
    width=400,
    height=400,
    scale=6,
    engine="kaleido",
)

print(f"Saved 300px summary plot to {output_file_300px}")


# TPR per ToxTemp and model 
# Directory containing Tier1 results organized by model subfolder
base_dir_tier1 = base_dir
base_dir_tier2 = BASE_DIR / "toxtempass/evaluation/negative_control/output"
# List of model subfolders
model_dirs = ["gpt-4.1-nano", "gpt-4o-mini", "o3-mini"]

tau = 0.6

# Function to load and concatenate all CSV files for a given model
def load_model_csvs_tier1(model_name):
    model_folder = base_dir_tier1 / model_name
    csv_paths = sorted(model_folder.glob("*.csv"))
    df_list = [pd.read_csv(path) for path in csv_paths]
    for df, path in zip(df_list, csv_paths):
        df['file'] = path.name
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

def calculate_tpr_precision(
    model_dfs,
    similarity_col="cos_similarity",
    answer_col="llm_answer",
    standard_string="Answer not found in documents.",
    tau=tau,
):
    df_TPR_per_model = []
    for model, df_in in model_dfs.items():
        tpr = []
        precision = []
        filenames = []
        for filename, df in df_in.groupby("file"):
            total_questions = len(df)
            filenames.append(trans_dict[filename.split("_")[-1].replace(".csv", "")])
            # Count non-trivial responses with similarity above tau
            hits = df[(df[answer_col] != standard_string) & (df[similarity_col] > tau)].shape[0]
            non_trivial = df[df[answer_col] != standard_string].shape[0]
            precision.append(
                hits / non_trivial * 100 if non_trivial > 0 else 0
            )
            tpr.append(hits / total_questions *100 if total_questions > 0 else 0)
        df_TPR_per_model.append(pd.DataFrame(columns=["file", "tpr", "precision", "model"],data= {"file": filenames, "tpr": tpr,"precision":precision, "model": model}).sort_values(by="file"))
    return pd.concat(df_TPR_per_model, ignore_index=True)

fig2 = px.scatter(
    calculate_tpr_precision(model_dfs),
    x="file",
    y="tpr",
    symbol="model",
    symbol_map=shape_dict,
    color_discrete_sequence=["rgba(0, 0, 0, 0.7)", "rgba(0, 0, 0, 0.7)", "rgba(0, 0, 0, 0.7)"],
    range_color=[0, 1],
)
fig2.update_layout(
    showlegend=True,
    xaxis=dict(title="Document", tickangle=-45, automargin=True),
    yaxis=dict(title="True Positive Rate (%)", showgrid=True, gridcolor='lightgrey'),
    margin=dict(b=150),
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
    paper_bgcolor='white',
    plot_bgcolor='white',
)


fig2.update_traces(marker=dict(size=10))

# Add line connecting square markers (model 'o3-mini')
o3_df = calculate_tpr_precision(model_dfs)[calculate_tpr_precision(model_dfs)["model"] == "o3-mini"]
fig2.add_trace(go.Scatter(
    x=o3_df["file"],
    y=o3_df["tpr"],
    mode="lines",
    name="",
    line=dict(dash="dash",width=1.5, color='lightgray'),
    showlegend=False,
))

# Add line connecting circle markers (model 'gpt-4.1-nano')
nano_df = calculate_tpr_precision(model_dfs)[calculate_tpr_precision(model_dfs)["model"] == "gpt-4.1-nano"]
fig2.add_trace(go.Scatter(
    x=nano_df["file"],
    y=nano_df["tpr"],
    mode="lines",
    name="",
    line=dict(dash="dash", width=1.5, color='lightgray'),
    showlegend=False,
))

# Add line connecting diamond markers (model 'gpt-4o-mini')
o4o_df = calculate_tpr_precision(model_dfs)[calculate_tpr_precision(model_dfs)["model"] == "gpt-4o-mini"]
fig2.add_trace(go.Scatter(
    x=o4o_df["file"],
    y=o4o_df["tpr"],
    mode="lines",
    name="",
    line=dict(dash="dash", width=1.5, color='lightgray'),
    showlegend=False,
))

# Draw lines beneath markers to prevent overlap
line_traces = [trace for trace in fig2.data if trace.mode == "lines"]
marker_traces = [trace for trace in fig2.data if trace.mode == "markers"]
fig2.data = tuple(line_traces + marker_traces)

fig2.update_traces(
    showlegend=False,
    marker_size=12,
    opacity=0.7,
    marker_line=dict(width=2, color="white")
)

fig2.show()

output_file_300pxB = (
    output_dir / "pcontrol_summary_figB.png"
)

fig2.write_image(
    str(output_file_300pxB),
    format="png",
    width=500,
    height=400,
    scale=6,
    engine="kaleido",
)

print(f"Saved 300px summary plot to {output_file_300pxB}")


# PResision plot

fig3 = px.scatter(
    calculate_tpr_precision(model_dfs),
    x="file",
    y="precision",
    symbol="model",
    symbol_map=shape_dict,
    color_discrete_sequence=["rgba(0, 0, 0, 0.7)", "rgba(0, 0, 0, 0.7)", "rgba(0, 0, 0, 0.7)"],
    range_color=[0, 1],
)
fig3.update_layout(
    showlegend=True,
    xaxis=dict(title="Document", tickangle=-45, automargin=True),
    yaxis=dict(title="Precision (%)", showgrid=True, gridcolor='lightgrey'),
    margin=dict(b=150),
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
    paper_bgcolor='white',
    plot_bgcolor='white',
)


fig3.update_traces(marker=dict(size=10))

# Add line connecting square markers (model 'o3-mini')
o3_df = calculate_tpr_precision(model_dfs)[calculate_tpr_precision(model_dfs)["model"] == "o3-mini"]
fig3.add_trace(go.Scatter(
    x=o3_df["file"],
    y=o3_df["precision"],
    mode="lines",
    name="",
    line=dict(dash="dash",width=1.5, color='lightgray'),
    showlegend=False,
))

# Add line connecting circle markers (model 'gpt-4.1-nano')
nano_df = calculate_tpr_precision(model_dfs)[calculate_tpr_precision(model_dfs)["model"] == "gpt-4.1-nano"]
fig3.add_trace(go.Scatter(
    x=nano_df["file"],
    y=nano_df["precision"],
    mode="lines",
    name="",
    line=dict(dash="dash", width=1.5, color='lightgray'),
    showlegend=False,
))

# Add line connecting diamond markers (model 'gpt-4o-mini')
o4o_df = calculate_tpr_precision(model_dfs)[calculate_tpr_precision(model_dfs)["model"] == "gpt-4o-mini"]
fig3.add_trace(go.Scatter(
    x=o4o_df["file"],
    y=o4o_df["precision"],
    mode="lines",
    name="",
    line=dict(dash="dash", width=1.5, color='lightgray'),
    showlegend=False,
))

# Draw lines beneath markers to prevent overlap
line_traces = [trace for trace in fig3.data if trace.mode == "lines"]
marker_traces = [trace for trace in fig3.data if trace.mode == "markers"]
fig3.data = tuple(line_traces + marker_traces)

fig3.update_traces(
    showlegend=False,
    marker_size=12,
    opacity=0.7,
    marker_line=dict(width=2, color="white")
)

fig3.show()

output_file_300pxC = (
    output_dir / "pcontrol_summary_figC.png"
)

fig3.write_image(
    str(output_file_300pxC),
    format="png",
    width=500,
    height=400,
    scale=6,
    engine="kaleido",
)

print(f"Saved 300px summary plot to {output_file_300pxC}")

# Only show the legend for the first plot (Completeness)
# Hide legend for all traces from the second plot (True Positive Rate)
for i, trace in enumerate(fig2.data):
    if hasattr(trace, "showlegend"):
        trace.showlegend = False
for i, trace in enumerate(fig3.data):
    if hasattr(trace, "showlegend"):
        trace.showlegend = False

fig_comb = make_subplots(
    rows=3,
    cols=1,
    subplot_titles=("(A) Completeness", "(B) Recall", "(C) Precision"),
    horizontal_spacing=0.1,
    vertical_spacing=0.15,
    shared_xaxes=True,
)

# Reduce the space between subplot titles and subplots
for i in range(3):
    fig_comb.layout.annotations[i].update(y=fig_comb.layout.annotations[i]['y'] + 0.02)  # decrease value to move titles closer to plots
fig_comb.add_traces(fig.data, rows=1, cols=1)
fig_comb.add_traces(fig2.data, rows=2, cols=1)
fig_comb.add_traces(fig3.data, rows=3, cols=1)
fig_comb.update_layout(
    title_text="",
    title_x=0.5,
    width=500,
    height=500,
    coloraxis = dict(colorscale=px.colors.sequential.Viridis),   # palette
    coloraxis_colorbar=dict(
        title=dict(
            text=r"$\overline{\cos\theta}$",
            side="right",
            font=dict(size=14),
        ),
        # tickvals=(((np.linspace(min_cos, max_cos, 5)*100).astype(int)/100)).tolist(),
        # ticktext=[f"{val:.2f}" for val in np.linspace(min_cos, max_cos, 5)],
        # use Viridis color scale
        ticks="inside",
        ticklen=5,
        tickwidth=1,
        len=0.33,  # 50% of plot height
        yanchor="top",  # "top", "middle", or "bottom"
        yref="paper",  # Use "paper" to position relative to the entire figure
        y=1.02,          # 0 (bottom) to 1 (top); adjust this value to move the colorbar up or down
        xanchor="left",
        x=1.02,
    ),
    legend=dict(
        title_text="",
        orientation="h",
        xref="paper",
        yref="paper",
        x=0.5,
        xanchor="center",
        y=1.1,
        yanchor="bottom",
        font=dict(size=11),
    ),
    paper_bgcolor='white',
    plot_bgcolor='white',
)
# fig_comb.update_xaxes(title_text="Document", row=1, col=1)
fig_comb.update_xaxes(title_text="ToxTemp Document", row=3, col=1, tickangle=0, automargin=True,tickmode="array", tickvals=calculate_tpr_precision(model_dfs)['file'].unique(), ticktext=[str(i) for i,_ in enumerate(calculate_tpr_precision(model_dfs)['file'].unique(),start=1)])
fig_comb.update_yaxes(title_text=r"$C\,\big/\,{\%}$", row=1, col=1,  showgrid=False, gridcolor='lightgrey')
fig_comb.update_yaxes(title_text=r"$R|_{\cos\theta>0.6}\,\big/\,{\%}$", row=2, col=1, range=[20, 100], showgrid=False, gridcolor='lightgrey')    
fig_comb.update_yaxes(title_text=r"$P|_{\cos\theta>0.6} \,\big/\,{\%}$", row=3, col=1, showgrid=False, gridcolor='lightgrey')    


fig_comb.write_image(
    str(output_dir / "pcontrol_summary_combined_fig.png"),
    format="png",
    width=485,
    height=500,
    scale=6,
    engine="kaleido",
)

print(f"Saved 300px summary plot to {output_dir / 'pcontrol_summary_combined_fig.png'}")
