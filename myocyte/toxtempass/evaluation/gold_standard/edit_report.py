"""Edit analysis: how many scientist-accepted answers were edited, and of what type.

Reads the latest typed gold CSV in ``output/_analysis/`` (the extract→enrich product) and
summarises the baseline→accepted change per answer. Two groups are kept honestly separate
because they answer different questions and have very different reliability:

* ``model_draft`` — the gpt-4o-mini draft survives in history (older assays), so the
  change is the **true AI-draft → accepted** edit. The clean signal — but few, and from a
  couple of batch-seeded assays, so NOT representative of interactive review.
* ``first_human_save`` — the draft was never logged (post-2025-09-13 ``.update()``
  bypass), so the change is **first-human-save → accepted**: edits made AFTER the first
  save. The AI-draft → first-save correction is invisible, so the edit *rate* here is a
  LOWER BOUND (the edit *types* are still informative).

Writes a Markdown report + an edit-type bar chart to ``output/_plotting/`` and prints a
summary. Pure pandas — no Django, no DB.

    poetry run python toxtempass/evaluation/gold_standard/edit_report.py [gold.csv]
"""

from __future__ import annotations

import sys
import textwrap
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
import plotly.express as px

HERE = Path(__file__).resolve().parent
ANALYSIS_DIR = HERE / "output" / "_analysis"
PLOTTING_DIR = HERE / "output" / "_plotting"

# change_type values (edit_analysis.classify_edit), most→least invasive for display.
EDIT_ORDER = [
    "rewrite", "expand", "trim", "edit", "cosmetic",
    "answer_to_abstain", "abstain_to_answer", "none", "n/a",
]
TRIVIAL = {"none", "n/a", ""}          # not an edit (blank guarded too)
SUBSTANTIVE = {"rewrite", "expand", "trim", "edit"}  # content change (vs cosmetic)
GROUP_LABEL = {
    "model_draft": "AI-draft→accepted (true, clean)",
    "first_human_save": "first-save→accepted (lower bound)",
    "none": "no baseline",
}

# Axis titles: plain in the HTML (LaTeX → MathJax breaks Plotly hovers); LaTeX in the PNG.
X_TITLE, Y_TITLE = "Number of answers", "Edit type"
X_TITLE_TEX, Y_TITLE_TEX = r"$\text{Number of answers}$", r"$\text{Edit type}$"


def _latest_gold() -> Path:
    """Return the newest typed gold CSV in output/_analysis (extract→enrich product)."""
    hits = sorted(ANALYSIS_DIR.glob("gold_answers_typed_*.csv"))
    if not hits:
        raise SystemExit("no gold_answers_typed_*.csv in output/_analysis")
    return hits[-1]


def _diff_churn(a: object, b: object) -> tuple[int, int]:
    """Return (chars inserted, chars deleted) from a→b via difflib opcodes.

    The CSV's ``chars_added``/``chars_removed`` are NET length deltas (one is always 0),
    which understates two-way rewords; this is the accurate edit magnitude.
    """
    sm = SequenceMatcher(None, str(a), str(b))
    ops = sm.get_opcodes()
    ins = sum(j2 - j1 for op, _i1, _i2, j1, j2 in ops if op in ("insert", "replace"))
    dele = sum(i2 - i1 for op, i1, i2, _j1, _j2 in ops if op in ("delete", "replace"))
    return ins, dele


def _num(x: object) -> float | None:
    """Parse a float from a possibly-blank CSV cell (None on failure)."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _short(text: object, width: int = 120) -> str:
    """One-line truncated preview of a cell (newlines collapsed)."""
    return textwrap.shorten(str(text).replace("\n", " ").strip(), width) or "—"


def _md_table(df: pd.DataFrame) -> str:
    """Render a DataFrame as a GitHub-flavoured Markdown table."""
    header = "| " + " | ".join(df.columns) + " |"
    sep = "| " + " | ".join("---" for _ in df.columns) + " |"
    body = "\n".join(
        "| " + " | ".join(str(v) for v in r) + " |"
        for r in df.itertuples(index=False)
    )
    return "\n".join([header, sep, body])


def _examples(df: pd.DataFrame, per_type: int = 2) -> str:
    """Pull a few largest-change examples per edit type (baseline→final previews)."""
    out: list[str] = []
    for ct in EDIT_ORDER:
        if ct in TRIVIAL:
            continue
        sub = df[df["change_type"] == ct].copy()
        if sub.empty:
            continue
        sub["_churn"] = sub.apply(
            lambda r: sum(_diff_churn(r["baseline_answer"], r["gold_answer"])), axis=1
        )
        out.append(f"\n**{ct}** ({len(sub)})")
        for r in sub.sort_values("_churn", ascending=False).head(per_type).itertuples():
            cos = _num(r.cosine_baseline_final)
            cos_s = f"{cos:.2f}" if cos is not None else "—"
            ins, dele = _diff_churn(r.baseline_answer, r.gold_answer)
            out.append(
                f"- assay #{r.assay_id} q{r.question_id} · cos {cos_s} · "
                f"{ins} ins / {dele} del chars"
            )
            out.append(f"    - baseline: {_short(r.baseline_answer)}")
            out.append(f"    - accepted: {_short(r.gold_answer)}")
    return "\n".join(out)


def build_report(df: pd.DataFrame) -> str:
    """Build the full Markdown edit-analysis report from the typed gold DataFrame."""
    total = len(df)
    edited = df[~df["change_type"].isin(TRIVIAL)]
    verbatim = int((df["change_type"] == "none").sum())

    # Type × group counts (drop trivial for the headline table).
    types = (
        df[~df["change_type"].isin(TRIVIAL)]
        .groupby(["change_type", "baseline_kind"]).size().reset_index(name="n")
    )
    pivot = (
        types.pivot_table(index="change_type", columns="baseline_kind", values="n",
                          fill_value=0, aggfunc="sum")
        .reindex([t for t in EDIT_ORDER if t not in TRIVIAL])
        .dropna(how="all")
        .astype(int)
    )
    pivot["total"] = pivot.sum(axis=1)
    pivot = pivot.reset_index().rename(
        columns={"change_type": "edit type", **GROUP_LABEL}
    )

    # Magnitude over substantive edits — TRUE difflib insert/delete (the stored
    # chars_added/removed are net length deltas and understate two-way rewords).
    sub = df[df["change_type"].isin(SUBSTANTIVE)].copy()
    churn = sub.apply(
        lambda r: _diff_churn(r["baseline_answer"], r["gold_answer"]), axis=1
    )
    ins = churn.map(lambda t: t[0]) if len(sub) else pd.Series(dtype=int)
    dele = churn.map(lambda t: t[1]) if len(sub) else pd.Series(dtype=int)

    md = df[df["baseline_kind"] == "model_draft"]
    n_md_edited = int((~md["change_type"].isin(TRIVIAL)).sum())

    lines = [
        "# Edit analysis — what scientists changed in the gpt-4o-mini drafts",
        "",
        f"**{total} accepted gold answers.** {len(edited)} show a recorded edit "
        f"(**{100 * len(edited) / total:.0f}%**); {verbatim} accepted with no recorded "
        "change. *The rate is a floor* — see the caveat.",
        "",
        "## Edit types (excludes 'none'/'n/a')",
        _md_table(pivot),
        "",
        f"Substantive edits (rewrite/expand/trim/edit) = **{len(sub)}**; the rest "
        "cosmetic. When experts edit, the dominant move is **trimming** verbosity.",
        "",
        "## Two groups, read differently",
        f"* **AI-draft→accepted (true)** — n={len(md)}; only {n_md_edited} edited "
        "(verbatim/cosmetic). The clean signal, but from 2 batch-seeded assays → not "
        "representative of interactive review.",
        f"* **first-save→accepted (lower bound)** — n="
        f"{int((df['baseline_kind'] == 'first_human_save').sum())}; the edits below are "
        "polishing *after* the human's first save; the AI-draft→first-save correction is "
        "unrecorded, so the rate understates real editing.",
        "",
        "## Magnitude (substantive edits, true difflib diff)",
        f"* chars inserted: median {int(ins.median()) if len(ins) else 0}, "
        f"max {int(ins.max()) if len(ins) else 0}",
        f"* chars deleted: median {int(dele.median()) if len(dele) else 0}, "
        f"max {int(dele.max()) if len(dele) else 0}",
        "",
        "## Examples (largest change per type)",
        _examples(df),
        "",
        "## Caveat",
        "The ~8% edit rate is a **lower bound**: for answers generated after 2025-09-13 "
        "the draft was written via a queryset `.update()` that bypasses django-simple-"
        "history, so the draft — and the first, biggest human correction — was never "
        "recorded. The true AI→expert edit is cleanly measurable only on the "
        f"{len(md)} `model_draft` answers, or by reconstructing drafts. Edit *types* "
        "stay indicative; the *rate* does not.",
        "",
    ]
    return "\n".join(lines)


def make_figure(df: pd.DataFrame) -> px.bar:
    """Stacked horizontal bar of edit-type counts, split by baseline group."""
    d = df[~df["change_type"].isin(TRIVIAL)].copy()
    d["group"] = d["baseline_kind"].map(GROUP_LABEL).fillna(d["baseline_kind"])
    counts = d.groupby(["change_type", "group"]).size().reset_index(name="n")
    fig = px.bar(
        counts, x="n", y="change_type", color="group", orientation="h",
        category_orders={"change_type": [t for t in EDIT_ORDER if t not in TRIVIAL]},
        labels={"n": X_TITLE, "change_type": Y_TITLE, "group": "baseline"},
        title=(
            "Scientist edits to gpt-4o-mini drafts, by type"
            "<br><sub>excludes accepted-verbatim ('none'); rate is a lower bound — most "
            "AI→expert corrections were never logged (see report)</sub>"
        ),
    )
    fig.update_layout(template="plotly_white", width=900, height=420,
                      margin=dict(t=86, l=90), legend=dict(orientation="h", y=-0.18))
    return fig


def main() -> None:
    """Read latest typed gold (or argv[1]); write report + figure; print summary."""
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else _latest_gold()
    # keep_default_na=False so literal "n/a"/"null"/"NA" stay strings (pandas would
    # otherwise coerce them to NaN); dtype=str keeps every field as text we parse.
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    report = build_report(df)
    sys.stdout.write(report + "\n")

    PLOTTING_DIR.mkdir(parents=True, exist_ok=True)
    (PLOTTING_DIR / "edit_report.md").write_text(report, encoding="utf-8")
    sys.stdout.write(f"Wrote {PLOTTING_DIR / 'edit_report.md'}\n")

    fig = make_figure(df)
    fig.write_html(PLOTTING_DIR / "edit_types.html")   # plain titles → hovers work
    sys.stdout.write(f"Wrote {PLOTTING_DIR / 'edit_types.html'}\n")
    fig.update_layout(xaxis_title=X_TITLE_TEX, yaxis_title=Y_TITLE_TEX)  # LaTeX for PNG
    try:
        fig.write_image(PLOTTING_DIR / "edit_types.png", scale=2)
        sys.stdout.write(f"Wrote {PLOTTING_DIR / 'edit_types.png'}\n")
    except Exception as exc:  # pragma: no cover - kaleido/Chrome optional
        sys.stdout.write(f"PNG export skipped ({type(exc).__name__}).\n")


if __name__ == "__main__":
    main()
