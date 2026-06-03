"""Tier 3 data-quality report — checks for missing / empty answers.

Scans every generated ``output/<experiment>/<model>/tier3_answers_<assay>.csv`` and,
per (experiment, model, assay), reports:

  * total       — rows in the CSV
  * empty       — TRULY empty answers (blank text) → a generation ERROR (timeout /
                  rate-limit / crash), NOT a legitimate "not found"
  * not_found   — answered "not found" (prose ``not_found_string`` or structured
                  ``answerable:no`` / ``answer:null``) — a real, intentional non-answer
  * answered    — substantive answers
  * empty_pct   — empty / total
  * flag        — HIGH_EMPTY (>5% empty, likely rate-limit/error damage) and/or
                  MISSING_ROWS (fewer rows than other models for the same assay)

Run:
    cd myocyte && USE_POSTGRES=false DJANGO_DEBUG=true \
        poetry run python toxtempass/evaluation/real_world/data_quality.py

Writes ``output/_analysis/data_quality_<ts>.csv`` and prints a summary that
highlights the flagged (problematic) rows.
"""

import os
import sys
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myocyte.settings")
django.setup()

from datetime import datetime  # noqa: E402

import pandas as pd  # noqa: E402
from django.core.management.color import make_style  # noqa: E402

from toxtempass.evaluation.config import config as eval_config  # noqa: E402
from toxtempass.evaluation.real_world.answer_utils import parse_answer  # noqa: E402

style = make_style()

OUTPUT_ROOT = eval_config.real_world_output
ANALYSIS_DIR = OUTPUT_ROOT / "_analysis"

HIGH_EMPTY_PCT = 5.0  # flag a (model, assay) when >this share of answers are empty


def main() -> None:
    """Scan all generated CSVs and write/print a data-quality report."""
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for exp_dir in sorted(OUTPUT_ROOT.iterdir()):
        if not exp_dir.is_dir() or exp_dir.name.startswith("_"):
            continue
        for model_dir in sorted(p for p in exp_dir.iterdir() if p.is_dir()):
            for csv_path in sorted(model_dir.glob("tier3_answers_*.csv")):
                assay = csv_path.stem[len("tier3_answers_"):]
                df = pd.read_csv(csv_path).fillna("")
                answers = [str(a) for a in df.get("answer", pd.Series(dtype=str))]
                total = len(answers)
                empty = sum(1 for a in answers if not a.strip())
                not_found = sum(
                    1 for a in answers if a.strip() and parse_answer(a)["not_found"]
                )
                answered = total - empty - not_found
                rows.append(
                    {
                        "experiment": exp_dir.name,
                        "model": model_dir.name,
                        "assay": assay,
                        "total": total,
                        "empty": empty,
                        "not_found": not_found,
                        "answered": answered,
                        "empty_pct": round(100 * empty / total, 1) if total else 0.0,
                    }
                )

    if not rows:
        print(style.ERROR(f"No answer CSVs found under {OUTPUT_ROOT}."))
        return

    report = pd.DataFrame(rows)
    # Expected row count per (experiment, assay) = the max any model produced.
    expected = (
        report.groupby(["experiment", "assay"])["total"].transform("max")
    )

    def _flag(r: pd.Series, exp_max: int) -> str:
        flags = []
        if r["empty_pct"] > HIGH_EMPTY_PCT:
            flags.append("HIGH_EMPTY")
        if r["total"] < exp_max:
            flags.append("MISSING_ROWS")
        return ",".join(flags)

    report["flag"] = [
        _flag(r, exp_max) for (_, r), exp_max in zip(report.iterrows(), expected)
    ]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    out_path = ANALYSIS_DIR / f"data_quality_{timestamp}.csv"
    report.sort_values(["experiment", "model", "assay"]).to_csv(out_path, index=False)
    print(style.SUCCESS(f"Data-quality report → {out_path}"))

    # Per-model roll-up.
    _cols = ["total", "empty", "not_found", "answered"]
    roll = (
        report.groupby(["experiment", "model"])[_cols].sum().reset_index()
    )
    roll["empty_pct"] = (100 * roll["empty"] / roll["total"]).round(1)
    print("\n" + style.HTTP_INFO("Per-(experiment, model) totals:"))
    print(roll.to_string(index=False))

    flagged = report[report["flag"] != ""]
    if len(flagged):
        print("\n" + style.ERROR(f"⚠ {len(flagged)} flagged (experiment, model, assay):"))
        print(
            flagged.sort_values("empty_pct", ascending=False)[
                ["experiment", "model", "assay", "total", "empty", "empty_pct", "flag"]
            ].to_string(index=False)
        )
    else:
        print("\n" + style.SUCCESS("✓ No empty/missing-answer issues detected."))


if __name__ == "__main__":
    main()
