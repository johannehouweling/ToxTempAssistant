"""Backfill the ``answer_scenario`` label onto the Tier 3 answer CSVs.

Adds (or refreshes) a single ``answer_scenario`` column on every
``tier3_answers_*.csv`` under ``real_world/output/<experiment>/<model>/`` so the
answered / hedged / abstained / empty classification is materialized once at
the source. Values (from ``parse_answer``):

    answered  -- substantive content, no abstention marker
    hedged    -- abstention marker BUT substantive content
    abstained -- abstention marker, no substantive content
    empty     -- blank answer

Idempotent: re-running overwrites the column (never appends duplicates). The raw
``answer`` column is left untouched.

    cd myocyte && USE_POSTGRES=false DJANGO_DEBUG=true \
        poetry run python toxtempass/evaluation/real_world/enrich_answer_status.py [--dry-run]

The core helpers (``enrich_dataframe`` / ``iter_answer_csvs`` / ``summarize``) take the
parser as an argument and import nothing project-specific, so they're unit-testable;
only ``main()`` bootstraps Django to import the real ``parse_answer``.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Callable, Iterator

import pandas as pd

_NEW_COLS = ["answer_scenario"]

# Scenario columns for the breakdown table (short header -> scenario value).
SCENARIOS = [
    ("answer", "answered"),
    ("hedged", "hedged"),
    ("abstain", "abstained"),
    ("empty", "empty"),
]
# Non-trivial = has substantive content (completeness numerator); abstention = any
# not-found marker (clean abstention OR hedged).
_NON_TRIVIAL = {"answered", "hedged"}
_ABSTENTION = {"hedged", "abstained"}


def iter_answer_csvs(root: Path) -> Iterator[tuple[str, str, Path]]:
    """Yield ``(experiment, model, csv_path)`` for every tier3 answer CSV under root."""
    for exp_dir in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("_")):
        for model_dir in sorted(p for p in exp_dir.iterdir() if p.is_dir()):
            for csv_path in sorted(model_dir.glob("tier3_answers_*.csv")):
                yield exp_dir.name, model_dir.name, csv_path


def enrich_dataframe(
    df: pd.DataFrame, parse: Callable[[str], dict]
) -> tuple[pd.DataFrame, Counter]:
    """Return a copy of ``df`` with the ``answer_scenario`` column (re)written.

    ``parse`` is ``parse_answer``-compatible: ``str -> {"answer_scenario", ...}``.
    Also returns a Counter of scenarios for the breakdown table.
    """
    if "answer" not in df.columns:
        raise KeyError("expected an 'answer' column in the answer CSV")

    parsed = [parse(a) for a in df["answer"].fillna("").astype(str)]
    df = df.drop(columns=[c for c in _NEW_COLS if c in df.columns])  # idempotent refresh
    df["answer_scenario"] = [p["answer_scenario"] for p in parsed]

    # Place the new column directly after 'answer' for readability.
    cols = [c for c in df.columns if c not in _NEW_COLS]
    insert_at = cols.index("answer") + 1
    ordered = cols[:insert_at] + _NEW_COLS + cols[insert_at:]
    counts = Counter(p["answer_scenario"] for p in parsed)
    return df[ordered], counts


def _fmt_row(label_exp: str, label_model: str, counts: Counter) -> str:
    total = sum(counts.values())
    non_trivial = sum(counts.get(s, 0) for s in _NON_TRIVIAL)
    abstention = sum(counts.get(s, 0) for s in _ABSTENTION)
    cells = " ".join(f"{counts.get(s, 0):>7d}" for _, s in SCENARIOS)
    compl = 100 * non_trivial / total if total else 0
    return (f"{label_exp:18.18s} {label_model:32.32s} {cells} "
            f"{non_trivial:>8d} {abstention:>8d} {total:>6d} {compl:>6.1f}%")


def summarize(rows: list[tuple[str, str, Counter]]) -> str:
    """Per-(experiment, model) breakdown by ``answer_scenario`` + non_trivial/abstention.

    ``rows`` is per-file; counts (keyed by scenario) are aggregated to one line per
    (experiment, model). Column legend: answer = substantive, no marker; hedged =
    abstention marker WITH substantive content; abstain = marker, no content; empty =
    blank. non_triv = answered + hedged (the completeness numerator).
    """
    agg: dict[tuple[str, str], Counter] = {}
    order: list[tuple[str, str]] = []
    for experiment, model, counts in rows:
        key = (experiment, model)
        if key not in agg:
            agg[key] = Counter()
            order.append(key)
        agg[key].update(counts)

    header = (f"{'experiment':18s} {'model':32s} "
              + " ".join(f"{h:>7s}" for h, _ in SCENARIOS)
              + f" {'non_triv':>8s} {'abstent':>8s} {'total':>6s} {'compl%':>7s}")
    lines = [header, "-" * len(header)]
    grand = Counter()
    for experiment, model in order:
        counts = agg[(experiment, model)]
        grand.update(counts)
        lines.append(_fmt_row(experiment, model, counts))
    lines.append("-" * len(header))
    lines.append(_fmt_row("TOTAL", "", grand))
    return "\n".join(lines)


def run(root: Path, parse: Callable[[str], dict], dry_run: bool = False) -> list:
    """Enrich every answer CSV under ``root``; return per-file (experiment, model, Counter)."""
    rows = []
    for experiment, model, csv_path in iter_answer_csvs(root):
        df = pd.read_csv(csv_path)
        enriched, counts = enrich_dataframe(df, parse)
        if not dry_run:
            enriched.to_csv(csv_path, index=False)
        rows.append((experiment, model, counts))
    return rows


def main() -> None:
    import argparse
    import os
    import sys

    import django

    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myocyte.settings")
    django.setup()

    from toxtempass.evaluation.config import config as eval_config
    from toxtempass.evaluation.real_world.answer_utils import parse_answer

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=str(eval_config.real_world_output),
                    help="output root containing <experiment>/<model>/tier3_answers_*.csv")
    ap.add_argument("--dry-run", action="store_true",
                    help="classify and report but do not write the CSVs")
    args = ap.parse_args()

    root = Path(args.root)
    rows = run(root, parse_answer, dry_run=args.dry_run)
    print(summarize(rows))
    if args.dry_run:
        print("\n(dry run — no files written)")
    else:
        n = sum(sum(c.values()) for _, _, c in rows)
        print(f"\nEnriched {len(rows)} CSV(s), {n} rows with answer_scenario.")


if __name__ == "__main__":
    main()
