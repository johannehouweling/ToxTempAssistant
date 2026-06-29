"""Tests for the RISK-HUNT3R readiness category (per-question colour) and the
per-category accepted-answers progress breakdown."""

import pytest

from toxtempass.models import Question
from toxtempass.tests.fixtures.factories import (
    AnswerFactory,
    AssayFactory,
    PersonFactory,
    QuestionFactory,
    SubsectionFactory,
)
from toxtempass.views import _coerce_riskhunt3r_label, create_questionset_from_json

# ---------------------------------------------------------------------------
# _coerce_riskhunt3r_label
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["blue", "green", "yellow", "orange", "red"])
def test_coerce_accepts_known_colours(value):
    assert _coerce_riskhunt3r_label(value) == value


@pytest.mark.parametrize("value", ["", "oragne", "purple", None, 5, "BLUE"])
def test_coerce_rejects_unknown_values(value):
    assert _coerce_riskhunt3r_label(value) == ""


# ---------------------------------------------------------------------------
# Assay.accepted_by_riskhunt3r_label
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAcceptedByRiskHunt3rLabel:
    def test_empty_when_no_answers(self):
        assay = AssayFactory.create()
        assert assay.accepted_by_riskhunt3r_label == []

    def test_breakdown_counts_only_accepted_and_excludes_uncategorised(self):
        assay = AssayFactory.create()
        # One shared subsection so a single QuestionSet backs all questions; an
        # explicit label avoids the v{n} factory sequence colliding with the
        # migration-seeded "v1" QuestionSet.
        subsection = SubsectionFactory.create(section__question_set__label="rhbrk")

        def q(colour):
            return QuestionFactory.create(
                subsection=subsection, riskhunt3r_db_label=colour
            )

        q_blue1, q_blue2 = q("blue"), q("blue")
        q_green = q("green")
        q_red = q("red")
        q_uncat = q("")

        AnswerFactory.create(assay=assay, question=q_blue1, accepted=True)
        # not accepted but a real answer -> "drafted" (like the main bar)
        AnswerFactory.create(
            assay=assay, question=q_blue2, accepted=False, answer_text="a draft"
        )
        AnswerFactory.create(assay=assay, question=q_green, accepted=True)
        AnswerFactory.create(
            assay=assay, question=q_red, accepted=False, answer_text="a draft"
        )
        # An uncategorised question is its own (blank) label, not in ORDER, so it
        # contributes to no level's counts.
        AnswerFactory.create(assay=assay, question=q_uncat, accepted=True)

        segs = assay.accepted_by_riskhunt3r_label
        by = {s["value"]: s for s in segs}

        # always 5 cells in gradient order (yellow/orange have no questions here
        # → empty cells, not omitted)
        assert [s["value"] for s in segs] == [
            "blue",
            "green",
            "yellow",
            "orange",
            "red",
        ]

        # each level's own accepted / drafted / total, plus the within-bar fill
        # percentages (accepted pct + drafted draft_pct)
        b, g, r = by["blue"], by["green"], by["red"]
        assert (b["accepted"], b["drafted"], b["total"]) == (1, 1, 2)
        assert (b["pct"], b["draft_pct"]) == (50, 50)  # half accepted, half drafted
        assert (g["accepted"], g["drafted"], g["total"]) == (1, 0, 1)
        assert (g["pct"], g["draft_pct"]) == (100, 0)  # fully accepted
        assert (r["accepted"], r["drafted"], r["total"]) == (0, 1, 1)
        assert (r["pct"], r["draft_pct"]) == (0, 100)  # fully drafted, none accepted
        # a level with no questions is an empty bar
        y = by["yellow"]
        assert (y["total"], y["pct"], y["draft_pct"]) == (0, 0, 0)
        # uncategorised answer is excluded from every level's counts
        assert sum(s["accepted"] for s in segs) == 2
        assert sum(s["drafted"] for s in segs) == 2
        assert sum(s["total"] for s in segs) == 4

    def test_segments_carry_bootstrap_classes(self):
        assay = AssayFactory.create()
        subsection = SubsectionFactory.create(section__question_set__label="rhseg")
        for colour in ("blue", "green", "yellow", "orange", "red"):
            AnswerFactory.create(
                assay=assay,
                question=QuestionFactory.create(
                    subsection=subsection, riskhunt3r_db_label=colour
                ),
                accepted=True,
            )
        by = {s["value"]: s for s in assay.accepted_by_riskhunt3r_label}
        assert by["blue"]["css_class"] == "bg-primary"
        assert by["green"]["css_class"] == "bg-success"
        assert by["yellow"]["css_class"] == "bg-warning"
        assert by["orange"]["css_class"] == "bg-orange"
        assert by["red"]["css_class"] == "bg-danger"


# ---------------------------------------------------------------------------
# Seeding from ToxTemp_v1.json
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_seed_v1_assigns_riskhunt3r_labels():
    """create_questionset_from_json reads the colour key from the real v1 seed
    and categorises every question."""
    user = PersonFactory.create(is_superuser=True, is_staff=True)
    qs = create_questionset_from_json(label="v1", created_by=user)

    questions = Question.objects.filter(subsection__section__question_set=qs)
    assert questions.exists()

    total = questions.count()
    categorised = questions.exclude(riskhunt3r_db_label="").count()
    # the v1 seed carries a colour on every question
    assert categorised == total

    colours = set(questions.values_list("riskhunt3r_db_label", flat=True))
    assert colours == {"blue", "green", "yellow", "orange", "red"}
