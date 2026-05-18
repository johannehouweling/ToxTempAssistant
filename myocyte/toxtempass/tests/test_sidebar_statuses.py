"""Tests for the _compute_sidebar_statuses helper (sidebar status icons)."""

import pytest

from toxtempass.tests.fixtures.factories import (
    AssayFactory,
    InvestigationFactory,
    PersonFactory,
    StudyFactory,
)


def _make_assay_with_structure(user, num_questions=2):
    """Helper: assay with one section, one subsection, and *num_questions* questions."""
    from toxtempass.models import Answer, Question, QuestionSet, Section, Subsection

    investigation = InvestigationFactory.create(owner=user)
    study = StudyFactory.create(investigation=investigation)
    assay = AssayFactory.create(study=study)
    qs = QuestionSet.objects.create(display_name="sidebar-test-qs", created_by=user)
    section = Section.objects.create(question_set=qs, title="Test Section")
    subsection = Subsection.objects.create(section=section, title="Test Subsection")
    questions = [
        Question.objects.create(subsection=subsection, question_text=f"Q{i}?")
        for i in range(num_questions)
    ]
    answers = [Answer.objects.create(assay=assay, question=q) for q in questions]
    assay.question_set = qs
    assay.save(update_fields=["question_set"])
    return assay, section, subsection, questions, answers


@pytest.mark.django_db
class TestComputeSidebarStatuses:
    """Unit tests for _compute_sidebar_statuses in views.py."""

    def test_no_answers_returns_no_answer(self, db):
        """Sections/subsections with only empty answer rows get 'no_answer' status."""
        from toxtempass.views import _compute_sidebar_statuses

        user = PersonFactory.create()
        assay, section, subsection, _, answers = _make_assay_with_structure(user)

        # answers are created with empty answer_text by default
        for answer in answers:
            assert not answer.answer_text  # confirm they're empty

        sec_statuses, sub_statuses = _compute_sidebar_statuses(assay)

        assert sub_statuses.get(subsection.id) == "no_answer"
        assert sec_statuses.get(section.id) == "no_answer"

    def test_empty_answers_not_counted_as_draft(self, db):
        """Empty answer_text rows are treated as 'no_answer', not 'has_draft'."""
        from toxtempass.models import Answer
        from toxtempass.views import _compute_sidebar_statuses

        user = PersonFactory.create()
        assay, section, subsection, questions, answers = _make_assay_with_structure(
            user, num_questions=1
        )

        # Empty answer (default state after creation)
        answer = answers[0]
        answer.answer_text = ""
        answer.accepted = False
        answer.save(update_fields=["answer_text", "accepted"])

        sec_statuses, sub_statuses = _compute_sidebar_statuses(assay)

        assert sub_statuses.get(subsection.id) == "no_answer"
        assert sec_statuses.get(section.id) == "no_answer"

    def test_not_found_string_counted_as_no_answer(self, db):
        """Answers containing the 'not found' string are treated as 'no_answer'."""
        from toxtempass import config
        from toxtempass.views import _compute_sidebar_statuses

        user = PersonFactory.create()
        assay, section, subsection, questions, answers = _make_assay_with_structure(
            user, num_questions=1
        )

        answers[0].answer_text = config.not_found_string
        answers[0].accepted = False
        answers[0].save(update_fields=["answer_text", "accepted"])

        sec_statuses, sub_statuses = _compute_sidebar_statuses(assay)

        assert sub_statuses.get(subsection.id) == "no_answer"
        assert sec_statuses.get(section.id) == "no_answer"

    def test_meaningful_unaccepted_answer_is_has_draft(self, db):
        """A non-trivial, unaccepted answer yields 'has_draft' status."""
        from toxtempass.views import _compute_sidebar_statuses

        user = PersonFactory.create()
        assay, section, subsection, questions, answers = _make_assay_with_structure(
            user, num_questions=1
        )

        answers[0].answer_text = "The assay uses HepG2 cells."
        answers[0].accepted = False
        answers[0].save(update_fields=["answer_text", "accepted"])

        sec_statuses, sub_statuses = _compute_sidebar_statuses(assay)

        assert sub_statuses.get(subsection.id) == "has_draft"
        assert sec_statuses.get(section.id) == "has_draft"

    def test_all_accepted_returns_all_accepted(self, db):
        """When every answer is accepted, status is 'all_accepted'."""
        from toxtempass.views import _compute_sidebar_statuses

        user = PersonFactory.create()
        assay, section, subsection, questions, answers = _make_assay_with_structure(
            user, num_questions=2
        )

        for answer in answers:
            answer.answer_text = "Accepted answer text."
            answer.accepted = True
            answer.save(update_fields=["answer_text", "accepted"])

        sec_statuses, sub_statuses = _compute_sidebar_statuses(assay)

        assert sub_statuses.get(subsection.id) == "all_accepted"
        assert sec_statuses.get(section.id) == "all_accepted"

    def test_partial_acceptance_is_has_draft(self, db):
        """When some answers are accepted and some are draft, status is 'has_draft'."""
        from toxtempass.views import _compute_sidebar_statuses

        user = PersonFactory.create()
        assay, section, subsection, questions, answers = _make_assay_with_structure(
            user, num_questions=2
        )

        # First answer accepted
        answers[0].answer_text = "Done."
        answers[0].accepted = True
        answers[0].save(update_fields=["answer_text", "accepted"])

        # Second answer is a draft
        answers[1].answer_text = "Still reviewing this one."
        answers[1].accepted = False
        answers[1].save(update_fields=["answer_text", "accepted"])

        sec_statuses, sub_statuses = _compute_sidebar_statuses(assay)

        assert sub_statuses.get(subsection.id) == "has_draft"
        assert sec_statuses.get(section.id) == "has_draft"

    def test_statuses_are_scoped_to_assay(self, db):
        """Status computation is assay-scoped; other assays' answers do not bleed in."""
        from toxtempass.models import Answer
        from toxtempass.views import _compute_sidebar_statuses

        user = PersonFactory.create()
        assay, section, subsection, questions, answers = _make_assay_with_structure(
            user, num_questions=1
        )

        # assay has an empty answer row → no_answer
        sec_statuses, sub_statuses = _compute_sidebar_statuses(assay)
        assert sub_statuses.get(subsection.id) == "no_answer"

        # Create a second assay sharing the same question set, with an accepted answer
        investigation2 = InvestigationFactory.create(owner=user)
        study2 = StudyFactory.create(investigation=investigation2)
        assay2 = AssayFactory.create(study=study2, question_set=assay.question_set)
        Answer.objects.create(
            assay=assay2,
            question=questions[0],
            answer_text="Accepted in other assay.",
            accepted=True,
        )

        # assay2 should show all_accepted; assay1 must still be no_answer
        sec_statuses2, sub_statuses2 = _compute_sidebar_statuses(assay2)
        assert sub_statuses2.get(subsection.id) == "all_accepted"

        # Re-check assay1 hasn't changed
        sec_statuses1, sub_statuses1 = _compute_sidebar_statuses(assay)
        assert sub_statuses1.get(subsection.id) == "no_answer"
