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

    No ``--out`` → ``output/_analysis/gold_answers_<ts>.csv``; a directory → a timestamped
    file in it; an explicit file path → used verbatim (caller owns the name).
    """
    ts = timezone.now().strftime("%Y%m%d_%H%M")
    name = f"gold_answers_{ts}.csv"
    if not out:
        return str(audit.ANALYSIS_DIR / name)
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
        parser.add_argument(
            "--no-cosine",
            action="store_true",
            help="Pure DB read — skip embeddings/cosine (no OpenAI key needed). Fill the "
            "edit-typing afterwards, locally, with enrich_gold_cosines.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Run the audit and print the headline summary."""
        out_path = _resolve_out(str(options["out"]))
        no_cosine = bool(options["no_cosine"])
        summary = audit.run(
            {
                "exclude_emails": options["exclude_emails"],
                "min_accepted": options["min_accepted"],
                "limit": options["limit"],
                "out": out_path,
                "no_cosine": no_cosine,
            }
        )
        w = self.stdout.write
        w("")
        w("GOLD-STANDARD EXTRACTION  (read-only)")
        w(f"  gold answers                      : {summary['n_gold_answers']}")
        w(f"  assays                            : {summary['n_assays']}")
        w(f"  delta EXACT (model draft recovered): {summary['n_delta_exact']}")
        w(f"  delta LOWER-BOUND (1st human save) : {summary['n_delta_lower_bound']}")
        if no_cosine:
            w("  edit-typing                       : DEFERRED (--no-cosine, no API)")
            w("    next, locally (where the OpenAI key lives), run:")
            w("      manage.py enrich_gold_cosines --in <this>.csv --out <typed>.csv")
        else:
            w("  change types (exact-delta subset):")
            for t, n in sorted(
                summary["change_type_counts_exact"].items(), key=lambda kv: -kv[1]
            ):
                w(f"    {t:18} {n}")
        w(f"  wrote CSV → {out_path}")
        w("")
