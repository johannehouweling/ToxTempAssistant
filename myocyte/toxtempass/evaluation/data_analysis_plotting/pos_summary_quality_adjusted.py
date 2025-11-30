import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

# Optional stats (used for correlation/tests below)
try:
    from scipy.stats import spearmanr, kruskal, mannwhitneyu

    _HAVE_SCIPY = True
except Exception:
    _HAVE_SCIPY = False
# from scipy.stats import gaussian_kde  # unused
from pathlib import Path
from toxtempass.evaluation.post_processing.utils import has_answer_not_found
import numpy as np

# from toxtempass.models import Question  # unused
from IPython.display import display

base_dir = Path(
    "/Users/johannehouweling/Desktop/ToxTempAssistant_Validation/Tier1_results"
)
model_dirs = ["gpt-4.1-nano", "gpt-4o-mini", "o3-mini"]

QUALITY_ORDER = pd.CategoricalDtype(categories=["Low", "Medium", "High"], ordered=True)

all_summaries = []
all_rows = []  # <-- collect raw rows to avoid double aggregation later

for model in model_dirs:
    folder = base_dir / model
    for file in folder.glob("tier1_comparison_*.csv"):
        print(f"\n=== Model: {model} | File: {file.stem} ===")
        df = pd.read_csv(file)

        # Clean & filter
        df = df.dropna(subset=["gtruth_answer"])
        df["llm_answer"] = df["llm_answer"].fillna("")
        df = df[~df["llm_answer"].apply(has_answer_not_found)]

        # Normalize & order quality labels
        df["gtruth_answer_quality_score"] = (
            df["gtruth_answer_quality_score"]
            .astype(str)
            .str.strip()
            .str.capitalize()  # "low"/"LOW" -> "Low"
            .astype(QUALITY_ORDER)
        )

        # Keep raw rows for exact later aggregation
        needed_cols = [
            "gtruth_answer_quality_score",
            "cos_similarity",
            "bert_precision",
        ]
        missing = set(needed_cols) - set(df.columns)
        if missing:
            raise KeyError(f"Missing columns in {file.name}: {missing}")

        df["_model"] = model
        df["_file"] = file.stem
        all_rows.append(
            df[
                [
                    "gtruth_answer_quality_score",
                    "cos_similarity",
                    "bert_precision",
                    "_model",
                    "_file",
                ]
            ]
        )

        # Per-file summary (no rounding here!)
        summary_df = (
            df.groupby("gtruth_answer_quality_score", observed=True)
            .agg(
                gtruth_answer_quality_score_count=(
                    "gtruth_answer_quality_score",
                    "count",
                ),
                cos_similarity_mean=("cos_similarity", "mean"),
                cos_similarity_std=("cos_similarity", "std"),
                cos_similarity_min=("cos_similarity", "min"),
                cos_similarity_max=("cos_similarity", "max"),
                bert_precision_mean=("bert_precision", "mean"),
            )
            .reset_index()
        )
        summary_df["model"] = model
        summary_df["file"] = file.stem
        all_summaries.append(summary_df)

        print("Summary by ground-truth answer quality score:")
        display(summary_df.round(3))

        # Histogram for the highest quality ("High")
        # Use the ordered categorical rather than .max()
        target_quality = "High"
        df_high = df[df["gtruth_answer_quality_score"] == target_quality]
        if not df_high.empty:
            fig = px.histogram(
                df_high,
                x="cos_similarity",
                title=f"Cosine Similarity Distribution (Quality {target_quality}) - {file.stem}",
                nbins=40,
            )
            fig.update_layout(bargap=0.1, xaxis=dict(range=[0, 1]))
            fig.show()
        else:
            print(f"No rows with quality={target_quality} in {file.stem}")

# Combined per-file summary (optional view)
if all_summaries:
    combined_summary = pd.concat(all_summaries, ignore_index=True)
    cols = ["model", "file"] + [
        c for c in combined_summary.columns if c not in ("model", "file")
    ]
    combined_summary = combined_summary[cols]
    print("\n=== Combined Summary Table (per-file aggregates) ===")
    display(combined_summary.round(3))

# Preferred: aggregate directly from raw rows (exact, no double-aggregation)
if all_rows:
    raw = pd.concat(all_rows, ignore_index=True)
    # Group by model × quality on per-row data
    agg_model_summary_exact = (
        raw.groupby(["_model", "gtruth_answer_quality_score"], observed=True)
        .agg(
            total_count=("cos_similarity", "size"),
            cos_similarity_mean=("cos_similarity", "mean"),
            cos_similarity_std=("cos_similarity", "std"),
            cos_similarity_min=("cos_similarity", "min"),
            cos_similarity_max=("cos_similarity", "max"),
            bert_precision_mean=("bert_precision", "mean"),
        )
        .reset_index()
        .rename(columns={"_model": "model"})
        .sort_values(["model", "gtruth_answer_quality_score"])
    )

    # 95% CI for the mean (normal approx)
    agg_model_summary_exact["ci95"] = 1.96 * (
        agg_model_summary_exact["cos_similarity_std"]
        / np.sqrt(agg_model_summary_exact["total_count"].clip(lower=1))
    )

    print("\n=== Aggregated Summary per Model and Quality (exact, from rows) ===")
    display(agg_model_summary_exact.round(3))

    # --- Effect of reference answer quality on cosine similarity ---
    # Ensure ordered category stays intact for plotting
    category_orders = {"gtruth_answer_quality_score": list(QUALITY_ORDER.categories)}

    # 1) Distribution views by quality (per model)
    fig_box = px.box(
        raw,
        x="gtruth_answer_quality_score",
        y="cos_similarity",
        color="_model",
        points="all",
        category_orders=category_orders,
        title="Cosine similarity by reference answer quality (per model)",
    )
    fig_box.update_layout(
        xaxis_title="Reference Answer Quality", yaxis_title=r"$\cos\theta$"
    )
    fig_box.show()

    color_map = {
        "gpt-4.1-nano": "#6A8DFF",
        "gpt-4o-mini": "#FF7660",
        "o3-mini": "#50D2A0"
    }

    fig_violin = go.Figure()

    for model in raw["_model"].unique():
        for quality in QUALITY_ORDER.categories:
            subset = raw[
                (raw["_model"] == model) & (raw["gtruth_answer_quality_score"] == quality)
            ]
            if not subset.empty:
                fig_violin.add_trace(
                    go.Violin(
                        x=[quality] * len(subset),
                        y=subset["cos_similarity"],
                        legendgroup=model,
                        # scalegroup=model,
                        jitter=0.7,
                        name=model,
                        scalemode="width",
                        meanline_visible=True,
                        points="all",
                        showlegend = True if quality == "Low" else False,
                        marker=dict(color=color_map.get(model), opacity=0.4, size=6),
                        line_color=color_map.get(model),
                    )
                )

    # Add text annotations showing N per model × quality
    for model in raw["_model"].unique():
        for num, quality in enumerate(QUALITY_ORDER.categories):
            subset = raw[
                (raw["_model"] == model) & (raw["gtruth_answer_quality_score"] == quality)
            ]
            if not subset.empty:
                n = len(subset)
                fig_violin.add_annotation(
                    x=[-0.1, 1, 2.1][num],
                    y=1.08,
                    text=f"n={n}",
                    showarrow=False,
                    xanchor="center",
                    yanchor="bottom",
                    font=dict(size=10, color=color_map.get(model)),
                    xshift={"gpt-4.1-nano": -60, "gpt-4o-mini": 0, "o3-mini": 60}[
                        model
                    ],  # horizontal offset per model
                ) 

    fig_violin.update_layout(
        yaxis_title=r"$\cos\theta$", 
        xaxis_title="Reference Answer Quality",
        template="plotly_white",
        violinmode="group",
        violingap=0.05,
        violingroupgap=0.05,
        showlegend=True,
    )
    fig_violin.update_layout(xaxis=dict(tickmode = 'array',
            tickvals = [-0.1, 1, 2.1],
            ticktext = QUALITY_ORDER.categories))
    fig_violin.show()

output_path = base_dir / "Grouped_ansqual"

fig_violin.write_image(str(output_path.with_name("cosine_similarity_by_quality.png")), format="png", width=900, height=600, scale=6, engine ="kaleido")

print(f"Saved corrected 300px violin plot to {output_path.with_name('cosine_similarity_by_quality.png')}")

# 2) Trend and non-parametric significance tests
raw = raw.copy()
raw["quality_ordinal"] = (
    raw["gtruth_answer_quality_score"].cat.codes + 1
)  # Low=1, Medium=2, High=3

if _HAVE_SCIPY:
    # Overall monotonic trend
    rho, pval = spearmanr(
        raw["quality_ordinal"], raw["cos_similarity"], nan_policy="omit"
    )
    print(f"Spearman ρ (overall quality vs cosθ): {rho:.3f}  (p={pval:.2e})")

    # Per-model trends
    for m, sub in raw.groupby("_model"):
        rho_m, p_m = spearmanr(
            sub["quality_ordinal"], sub["cos_similarity"], nan_policy="omit"
        )
        print(f"  {m}: ρ={rho_m:.3f} (p={p_m:.2e})")

    # Kruskal–Wallis across quality levels
    def _kruskal_report(df, label):
        groups = [
            df[df["gtruth_answer_quality_score"] == lvl]["cos_similarity"].dropna()
            for lvl in QUALITY_ORDER.categories
        ]
        groups = [g for g in groups if len(g) > 0]
        if len(groups) >= 2:
            stat, p = kruskal(*groups)
            print(
                f"Kruskal–Wallis across quality levels ({label}): H={stat:.2f}, p={p:.2e}, k={len(groups)}"
            )

    _kruskal_report(raw, "overall")
    for m, sub in raw.groupby("_model"):
        _kruskal_report(sub, f"model={m}")

    # Post-hoc pairwise comparisons (Dunn's test)
    try:
        import scikit_posthocs as sp
        import warnings

        # Suppress warnings from ties if they occur
        warnings.filterwarnings("ignore", category=RuntimeWarning)

        # Use raw values (cos_similarity) grouped by quality
        dunn = sp.posthoc_dunn(
            raw,
            val_col="cos_similarity",
            group_col="gtruth_answer_quality_score",
            p_adjust="holm"  # alternatives: 'bonferroni', 'fdr_bh'
        )

        print("\n=== Dunn’s post-hoc test (pairwise comparisons, Holm-corrected p-values) ===")
        print(dunn)

        # Also run Dunn's test with Bonferroni correction and print results
        dunn_bonf = sp.posthoc_dunn(
            raw,
            val_col="cos_similarity",
            group_col="gtruth_answer_quality_score",
            p_adjust="bonferroni"
        )
        print("\n=== Dunn’s post-hoc test (pairwise comparisons, Bonferroni-corrected p-values) ===")
        print(dunn_bonf)

    except ImportError:
        print("scikit-posthocs not installed: run `pip install scikit-posthocs` to enable Dunn's test.")

    # --- Effect sizes: Kruskal epsilon-squared and pairwise Cliff's delta ---
    def _kruskal_epsilon_squared(H, n, k):
        try:
            return float((H - k + 1) / (n - k)) if (n > k) else np.nan
        except Exception:
            return np.nan

    def _cliffs_delta_from_u(u_stat, n1, n2):
        # Rank-biserial correlation; equivalent to Cliff's delta for Mann–Whitney U
        return (2.0 * u_stat) / (n1 * n2) - 1.0

    # Compute Kruskal epsilon-squared overall and per model (re-compute H to capture n,k)
    def _kruskal_effect_size(df, label):
        groups = [
            df[df["gtruth_answer_quality_score"] == lvl]["cos_similarity"].dropna()
            for lvl in QUALITY_ORDER.categories
        ]
        groups = [g for g in groups if len(g) > 0]
        k = len(groups)
        n = sum(len(g) for g in groups)
        if k >= 2:
            H, p = kruskal(*groups)
            eps2 = _kruskal_epsilon_squared(H, n, k)
            return {
                "label": label,
                "H": float(H),
                "p": float(p),
                "k": int(k),
                "n": int(n),
                "epsilon_squared": float(eps2),
            }
        return {"label": label, "H": np.nan, "p": np.nan, "k": int(k), "n": int(n), "epsilon_squared": np.nan}

    eff_rows = []
    eff_rows.append(_kruskal_effect_size(raw, "overall"))
    for m, sub in raw.groupby("_model"):
        eff_rows.append(_kruskal_effect_size(sub, f"model={m}"))

    eff_df = pd.DataFrame(eff_rows)
    print("\n=== Kruskal effect size (epsilon squared) ===")
    print(eff_df.round(4))
    try:
        out_eff = base_dir / "kruskal_effect_sizes.csv"
        eff_df.to_csv(out_eff, index=False)
        print(f"Saved Kruskal effect sizes to {out_eff}")
    except Exception as e:
        print(f"Could not save Kruskal effect sizes: {e}")

    # Pairwise Cliff's delta overall and per model
    def _pairwise_cliffs_delta(df, label):
        pairs = [("Low", "Medium"), ("Medium", "High"), ("Low", "High")]
        rows = []
        for a, b in pairs:
            x = df[df["gtruth_answer_quality_score"] == a]["cos_similarity"].dropna().to_numpy()
            y = df[df["gtruth_answer_quality_score"] == b]["cos_similarity"].dropna().to_numpy()
            n1, n2 = len(x), len(y)
            if n1 > 0 and n2 > 0:
                # Use Mann–Whitney U to compute delta robustly
                try:
                    u_stat, _ = mannwhitneyu(x, y, alternative="two-sided")
                    delta = _cliffs_delta_from_u(u_stat, n1, n2)
                except Exception:
                    delta = np.nan
                rows.append({
                    "label": label,
                    "group1": a,
                    "group2": b,
                    "n1": int(n1),
                    "n2": int(n2),
                    "cliffs_delta": float(delta) if delta == delta else np.nan,
                })
        return pd.DataFrame(rows)

    cd_overall = _pairwise_cliffs_delta(raw, "overall")
    cd_list = [cd_overall]
    for m, sub in raw.groupby("_model"):
        cd_list.append(_pairwise_cliffs_delta(sub, f"model={m}"))

    cd_df = pd.concat(cd_list, ignore_index=True)
    print("\n=== Pairwise effect size (Cliff's delta) ===")
    print(cd_df.round(4))

    try:
        out_cd = base_dir / "cliffs_delta_pairwise.csv"
        cd_df.to_csv(out_cd, index=False)
        print(f"Saved Cliff's delta table to {out_cd}")
    except Exception as e:
        print(f"Could not save Cliff's delta table: {e}")
else:
    print(
        "SciPy not available: skipping Spearman/Kruskal tests. Install scipy to enable."
    )

# 3) Mean ±95% CI by model×quality (from exact aggregation)
mean_ci = agg_model_summary_exact.copy()
mean_ci["lower"] = mean_ci["cos_similarity_mean"] - mean_ci["ci95"]
mean_ci["upper"] = mean_ci["cos_similarity_mean"] + mean_ci["ci95"]
fig_err = px.scatter(
    mean_ci,
    x="gtruth_answer_quality_score",
    y="cos_similarity_mean",
    color="model",
    error_y="ci95",
    category_orders=category_orders,
    title="Mean cosθ ±95% CI by reference quality",
)
fig_err.update_traces(mode="lines+markers")
fig_err.update_layout(
    xaxis_title="Reference answer quality",
    yaxis_title="Mean cosine similarity (±95% CI)",
)
fig_err.show()
