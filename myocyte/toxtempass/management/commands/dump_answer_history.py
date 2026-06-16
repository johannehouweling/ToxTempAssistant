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
        parser.add_argument(
            "--scan", action="store_true",
            help="Aggregate: how many answers carry a non-blank user=None (LLM draft) "
                 "snapshot, split by era; dump example chains.",
        )
        parser.add_argument(
            "--classify", action="store_true",
            help="Dump every post-cutoff user=None draft snapshot (full-ish text + "
                 "question) to judge prose-draft vs placeholder.",
        )
        parser.add_argument("--exclude-emails", default="")

    def handle(self, *args: object, **options: object) -> None:
        """Run the dump/scan/classify inside a read-only transaction."""
        with transaction.atomic():
            if connection.vendor == "postgresql":
                with connection.cursor() as cur:
                    cur.execute("SET TRANSACTION READ ONLY")
            if options["classify"]:
                self._classify(options)
            elif options["scan"]:
                self._scan(options)
            else:
                self._run(options)

    def _scan(self, options: dict) -> None:
        """Across reviewed answers, count non-blank user=None snapshots (LLM drafts)."""
        from datetime import date

        w = self.stdout.write
        cutoff = date(2025, 9, 13)
        exclude = {
            e.strip().lower()
            for e in str(options["exclude_emails"]).split(",")
            if e.strip()
        }
        answers = list(
            Answer.objects.filter(
                accepted=True, assay__demo_lock=False, assay__demo_template=False,
                assay__demo_source__isnull=True,
            ).select_related("assay__study__investigation__owner")
        )
        answers = [
            a for a in answers
            if (getattr(a.assay.study.investigation.owner, "email", "") or "").lower()
            not in exclude
        ]
        ids = [a.id for a in answers]
        hist: dict[int, list] = {}
        for h in Answer.history.model.objects.filter(id__in=ids).values(
            "id", "answer_text", "history_type", "history_user_id", "history_date"
        ):
            hist.setdefault(h["id"], []).append(h)

        post = post_nulldraft = post_edited = pre = pre_nulldraft = 0
        examples = []
        for a in answers:
            rows = sorted(hist.get(a.id, []), key=lambda r: r["history_date"])
            nonblank = [r for r in rows if (r["answer_text"] or "").strip()]
            null_draft = [
                r for r in nonblank
                if r["history_type"] == "~" and r["history_user_id"] is None
            ]
            is_pre = a.assay.submission_date.date() < cutoff
            if is_pre:
                pre += 1
                pre_nulldraft += bool(null_draft)
            else:
                post += 1
                post_nulldraft += bool(null_draft)
                first = (nonblank[0]["answer_text"] or "").strip() if nonblank else ""
                if first and first != (a.answer_text or "").strip():
                    post_edited += 1
                if (null_draft or (first and first != (a.answer_text or "").strip())) \
                        and len(examples) < 4:
                    examples.append((a, rows))

        w("\n=== SCAN: is the LLM draft in version history? ===")
        w(f"reviewed accepted answers: {len(answers)}  (pre-cutoff {pre}, post {post})")
        w(f"PRE-cutoff with user=None draft snapshot:  {pre_nulldraft}/{pre}")
        w(f"POST-cutoff with user=None draft snapshot: {post_nulldraft}/{post}")
        w(f"POST-cutoff edited (first non-blank != final): {post_edited}/{post}")
        w("\n--- example post-cutoff chains (edited and/or null-user) ---")
        for a, rows in examples:
            w(f"\nAnswer {a.id} (assay {a.assay_id}, {a.assay.submission_date:%Y-%m-%d})")
            w(f"  LIVE (len {len(a.answer_text or '')}): \"{_prev(a.answer_text)}\"")
            for i, h in enumerate(rows):
                txt = h["answer_text"] or ""
                user = h["history_user_id"] if h["history_user_id"] is not None else "—"
                w(
                    f"    [{i}] {h['history_type']} user={user!s:>5} "
                    f"{h['history_date']:%Y-%m-%d %H:%M:%S} len={len(txt):>4}  "
                    f"\"{_prev(txt)}\""
                )
        w("")

    def _classify(self, options: dict) -> None:
        """Dump every post-cutoff user=None draft snapshot (draft vs placeholder)."""
        from datetime import date

        w = self.stdout.write
        cutoff = date(2025, 9, 13)
        exclude = {
            e.strip().lower()
            for e in str(options["exclude_emails"]).split(",")
            if e.strip()
        }
        answers = list(
            Answer.objects.filter(
                accepted=True, assay__demo_lock=False, assay__demo_template=False,
                assay__demo_source__isnull=True,
            ).select_related("assay__study__investigation__owner", "question")
        )
        answers = [
            a for a in answers
            if a.assay.submission_date.date() >= cutoff
            and (getattr(a.assay.study.investigation.owner, "email", "") or "").lower()
            not in exclude
        ]
        hist: dict[int, list] = {}
        for h in Answer.history.model.objects.filter(
            id__in=[a.id for a in answers]
        ).values("id", "answer_text", "history_type", "history_user_id", "history_date"):
            hist.setdefault(h["id"], []).append(h)

        found = []
        for a in answers:
            rows = sorted(hist.get(a.id, []), key=lambda r: r["history_date"])
            null_nb = [
                r for r in rows
                if (r["answer_text"] or "").strip()
                and r["history_type"] == "~" and r["history_user_id"] is None
            ]
            if null_nb:
                found.append((a, null_nb[0]["answer_text"]))

        long_ = sum(1 for _, d in found if len(d) > 150)
        short = sum(1 for _, d in found if len(d) < 50)
        per_assay: dict[int, int] = {}
        for a, _ in found:
            per_assay[a.assay_id] = per_assay.get(a.assay_id, 0) + 1
        w(f"\n=== CLASSIFY: {len(found)} post-cutoff user=None draft snapshots ===")
        w(f"  length: >150 (prose) {long_} | <50 (placeholder) {short} | "
          f"mid {len(found) - long_ - short}")
        w(f"  per assay: {per_assay}")
        w("\n--- each snapshot (Q → draft text) ---")
        for a, draft in found:
            same = "==final" if draft.strip() == (a.answer_text or "").strip() else "DIFF"
            w(f"\n[assay {a.assay_id}] Q: {_prev(a.question.question_text)}")
            w(f"   draft (len {len(draft)}, {same}): {draft[:160]!r}")
        w("")

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
