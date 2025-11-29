import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from pathlib import Path
from scipy.stats import gaussian_kde

from toxtempass.evaluation.post_processing.utils import has_answer_not_found
from toxtempass.models import Question

# --- Configuration ---------------------------------------------------------
# Corrected base_dir path ("Assistant" not "Assistanmt")
base_dir = Path("/Users/johannehouweling/Desktop/ToxTempAssistant_Validation/Tier1_results")
model_dirs = ["gpt-4.1-nano", "gpt-4o-mini", "o3-mini"]

# Consistent color mapping for models
color_map = {
    "gpt-4.1-nano": "#6A8DFF",
    "gpt-4o-mini": "#FF7660",
    "o3-mini": "#50D2A0",
}

nbins = 18

# --- Collect per-assay distributions --------------------------------------
assay_data: dict[str, dict[str, dict[str, np.ndarray]]] = {}

for model in model_dirs:
    folder = base_dir / model
    if not folder.exists():
        continue

    for file in folder.glob("tier1_comparison_*.csv"):
        df = pd.read_csv(file)

        passed_mask = (
            df["gtruth_answer"].notna()
            & df["gtruth_answer"].astype(bool)
            & df["llm_answer"].notna()
            & df["llm_answer"].astype(bool)
            & ~df["llm_answer"].apply(has_answer_not_found)
        )
        df_passed = df.loc[passed_mask].copy()
        if df_passed.empty:
            continue

        values = df_passed["cos_similarity"].astype(float).values

        # Map question text to IDs when possible; otherwise NA strings
        # Robust to duplicates (uses the first matching ID) and caches lookups
        _qid_cache: dict[str, str] = {}
        def _lookup_qid(qtext: str) -> str:
            if pd.isna(qtext):
                return pd.NA
            if qtext in _qid_cache:
                return _qid_cache[qtext]
            qid = (
                Question.objects
                .filter(question_text=qtext)
                .values_list("id", flat=True)
                .first()
            )
            _qid_cache[qtext] = str(qid) if qid is not None else pd.NA
            return _qid_cache[qtext]

        qids = df_passed["question"].apply(_lookup_qid).astype(str).values

        # Derive assay name from filename: "tier1_comparison_<ASSAY>_*.csv"
        stem = file.stem
        assay = stem[len("tier1_comparison_"):].rsplit("_", 1)[0].rstrip("_")

        assay_data.setdefault(assay, {})
        if model in assay_data[assay]:
            # If multiple files per assay-model, concatenate
            assay_data[assay][model]["values"] = np.concatenate(
                [assay_data[assay][model]["values"], values]
            )
            assay_data[assay][model]["qids"] = np.concatenate(
                [assay_data[assay][model]["qids"], qids]
            )
        else:
            assay_data[assay][model] = {"values": values, "qids": qids}

if not assay_data:
    raise SystemExit("No assay data found. Check base_dir and input CSVs.")

# --- Compute shared binning across all assays/models ----------------------
all_values = np.concatenate(
    [model_dict["values"] for assay_dict in assay_data.values() for model_dict in assay_dict.values()]
)

bin_edges = np.histogram(all_values, bins=nbins)[1]
bin_size = bin_edges[1] - bin_edges[0]

# Peak y across all histograms to use a consistent y-axis range
y_max = 0
for assay_dict in assay_data.values():
    for model_dict in assay_dict.values():
        counts, _ = np.histogram(model_dict["values"], bins=bin_edges)
        y_max = max(y_max, counts.max())

# --- Build figures per assay ---------------------------------------------
figs: list[go.Figure] = []

for assay, model_vals in assay_data.items():
    fig = go.Figure()

    # Add overlaid histograms, one per model
    for model in model_dirs:
        if model not in model_vals:
            continue
        vals = model_vals[model]["values"]

        fig.add_trace(
            go.Histogram(
                x=vals,
                xbins=dict(start=float(bin_edges[0]), end=float(bin_edges[-1]), size=float(bin_size)),
                name=model,
                marker_color=color_map[model],
                marker_line_color=color_map[model],
                marker_line_width=1,
                opacity=0.55,
                hovertemplate=(
                    "<b>Bin center</b>: %{x:.3f}<br>"
                    "<b>Count</b>: %{y}<extra>" + model + "</extra>"
                ),
            )
        )

    # Add KDE curves scaled to histogram counts
    x_kde = np.linspace(bin_edges[0], bin_edges[-1], 200)
    for model in model_dirs:
        if model not in model_vals:
            continue
        vals = model_vals[model]["values"]
        if len(vals) < 2:
            continue  # KDE needs >1 sample
        kde = gaussian_kde(vals)
        y_kde = kde(x_kde) * len(vals) * bin_size
        fig.add_trace(
            go.Scatter(
                x=x_kde,
                y=y_kde,
                mode="lines",
                opacity=0.8,
                line=dict(color=color_map[model], width=2),
                name=f"{model} KDE",
                showlegend=True,
            )
        )

    fig.update_layout(
        title_text=f"{assay}",
        title_x=0.5,
        xaxis_title=r"$\\cos\\theta$",
        yaxis_title="Frequency",
        barmode="overlay",
        template="plotly_white",
        plot_bgcolor="white",
        paper_bgcolor="white",
        xaxis=dict(showgrid=False, range=[float(bin_edges[0]), float(bin_edges[-1])]),
        yaxis=dict(showgrid=True, gridcolor="lightgrey", range=[0, float(y_max) * 1.1]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    fig.show()

    # Save high-resolution PNG per assay
    output_file = base_dir / f"{assay}_cossim_dist_highres.png"
    pio.write_image(
        fig,
        str(output_file),
        format="png",
        width=1600,
        height=1200,
        scale=3,
        engine="kaleido",
    )
    print(f"Saved high-res plot to {output_file}")

    figs.append(fig)
