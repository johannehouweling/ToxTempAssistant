"""READ-ONLY diagnostic: dump the full simple-history snapshot chain for a few answers.

Shows, per answer, every ``HistoricalAnswer`` row (oldest→newest) with its type,
user, date, text length and a preview — so we can SEE exactly what each recorded
version holds and whether the gpt-4o-mini draft is anywhere in history. Targets a
specific assay (``--assay-id``) or, by default, the newest non-demo assay; ``--oldest``
picks the earliest assay (pre-2025-09-13) for contrast.

    sudo docker exec djangoapp python manage.py dump_answer_history --limit 3
    sudo docker exec djangoapp python manage.py dump_answer_history --oldest --limit 2
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandParser
from django.db import connection, transaction

from toxtempass.models import Answer, Assay

PREVIEW = 90


def _prev(text: str) -> str:
    """One-line, truncated preview of a snapshot's text."""
    s = (text or "").replace("\n", " ").strip()
    return s[:PREVIEW] + ("…" if len(s) > PREVIEW else "")


class Command(BaseCommand):
    """Print the full history snapshot chain for a sample of accepted answers."""

    help = "Read-only: dump each answer's simple-history snapshot chain (text + meta)."

    def add_arguments(self, parser: CommandParser) -> None:
        """Register CLI options."""
        parser.add_argument("--assay-id", type=int, default=None)
        parser.add_argument("--limit", type=int, default=3)
        parser.add_argument(
            "--oldest", action="store_true", help="Use the earliest assay (pre-cutoff)."
        )

    def handle(self, *args: object, **options: object) -> None:
        """Run the dump inside a read-only transaction."""
        with transaction.atomic():
            if connection.vendor == "postgresql":
                with connection.cursor() as cur:
                    cur.execute("SET TRANSACTION READ ONLY")
            self._run(options)

    def _run(self, options: dict) -> None:
        """Resolve the target assay + answers and print each history chain."""
        w = self.stdout.write
        assays = Assay.objects.filter(
            demo_lock=False, demo_template=False, demo_source__isnull=True
        )
        if options["assay_id"]:
            assay = assays.filter(id=options["assay_id"]).first()
        else:
            order = "submission_date" if options["oldest"] else "-submission_date"
            assay = assays.order_by(order).first()
        if not assay:
            w("No matching assay.")
            return

        w(f"\nASSAY {assay.id} — {assay.title}  ({assay.submission_date:%Y-%m-%d})")
        w("=" * 96)
        answers = (
            Answer.objects.filter(assay=assay, accepted=True)
            .select_related("question")
            .order_by("question_id")[: int(options["limit"])]
        )
        for a in answers:
            w(f"\nAnswer {a.id}  ·  Q: {_prev(a.question.question_text)}")
            w(f"  LIVE gold (len {len(a.answer_text or '')}): \"{_prev(a.answer_text)}\"")
            rows = list(a.history.all().order_by("history_date", "history_id"))
            w(f"  history: {len(rows)} snapshot(s) (oldest → newest):")
            for i, h in enumerate(rows):
                txt = h.answer_text or ""
                user = h.history_user_id if h.history_user_id is not None else "—"
                w(
                    f"    [{i}] {h.history_type} user={user!s:>5} "
                    f"{h.history_date:%Y-%m-%d %H:%M:%S} acc={h.accepted!s:<5} "
                    f"len={len(txt):>4}  \"{_prev(txt)}\""
                )
        w("")
