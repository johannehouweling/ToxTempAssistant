"""Thin command: locally fill the cosine edit-typing for a --no-cosine gold CSV.

Pairs with ``extract_gold_answers --no-cosine`` (prod, pure DB read, no OpenAI key). This
runs on your machine, where the OpenAI key + SHA embedding cache live. Logic lives in
``toxtempass.evaluation.gold_standard.enrich``.
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.utils import timezone

from toxtempass.evaluation.gold_standard import enrich


def _resolve_out(in_path: str, out: str) -> str:
    """Resolve the output CSV path (file verbatim; directory → timestamped name)."""
    ts = timezone.now().strftime("%Y%m%d_%H%M")
    if not out:
        p = Path(in_path)
        return str(p.with_name(f"{p.stem}_typed_{ts}.csv"))
    p = Path(out)
    return str(p / f"gold_typed_{ts}.csv") if p.is_dir() else out


class Command(BaseCommand):
    """Locally fill cosine + edit type for a --no-cosine gold CSV (uses OpenAI key)."""

    help = "Locally fill cosine edit-typing for a --no-cosine gold CSV."

    def add_arguments(self, parser: CommandParser) -> None:
        """Register CLI options."""
        parser.add_argument(
            "--in",
            dest="in_path",
            required=True,
            help="Path to the --no-cosine gold CSV from extract_gold_answers.",
        )
        parser.add_argument(
            "--out",
            default="",
            help="Output path (file used verbatim; a directory gets a timestamped name).",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Run the local enrichment and print the change-type distribution."""
        in_path = str(options["in_path"])
        if not Path(in_path).is_file():
            raise CommandError(f"--in file not found: {in_path}")
        out_path = _resolve_out(in_path, str(options["out"]))
        summary = enrich.run_enrich(in_path, out_path)
        w = self.stdout.write
        w("")
        w("GOLD COSINE ENRICHMENT  (local)")
        w(f"  rows                 : {summary['n_rows']}")
        w(f"  typed (had baseline) : {summary['n_typed']}")
        w("  change types (exact-delta subset):")
        for t, n in sorted(
            summary["change_type_counts_exact"].items(), key=lambda kv: -kv[1]
        ):
            w(f"    {t:18} {n}")
        w(f"  wrote CSV → {out_path}")
        w("")
