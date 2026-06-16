"""Presentable status table of the scientist-reviewed gold ToxTemp answers.

Reads the latest typed gold CSV in ``output/_analysis/`` (or a path given as argv[1]) and
prints a per-assay Markdown table + a one-line summary, writing them to
``output/_plotting/gold_status_table.{md,html,png}`` for slides. Pure pandas — no Django.

    poetry run python toxtempass/evaluation/gold_standard/status_table.py [gold.csv]
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

HERE = Path(__file__).resolve().parent
ANALYSIS_DIR = HERE / "output" / "_analysis"      # gold CSVs live here
PLOTTING_DIR = HERE / "output" / "_plotting"      # figures written here
QUESTIONNAIRE = 77  # ToxTemp question count (completeness denominator)


def _latest_gold() -> Path:
    """Newest typed gold CSV in output/_analysis (the extract→enrich product)."""
    hits = sorted(ANALYSIS_DIR.glob("gold_answers_typed_*.csv"))
    if not hits:
        raise SystemExit(
            "no gold_answers_typed_*.csv in output/_analysis (run extract + enrich first)"
        )
    return hits[-1]

# Email domain → readable institute label (for a multi-institute workshop).
INSTITUTE = {
    "rivm.nl": "RIVM", "iuf-duesseldorf.de": "IUF Düsseldorf", "tno.nl": "TNO",
    "uu.nl": "Utrecht U.", "swansea.ac.uk": "Swansea U.", "list.lu": "LIST",
    "recetox.muni.cz": "RECETOX", "kuleuven.be": "KU Leuven", "empa.ch": "Empa",
    "uniroma2.it": "Rome Tor Vergata", "nmbu.no": "NMBU", "kist-europe.de": "KIST Europe",
    "ait.ac.at": "AIT", "kist.re.kr": "KIST",
}


def _institute(email: str) -> str:
    """Map an owner email to a readable institute label (fallback: the domain)."""
    domain = str(email).split("@")[-1].lower()
    return INSTITUTE.get(domain, domain or "—")


def build(csv_path: Path) -> tuple[str, str]:
    """Return (markdown_table, summary_line) for the gold CSV."""
    df = pd.read_csv(csv_path).fillna("")
    df["institute"] = df["owner_email"].map(_institute)
    df["is_nf"] = df["is_not_found"].astype(str).str.lower().isin(["true", "1", "1.0"])

    rows = []
    for (title, inst), g in df.groupby(["assay_title", "institute"]):
        accepted = len(g)
        nf = int(g["is_nf"].sum())
        rows.append(
            {
                "Assay": title[:42],
                "Institute": inst,
                # Expert answers = substantive accepted; "Not found" = reviewed but no
                # answer in the docs; Reviewed % = share of the 77-question questionnaire.
                "Expert answers": accepted - nf,
                '"Not found"': nf,
                "Reviewed (%)": round(100 * accepted / QUESTIONNAIRE),
            }
        )
    tbl = pd.DataFrame(rows).sort_values(
        ["Expert answers", "Reviewed (%)"], ascending=False
    ).reset_index(drop=True)
    tbl.insert(0, "#", range(1, len(tbl) + 1))

    header = "| " + " | ".join(tbl.columns) + " |"
    sep = "| " + " | ".join("---" for _ in tbl.columns) + " |"
    body = "\n".join(
        "| " + " | ".join(str(v) for v in r) + " |" for r in tbl.itertuples(index=False)
    )
    md = "\n".join([header, sep, body])

    n_assays = len(tbl)
    n_inst = df["institute"].nunique()
    n_people = df["owner_email"].nunique()
    total_acc = len(df)
    total_gold = int((~df["is_nf"]).sum())
    total_nf = int(df["is_nf"].sum())
    summary = (
        f"**{total_gold} expert-validated answers** across **{n_assays} assays** from "
        f"**{n_people} scientists** at **{n_inst} institutes** "
        f"({total_acc} accepted total; {total_nf} confirmed 'not found')."
    )
    return md, summary, tbl


def _green(pct: float) -> str:
    """Light→dark green shade for a 0–100 'reviewed' value (slide-friendly highlight)."""
    t = max(0.0, min(1.0, pct / 100))
    return f"rgb({int(232 - 150 * t)},{int(245 - 75 * t)},{int(233 - 150 * t)})"


def make_table_figure(tbl: pd.DataFrame, summary: str) -> go.Figure:
    """Render the per-assay table as a styled Plotly figure (PNG/HTML for slides)."""
    n = len(tbl)
    zebra = ["#f4f7f8" if i % 2 else "#ffffff" for i in range(n)]
    reviewed = [_green(v) for v in tbl["Reviewed (%)"]]
    fill = [zebra, zebra, zebra, zebra, zebra, reviewed]  # one entry per column
    fig = go.Figure(
        go.Table(
            columnwidth=[0.5, 5.2, 2.3, 1.7, 1.4, 1.6],
            header=dict(
                values=[f"<b>{c}</b>" for c in tbl.columns],
                fill_color="#1f4e5f", font=dict(color="white", size=13),
                align="left", height=34,
            ),
            cells=dict(
                values=[tbl[c].tolist() for c in tbl.columns],
                fill_color=fill, align="left", height=25, font=dict(size=12),
            ),
        )
    )
    fig.update_layout(
        title=dict(
            text=(
                "Gold-standard ToxTemp answers — workshop result"
                f"<br><sub>{summary.replace('**', '')}</sub>"
            ),
            x=0.01, font=dict(size=18),
        ),
        width=960, height=130 + 26 * n, margin=dict(l=12, r=12, t=86, b=12),
        template="plotly_white",
    )
    return fig


def main() -> None:
    """Print the markdown table + write the .md and a styled PNG/HTML figure."""
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else _latest_gold()
    md, summary, tbl = build(csv_path)
    title = "# Gold-standard ToxTemp answers — workshop result"
    out = f"{title}\n\n{summary}\n\n{md}\n"
    sys.stdout.write(out + "\n")
    out_dir = PLOTTING_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "gold_status_table.md").write_text(out, encoding="utf-8")
    sys.stdout.write(f"Wrote {out_dir / 'gold_status_table.md'}\n")

    fig = make_table_figure(tbl, summary)
    fig.write_html(out_dir / "gold_status_table.html")
    sys.stdout.write(f"Wrote {out_dir / 'gold_status_table.html'}\n")
    try:
        fig.write_image(out_dir / "gold_status_table.png", scale=2)
        sys.stdout.write(f"Wrote {out_dir / 'gold_status_table.png'}\n")
    except Exception as exc:  # pragma: no cover - kaleido/Chrome optional
        sys.stdout.write(f"PNG export skipped ({type(exc).__name__}).\n")


if __name__ == "__main__":
    main()
