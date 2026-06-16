"""Thin management command for the gold_standard audit.

Delegates to ``toxtempass.evaluation.gold_standard.audit.run`` (mirrors how ``run_evals``
delegates to each control package). Read-only; extracts scientist-accepted gold answers
and, where the gpt-4o-mini draft survives in history, the draft→final edit-typing.
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from toxtempass.evaluation.gold_standard import audit


def _resolve_out(out: str) -> str:
    """Resolve the export path, embedding a timestamp in the filename.

    No ``--out`` → ``output/gold_answers_<ts>.csv``; a directory → a timestamped file in
    it; an explicit file path → used verbatim (caller owns the name).
    """
    ts = timezone.now().strftime("%Y%m%d_%H%M")
    name = f"gold_answers_{ts}.csv"
    if not out:
        return str(audit.OUTPUT_DIR / name)
    p = Path(out)
    return str(p / name) if p.is_dir() else out


class Command(BaseCommand):
    """Extract the gold answer set + gpt-4o-mini draft/edit-typing (read-only)."""

    help = "Extract scientist-accepted gold answers + draft/edit-typing (read-only)."

    def add_arguments(self, parser: CommandParser) -> None:
        """Register CLI options."""
        parser.add_argument(
            "--exclude-emails",
            default="",
            help="Comma-separated owner emails to drop (e.g. test accounts).",
        )
        parser.add_argument(
            "--min-accepted",
            type=int,
            default=1,
            help="Only assays with at least this many accepted answers (default 1).",
        )
        parser.add_argument(
            "--limit", type=int, default=None, help="Cap assays processed (quick run)."
        )
        parser.add_argument(
            "--out", default="", help="Path to write the gold + edit-analysis CSV."
        )

    def handle(self, *args: object, **options: object) -> None:
        """Run the audit and print the headline summary."""
        out_path = _resolve_out(str(options["out"]))
        summary = audit.run(
            {
                "exclude_emails": options["exclude_emails"],
                "min_accepted": options["min_accepted"],
                "limit": options["limit"],
                "out": out_path,
            }
        )
        w = self.stdout.write
        w("")
        w("GOLD-STANDARD EXTRACTION  (read-only)")
        w(f"  gold answers          : {summary['n_gold_answers']}")
        w(f"  assays                : {summary['n_assays']}")
        w(f"  draft in history      : {summary['n_draft_in_history']} (edit-typable)")
        w(f"  draft missing (≥09-13): {summary['n_draft_missing']} (needs re-run)")
        w("  edit types (where draft recoverable):")
        for etype, n in sorted(
            summary["edit_type_counts"].items(), key=lambda kv: -kv[1]
        ):
            w(f"    {etype:18} {n}")
        w(f"  wrote CSV → {out_path}")
        w("")
