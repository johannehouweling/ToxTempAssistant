import json
from pathlib import Path

import pandas as pd
from plotly import express as px
from myocyte.settings import BASE_DIR

base_dir_tier2 = BASE_DIR / "toxtempass/evaluation/negative_control/output"

def _get_model_file(model: str) -> Path:
    model_folder = base_dir_tier2 / model
    json_paths = sorted(model_folder.glob("*.json"))
    if not json_paths:
        raise FileNotFoundError(f"No Tier2 JSON found for model '{model}' in {model_folder}")
    return json_paths[0]

model_files = {model: _get_model_file(model) for model in ["gpt-4.1-nano", "gpt-4o-mini", "o3-mini"]}

def map_cont_rating_to_discrete(num: int) -> str:
    """Map."""

    if num == 0:
        return "Low"

    if num == 1:
        return "Medium"

    if num == 2:
        return "High"


def extract_question_text(failures, n=50) -> str:
    return [
        (
            elem["question_text"][:n] + "<br>"
            if len(elem["question_text"]) > n
            else elem["question_text"]
        )
        for elem in failures
    ]


dfs = []
for model_name, file_path in model_files.items():
    with Path(file_path).open("r") as fp:
        data = json.load(fp)

    df = pd.DataFrame(data["records"])
    df = df.sort_values(by="LLM_challenge_level")
    df["expected_challenge_level"] = df["LLM_challenge_level"].map(map_cont_rating_to_discrete)
    df = df.reset_index(drop=True)
    df["title_dummy"] = (df.index + 1).astype(str)
    df["failures_question_texts"] = df["failures"].map(extract_question_text)
    df["model_name"] = model_name
    dfs.append(df)

df_all = pd.concat(dfs, ignore_index=True)

# Explicit mapping so shapes stay consistent
symbol_map = {
    "gpt-4.1-nano": "circle",
    "gpt-4o-mini": "diamond",
    "o3-mini": "square",
}

fig = px.scatter(
    df_all,
    x="title_dummy",
    y="pass_rate",
    hover_data=["file", "failures_question_texts"],
    color="expected_challenge_level",
    color_discrete_map={
        "Low": "green",
        "Medium": "orange",
        "High": "red",
    },
    symbol="model_name",
    symbol_map=symbol_map,
    labels={
        "expected_challenge_level": "Expected Difficulty",
    }
)
# Hide automatic legend entries from the main scatter
fig.update_traces(
    showlegend=False,
    marker_size=12,
    opacity=0.7,
    marker_line=dict(width=2, color="white")
)


import plotly.graph_objects as go

# Add model legend entries with grouping title
model_written = False
for model_name, symbol in zip(["gpt-4.1-nano", "gpt-4o-mini", "o3-mini"], ["circle", "diamond", "square"]):
    trace_kwargs = dict(
        x=[None],
        y=[None],
        mode="markers",
        marker=dict(symbol=symbol, color="black", size=10, opacity=0.7),
        name=model_name,
        legendgroup="Model",
        showlegend=True,
    )
    if not model_written:
        trace_kwargs["legendgrouptitle"] = dict(text="Model")
        model_written = True
    fig.add_trace(go.Scatter(**trace_kwargs))

# Add difficulty legend entries with grouping title
diff_written = False
for expected_challenge_level, color in zip(df_all["expected_challenge_level"].unique(), ["green", "orange", "red"]):
    trace_kwargs = dict(
        x=[None],
        y=[None],
        mode="markers",
        marker=dict(symbol="square", color=color, size=25, opacity=0.7),
        name=expected_challenge_level,
        legendgroup="Expected Difficulty",
        showlegend=True,
    )
    if not diff_written:
        trace_kwargs["legendgrouptitle"] = dict(text="Expected Difficulty")
        diff_written = True
    fig.add_trace(go.Scatter(**trace_kwargs))

fig.update_layout(
    title=dict(
        text="Specificity",
        x=0.5,
        y=0.97,
        yref="container",
        automargin=True,
        xanchor="center",
        yanchor="top",
    ),
    margin=dict(t=130),
    xaxis=dict(title="Out-of-scope Document", showgrid=False),
    yaxis=dict(title=r"$Sp\,\big/\,{\%}$", showgrid=True, gridcolor="lightgrey", zeroline=False),
    legend=dict(
        orientation="h",
        xref="paper",
        yref="paper",
        y=1.02,
        x=0.5,
        yanchor="bottom",
        xanchor="center",
        font=dict(size=11),
        # itemsizing="constant"
    ),
    legend_title_text="",
    paper_bgcolor='white',
    plot_bgcolor='white',
)



# Add lines connecting scatter plot dots per model (same style as Tier 1)
# Ensure points are connected in x-order
for _model in ["gpt-4.1-nano", "gpt-4o-mini", "o3-mini"]:
    _m_df = (
        df_all[df_all["model_name"] == _model]
        .sort_values(by="title_dummy")
    )
    fig.add_trace(go.Scatter(
        x=_m_df["title_dummy"],
        y=_m_df["pass_rate"],
        mode="lines",
        name=f"{_model} line",
        line=dict(dash="dash", width=1.5, color="lightgray"),
        showlegend=False,
    ))

# Draw lines beneath markers to prevent overlap
line_traces = [trace for trace in fig.data if getattr(trace, "mode", None) == "lines"]
marker_traces = [trace for trace in fig.data if getattr(trace, "mode", None) == "markers"]
fig.data = tuple(line_traces + marker_traces)

fig.show()
# Export figure as PNG (requires `pip install -U kaleido`)
output_dir = BASE_DIR / "toxtempass" / "evaluation" / "plots"
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / "ncontrol_summary_fig.png"

fig.write_image(
    str(output_file),
    format="png",
    width=600,
    height=400,
    scale=6,
    engine="kaleido",
)

print(f"Saved summary plot to {output_file}")
