"""Quick, READ-ONLY sufficiency check on scientist-reviewed (gold) answers in prod.

Answers "do we have enough ground truth right now, or do more people need to create
ToxTemps?" — it does NOT touch history, drafts, or edit-typing (that is the larger
`gold_standard` audit). For each non-demo assay it reports id, name, description, whether
it has context documents, how many answers a human accepted, and how many are real gold
(non-abstention, non-empty), with totals and a short sufficiency readout.

Document signals (both DB-only, no object-storage access):
  * docs  = distinct filenames in answers' ``answer_documents`` — proves context documents
            were used at generation (independent of file-storage consent).
  * files = distinct available ``FileAsset`` rows still linked — proves the source files
            are retrievable now (needed to reproduce / run a bake-off).

Read-only by construction: zero write-ORM calls, and the work runs inside a Postgres
``SET TRANSACTION READ ONLY`` transaction so any accidental write is rejected by the DB.

Examples:
    python manage.py assess_ground_truth
    python manage.py assess_ground_truth --exclude-emails a@x.org,b@y.org
    python manage.py assess_ground_truth --min-accepted 5 --out /app/ground_truth.csv

"""

from __future__ import annotations

import csv
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandParser
from django.db import connection, transaction
from django.db.models import Count, Q

from toxtempass import config
from toxtempass.models import Answer, Assay

NF = config.not_found_string


class Command(BaseCommand):
    """Print a read-only sufficiency snapshot of scientist-accepted gold answers."""

    help = "Quick read-only check of how much scientist-reviewed gold data exists."

    def add_arguments(self, parser: CommandParser) -> None:
        """Register CLI options."""
        parser.add_argument(
            "--exclude-emails",
            default="",
            help="Comma-separated emails; drop assays owned/created by these people.",
        )
        parser.add_argument(
            "--min-accepted",
            type=int,
            default=1,
            help="Only show assays with at least this many accepted answers (default 1).",
        )
        parser.add_argument(
            "--include-demo",
            action="store_true",
            help="Include demo assays (excluded by default).",
        )
        parser.add_argument(
            "--out",
            default="",
            help="Optional path to write a CSV (full name + description + counts).",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Run the assessment inside a read-only transaction."""
        with transaction.atomic():
            if connection.vendor == "postgresql":
                with connection.cursor() as cur:
                    cur.execute("SET TRANSACTION READ ONLY")
            self._run(options)

    def _docs_by_assay(self, assay_ids: list) -> dict:
        """Map assay id -> set of distinct document filenames cited across its answers."""
        docs: dict = defaultdict(set)
        pairs = Answer.objects.filter(assay_id__in=assay_ids).values_list(
            "assay_id", "answer_documents"
        )
        for assay_id, names in pairs:
            if isinstance(names, list):
                docs[assay_id].update(str(n) for n in names if n)
        return docs

    def _collect(self, options: dict) -> list[dict]:
        """Query + aggregate assays into a list of per-assay dicts (read-only)."""
        exclude = {
            e.strip().lower()
            for e in str(options["exclude_emails"]).split(",")
            if e.strip()
        }
        min_accepted = int(options["min_accepted"])

        qs = Assay.objects.all()
        if not options["include_demo"]:
            qs = qs.filter(
                demo_lock=False, demo_template=False, demo_source__isnull=True
            )
        qs = qs.select_related("study__investigation__owner", "created_by").annotate(
            n_answers=Count("answers", distinct=True),
            n_accepted=Count(
                "answers", filter=Q(answers__accepted=True), distinct=True
            ),
            n_notfound=Count(
                "answers",
                filter=Q(answers__accepted=True, answers__answer_text__icontains=NF),
                distinct=True,
            ),
            n_empty=Count(
                "answers",
                filter=Q(answers__accepted=True, answers__answer_text=""),
                distinct=True,
            ),
            n_files=Count(
                "answers__files",
                filter=Q(answers__files__status="available"),
                distinct=True,
            ),
        )

        assays = list(qs)
        docs_by_assay = self._docs_by_assay([a.id for a in assays])

        rows = []
        for a in assays:
            owner = getattr(a.study.investigation.owner, "email", "") or ""
            creator = getattr(a.created_by, "email", "") or ""
            if exclude and ({owner.lower(), creator.lower()} & exclude):
                continue
            if a.n_accepted < min_accepted:
                continue
            rows.append(
                {
                    "assay_id": a.id,
                    "title": a.title or "(untitled)",
                    "description": (a.description or "").replace("\n", " ").strip(),
                    "owner": owner or "—",
                    "creator": creator or "—",
                    "n_docs": len(docs_by_assay.get(a.id, ())),
                    "n_files": a.n_files,
                    "n_answers": a.n_answers,
                    "n_accepted": a.n_accepted,
                    "n_gold": a.n_accepted - a.n_notfound - a.n_empty,
                    "n_notfound": a.n_notfound,
                    "pct": (100 * a.n_accepted / a.n_answers) if a.n_answers else 0.0,
                    "date": a.submission_date.strftime("%Y-%m-%d"),
                    "status": a.status,
                }
            )
        rows.sort(key=lambda r: r["n_gold"], reverse=True)
        return rows

    def _run(self, options: dict) -> None:
        """Collect, print the report, and optionally write a CSV."""
        rows = self._collect(options)
        self._print(rows, options)
        if options["out"]:
            self._write_csv(rows, str(options["out"]))

    def _print(self, rows: list[dict], options: dict) -> None:
        """Render per-assay blocks (id + name + docs + counts), totals, readout."""
        w = self.stdout.write
        exclude = [
            e.strip() for e in str(options["exclude_emails"]).split(",") if e.strip()
        ]
        demo_note = "included" if options["include_demo"] else "excluded"
        w("")
        w(f"GROUND-TRUTH SUFFICIENCY  (read-only; demo assays {demo_note})")
        w("  [N] = assay id | docs = source files cited | files = files retrievable now")
        if exclude:
            w(f"  excluding owners/creators: {', '.join(exclude)}")
        w(f"  showing assays with >= {options['min_accepted']} accepted answer(s)")
        w("=" * 88)
        for r in rows:
            w(
                f"[{r['assay_id']:>5}] {r['title'][:66]}  ({r['owner']}, {r['date']}, "
                f"{r['status']})"
            )
            w(
                f"        answers {r['n_answers']:>3} | accepted {r['n_accepted']:>3} "
                f"({r['pct']:.0f}%) | gold {r['n_gold']:>3} | not-found "
                f"{r['n_notfound']:>3} | docs {r['n_docs']:>2} | files {r['n_files']:>2}"
            )
            if r["description"]:
                desc = r["description"]
                w(f"        desc: {desc[:150]}{'…' if len(desc) > 150 else ''}")
            w("-" * 88)

        n_assays = len(rows)
        total_accepted = sum(r["n_accepted"] for r in rows)
        total_gold = sum(r["n_gold"] for r in rows)
        total_nf = sum(r["n_notfound"] for r in rows)
        with_docs = sum(1 for r in rows if r["n_docs"])
        with_files = sum(1 for r in rows if r["n_files"])
        fully = sum(
            1 for r in rows if r["n_answers"] and r["n_accepted"] == r["n_answers"]
        )
        owners = len({r["owner"] for r in rows} - {"—"})
        w("")
        w("TOTALS")
        w(f"  reviewed assays (>= {options['min_accepted']} accepted) : {n_assays}")
        w(f"  fully-accepted assays                  : {fully}")
        w(f"  distinct owners/creators               : {owners}")
        w(f"  assays with context documents cited    : {with_docs}")
        w(f"  assays with files still retrievable    : {with_files}")
        w(f"  accepted answers                       : {total_accepted}")
        w(f"  └ real gold (non-abstention, non-empty): {total_gold}")
        w(f"  └ accepted abstentions ('not found')   : {total_nf}")
        w("")
        w(
            f"Sufficiency (your call): {total_gold} gold answers across {n_assays} "
            f"assays from {owners} people ({fully} fully reviewed; "
            f"{with_files} with retrievable source files)."
        )
        w("")

    def _write_csv(self, rows: list[dict], path: str) -> None:
        """Write the full per-assay table (incl. full description) to a CSV."""
        cols = [
            "assay_id", "title", "description", "owner", "creator", "n_docs",
            "n_files", "n_answers", "n_accepted", "n_gold", "n_notfound", "pct",
            "date", "status",
        ]
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=cols)
            writer.writeheader()
            for r in rows:
                writer.writerow({c: r[c] for c in cols})
        self.stdout.write(f"Wrote {path}")
