import json
import re

from django.conf import settings
from django.db import migrations, models

# Valid RISK-HUNT3R readiness colours (kept inline so the migration does not
# import the model layer, which can drift from this historical state).
_VALID = {"blue", "green", "yellow", "orange", "red"}


def _norm(text: str | None) -> str:
    """Whitespace-collapsed, lower-cased question text for robust matching."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def backfill_riskhunt3r_label(apps, schema_editor):
    """Colour existing questions from the ToxTemp_v1.json seed.

    The seed carries a ``riskhunt3r_db_label`` per question; match DB questions
    by their (normalised) text so already-seeded QuestionSets get categorised
    without a re-seed. Missing/odd seed file → no-op (field stays blank, which
    simply renders as uncategorised).
    """
    Question = apps.get_model("toxtempass", "Question")
    path = settings.BASE_DIR / "ToxTemp_v1.json"
    try:
        data = json.loads(path.read_text())
    except (FileNotFoundError, ValueError, OSError):
        return

    colour_by_text: dict[str, str] = {}

    def record(obj: dict) -> None:
        colour = obj.get("riskhunt3r_db_label", "")
        if colour in _VALID:
            colour_by_text[_norm(obj.get("question", ""))] = colour

    for section in data.get("sections", []):
        for subsec in section.get("subsections", []):
            if subsec.get("question"):
                record(subsec)
            for subq in subsec.get("subquestions", []):
                record(subq)

    if not colour_by_text:
        return

    for question in Question.objects.all().only(
        "id", "question_text", "riskhunt3r_db_label"
    ).iterator():
        colour = colour_by_text.get(_norm(question.question_text))
        if colour and question.riskhunt3r_db_label != colour:
            question.riskhunt3r_db_label = colour
            question.save(update_fields=["riskhunt3r_db_label"])


def noop(apps, schema_editor):
    """Reverse migration: the column is dropped, so nothing to undo."""


class Migration(migrations.Migration):

    dependencies = [
        ("toxtempass", "0034_demoassay"),
    ]

    operations = [
        migrations.AddField(
            model_name="question",
            name="riskhunt3r_db_label",
            field=models.CharField(
                blank=True,
                choices=[
                    ("blue", "Basic"),
                    ("green", "Level 1"),
                    ("yellow", "Level 2"),
                    ("orange", "Level 3"),
                    ("red", "Level 3+"),
                ],
                default="",
                help_text=(
                    "RISK-HUNT3R test-method-DB readiness category (rendered as a "
                    "colour). Drives the optional per-category progress breakdown. "
                    "Blank = uncategorised."
                ),
                max_length=10,
            ),
        ),
        migrations.RunPython(backfill_riskhunt3r_label, noop),
    ]
