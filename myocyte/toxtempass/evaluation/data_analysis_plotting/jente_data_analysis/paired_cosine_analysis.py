#!/usr/bin/env python3
from pathlib import Path
import glob
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")  # Safe for headless mode, still works in notebooks
import matplotlib.pyplot as plt

# --- CONFIG ---
BASE_DIR = Path(
    "/Users/johannehouweling/Desktop/ToxTempAssistant_Validation_FAIR/experiments/positive/analyses/common_subset_all_models/common_subset_per_doc"
)

# ==========================================================
# Data loading and pivot building
# ==========================================================
def load_combined_csvs(input_dir: Path) -> pd.DataFrame:
    files = sorted(glob.glob(str(input_dir / "*_combined.csv")))
    if len(files) != 8:
        raise FileNotFoundError(
            f"Expected 8 *_combined.csv files in {input_dir}, found {len(files)}.\n"
            f"Seen:\n- " + "\n- ".join(files)
        )
    dfs = []
    for f in files:
        df = pd.read_csv(f)
        df["assay"] = Path(f).stem.replace("_combined", "")
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)

def build_pivot(raw: pd.DataFrame) -> pd.DataFrame:
    req = [
        "assay", "question", "gtruth_answer",
        "llm_answer_gpt-4.1-nano", "llm_answer_gpt-4.1-nano_cos_similarity",
        "llm_answer_gpt-4o-mini",  "llm_answer_gpt-4o-mini_cos_similarity",
        "llm_answer_o3-mini",      "llm_answer_o3-mini_cos_similarity",
    ]
    missing = [c for c in req if c not in raw.columns]
    if missing:
        raise KeyError(f"Missing required columns: {missing}")

    pivot = raw[[
        "assay", "question", "gtruth_answer",
        "llm_answer_gpt-4.1-nano_cos_similarity",
        "llm_answer_gpt-4o-mini_cos_similarity",
        "llm_answer_o3-mini_cos_similarity",
        "llm_answer_gpt-4.1-nano",
        "llm_answer_gpt-4o-mini",
        "llm_answer_o3-mini",
    ]].copy()

    pivot = pivot.rename(columns={
        "llm_answer_gpt-4.1-nano_cos_similarity": "gpt-4.1-nano",
        "llm_answer_gpt-4o-mini_cos_similarity": "gpt-4o-mini",
        "llm_answer_o3-mini_cos_similarity": "o3-mini",
        "llm_answer_gpt-4.1-nano": "answer_gpt-4.1-nano",
        "llm_answer_gpt-4o-mini": "answer_gpt-4o-mini",
        "llm_answer_o3-mini": "answer_o3-mini",
    })

    for m in ["gpt-4.1-nano", "gpt-4o-mini", "o3-mini"]:
        pivot[m] = pd.to_numeric(pivot[m], errors="coerce")

    return pivot.dropna(subset=["gpt-4.1-nano", "gpt-4o-mini", "o3-mini"])

# ==========================================================
# Analysis
# ==========================================================
def run_pair_analysis(pivot: pd.DataFrame, out_dir: Path, top_n: int = 15, plots: bool = False) -> pd.DataFrame:
    out_dir.mkdir(parents=True, exist_ok=True)
    model_pairs = [
        ("o3-mini", "gpt-4o-mini"),
        ("o3-mini", "gpt-4.1-nano"),
        ("gpt-4o-mini", "gpt-4.1-nano"),
    ]
    rows = []
    for m1, m2 in model_pairs:
        diff = pivot[m1] - pivot[m2]
        try:
            shapiro_stat, shapiro_p = stats.shapiro(diff)
        except Exception:
            shapiro_stat, shapiro_p = np.nan, np.nan

        if pd.notna(shapiro_p) and shapiro_p > 0.05:
            t_stat, p_val = stats.ttest_rel(pivot[m1], pivot[m2])
            test_name, test_stat = "paired t-test", float(t_stat)
        else:
            w_stat, p_val = stats.wilcoxon(pivot[m1], pivot[m2], zero_method="wilcox")
            test_name, test_stat = "Wilcoxon signed-rank", float(w_stat)

        rows.append({
            "pair": f"{m1} vs {m2}",
            "mean_diff": float(diff.mean()),
            "median_diff": float(diff.median()),
            "shapiro_p": float(shapiro_p) if pd.notna(shapiro_p) else np.nan,
            "test": test_name,
            "test_stat": test_stat,
            "p_value": float(p_val),
            "n": int(diff.shape[0]),
        })

        abs_idx = diff.abs().sort_values(ascending=False).index
        top = pivot.loc[abs_idx, ["assay", "question", m1, m2, "gtruth_answer",
                                  "answer_gpt-4.1-nano", "answer_gpt-4o-mini", "answer_o3-mini"]].copy()
        top["diff_signed"] = diff.loc[abs_idx].values
        top["diff_abs"] = diff.abs().loc[abs_idx].values
        top = top.head(top_n).reset_index(drop=True)
        top.to_csv(out_dir / f"top_differences_{m1}_vs_{m2}.csv", index=False)

        if plots:
            plt.figure(figsize=(6, 4))
            plt.hist(diff.dropna(), bins=30)
            plt.title(f"Difference distribution: {m1} - {m2}")
            plt.xlabel("Cosine difference")
            plt.ylabel("Count")
            plt.tight_layout()
            plt.savefig(out_dir / f"hist_diff_{m1}_vs_{m2}.png", dpi=200)
            plt.close()

            fig = plt.figure(figsize=(6, 4))
            ax = fig.add_subplot(111)
            stats.probplot(diff.dropna(), dist="norm", plot=ax)
            ax.set_title(f"Q–Q plot: {m1} - {m2}")
            plt.tight_layout()
            plt.savefig(out_dir / f"qq_diff_{m1}_vs_{m2}.png", dpi=200)
            plt.close()

    summary = pd.DataFrame(rows)
    summary.to_csv(out_dir / "paired_tests_summary.csv", index=False)
    return summary

# ==========================================================
# Main runner for CLI or Notebook
# ==========================================================
def run_analysis(input_dir=BASE_DIR, output_dir="./paired_results", top_n=15, plots=False):
    raw = load_combined_csvs(Path(input_dir))
    pivot = build_pivot(raw)
    summary = run_pair_analysis(pivot, Path(output_dir), top_n=top_n, plots=plots)
    return summary

# ==========================================================
# CLI entry point
# ==========================================================
if __name__ == "__main__":
    import sys
    if any(arg.endswith(".json") or arg.startswith("--f=") for arg in sys.argv):
        # Likely running in Jupyter — skip argparse, just run with defaults
        print("Detected Jupyter/IPython, running with defaults...")
        summary_df = run_analysis()
        print(summary_df.to_string(index=False))
    else:
        import argparse
        parser = argparse.ArgumentParser(description="Paired question-level cosine analysis across LLMs.")
        parser.add_argument("-i", "--input_dir", type=Path, default=BASE_DIR,
                            help="Directory containing *_combined.csv files.")
        parser.add_argument("-o", "--output_dir", type=Path, default=Path("./paired_results"),
                            help="Directory to write outputs.")
        parser.add_argument("--top_n", type=int, default=15, help="Top |Δ| items per pair.")
        parser.add_argument("--plots", action="store_true", help="Save histogram + Q–Q plots per pair.")
        args = parser.parse_args()
        summary_df = run_analysis(args.input_dir, args.output_dir, top_n=args.top_n, plots=args.plots)
        print("\n=== Paired Tests Summary ===")
        print(summary_df.to_string(index=False))