"""Tests for the assay_time_sync endpoint and AssayTimeLog model."""

import pytest
from django.test import Client
from django.urls import reverse

from toxtempass.models import AssayTimeLog
from toxtempass.tests.fixtures.factories import (
    AssayFactory,
    InvestigationFactory,
    PersonFactory,
    StudyFactory,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user(db):
    return PersonFactory.create()


@pytest.fixture
def other_user(db):
    return PersonFactory.create()


@pytest.fixture
def assay(db, user):
    """An assay whose investigation is owned by *user* so access checks pass."""
    investigation = InvestigationFactory.create(owner=user)
    study = StudyFactory.create(investigation=investigation)
    return AssayFactory.create(study=study)


@pytest.fixture
def sync_url(assay):
    return reverse("assay_time_sync", kwargs={"assay_id": assay.id})


# ---------------------------------------------------------------------------
# assay_time_sync view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAssayTimeSyncView:
    def test_unauthenticated_redirects(self, client, sync_url):
        resp = client.post(sync_url, {"seconds": "100"})
        assert resp.status_code == 302

    def test_get_not_allowed(self, client, user, sync_url):
        client.force_login(user)
        resp = client.get(sync_url)
        assert resp.status_code == 405

    def test_creates_time_log_row(self, client, user, assay, sync_url):
        client.force_login(user)
        resp = client.post(sync_url, {"seconds": "120"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        row = AssayTimeLog.objects.get(user=user, assay=assay)
        assert row.seconds == 120

    def test_updates_existing_row(self, client, user, assay, sync_url):
        AssayTimeLog.objects.create(user=user, assay=assay, seconds=60)
        client.force_login(user)
        resp = client.post(sync_url, {"seconds": "180"})
        assert resp.status_code == 200
        assert AssayTimeLog.objects.filter(user=user, assay=assay).count() == 1
        assert AssayTimeLog.objects.get(user=user, assay=assay).seconds == 180

    def test_total_seconds_aggregates_across_users(self, client, user, other_user, assay, sync_url):
        """total_seconds in the response is the sum across all collaborators."""
        # Grant other_user access via the investigation
        assay.study.investigation.share(other_user)

        client.force_login(user)
        client.post(sync_url, {"seconds": "100"})

        client2 = Client()
        client2.force_login(other_user)
        resp = client2.post(sync_url, {"seconds": "200"})

        data = resp.json()
        assert data["success"] is True
        assert data["total_seconds"] == 300

    def test_invalid_seconds_non_integer(self, client, user, sync_url):
        client.force_login(user)
        resp = client.post(sync_url, {"seconds": "abc"})
        assert resp.status_code == 400
        assert resp.json()["success"] is False

    def test_invalid_seconds_negative(self, client, user, sync_url):
        client.force_login(user)
        resp = client.post(sync_url, {"seconds": "-5"})
        assert resp.status_code == 400

    def test_zero_seconds_accepted(self, client, user, assay, sync_url):
        client.force_login(user)
        resp = client.post(sync_url, {"seconds": "0"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["total_seconds"] == 0

    def test_total_seconds_is_zero_with_no_logs(self, client, user, assay, sync_url):
        """First call with 0 seconds returns total_seconds 0."""
        client.force_login(user)
        resp = client.post(sync_url, {"seconds": "0"})
        assert resp.json()["total_seconds"] == 0

    def test_inaccessible_assay_returns_403(self, client, db):
        """A user with no access to the assay gets a 403."""
        outsider = PersonFactory.create()
        assay = AssayFactory.create()
        # The assay owner is the investigation owner; outsider has no access
        url = reverse("assay_time_sync", kwargs={"assay_id": assay.id})
        client.force_login(outsider)
        resp = client.post(url, {"seconds": "60"})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# AssayTimeLog model
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAssayTimeLogModel:
    def test_unique_together_constraint(self, user, assay):
        AssayTimeLog.objects.create(user=user, assay=assay, seconds=10)
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            AssayTimeLog.objects.create(user=user, assay=assay, seconds=20)

    def test_str_representation(self, user, assay):
        log = AssayTimeLog(user=user, assay=assay, seconds=42)
        assert str(log.user.email) in str(log)
        assert "42" in str(log)


# ---------------------------------------------------------------------------
# Completion-time auto-capture (AssayAnswerForm.save -> Assay.completion_time_seconds)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCompletionTimeCapture:
    """completion_time_seconds is auto-set when all answers are accepted."""

    def _make_assay_with_questions(self, user, n=2):
        """Helper: assay with *n* questions and empty answer rows."""
        from toxtempass.models import Answer, Question, QuestionSet, Section, Subsection

        investigation = InvestigationFactory.create(owner=user)
        study = StudyFactory.create(investigation=investigation)
        assay = AssayFactory.create(study=study)
        qs = QuestionSet.objects.create(
            display_name="completion-test-qs",
            created_by=user,
        )
        section = Section.objects.create(question_set=qs, title="Sec")
        subsection = Subsection.objects.create(section=section, title="Subsec")
        questions = [
            Question.objects.create(subsection=subsection, question_text=f"Q{i}?")
            for i in range(n)
        ]
        answers = [Answer.objects.create(assay=assay, question=q) for q in questions]
        assay.question_set = qs
        assay.save(update_fields=["question_set"])
        return assay, questions, answers

    def test_completion_time_set_when_all_accepted(self, db):
        """completion_time_seconds is populated the first time all answers are accepted."""
        from toxtempass.forms import AssayAnswerForm

        user = PersonFactory.create()
        assay, questions, answers = self._make_assay_with_questions(user)

        # Pre-seed AssayTimeLog to simulate ~10 min of tracked time
        AssayTimeLog.objects.create(user=user, assay=assay, seconds=600)

        # Accept all answers via the form
        data = {}
        for answer in answers:
            answer.answer_text = "Some text"
            answer.save(update_fields=["answer_text"])
            data[f"question_{answer.question_id}"] = "Some text"
            data[f"accepted_{answer.question_id}"] = True

        form = AssayAnswerForm(data=data, assay=assay, user=user)
        assert form.is_valid(), f"Form errors: {form.errors}"
        form.save()

        assay.refresh_from_db()
        assert assay.completion_time_seconds == 600

    def test_completion_time_not_set_when_some_unaccepted(self, db):
        """completion_time_seconds stays None when at least one answer is not accepted."""
        from toxtempass.forms import AssayAnswerForm

        user = PersonFactory.create()
        assay, questions, answers = self._make_assay_with_questions(user, n=2)

        AssayTimeLog.objects.create(user=user, assay=assay, seconds=300)

        # Accept only the first answer, leave the second un-accepted
        answers[0].answer_text = "Done"
        answers[0].save(update_fields=["answer_text"])
        data = {
            f"question_{answers[0].question_id}": "Done",
            f"accepted_{answers[0].question_id}": True,
            f"question_{answers[1].question_id}": "In progress",
            # accepted_<id> intentionally absent → defaults to False
        }

        form = AssayAnswerForm(data=data, assay=assay, user=user)
        assert form.is_valid(), f"Form errors: {form.errors}"
        form.save()

        assay.refresh_from_db()
        assert assay.completion_time_seconds is None

    def test_completion_time_not_overwritten_on_subsequent_saves(self, db):
        """Once set, completion_time_seconds is not overwritten by later saves."""
        from toxtempass.forms import AssayAnswerForm

        user = PersonFactory.create()
        assay, questions, answers = self._make_assay_with_questions(user, n=1)

        AssayTimeLog.objects.create(user=user, assay=assay, seconds=120)

        answer = answers[0]
        answer.answer_text = "First pass"
        answer.save(update_fields=["answer_text"])
        data = {
            f"question_{answer.question_id}": "First pass",
            f"accepted_{answer.question_id}": True,
        }
        form = AssayAnswerForm(data=data, assay=assay, user=user)
        assert form.is_valid()
        form.save()

        assay.refresh_from_db()
        assert assay.completion_time_seconds == 120

        # Simulate more time passing and a second save with all still accepted
        AssayTimeLog.objects.filter(user=user, assay=assay).update(seconds=999)

        form2 = AssayAnswerForm(data=data, assay=assay, user=user)
        assert form2.is_valid()
        form2.save()

        assay.refresh_from_db()
        # Must still be the original value
        assert assay.completion_time_seconds == 120

    def test_all_answers_accepted_property(self, db):
        """Assay.all_answers_accepted returns True only when all rows are accepted."""
        from toxtempass.models import Answer, Question, QuestionSet, Section, Subsection

        user = PersonFactory.create()
        assay, questions, answers = self._make_assay_with_questions(user, n=2)

        # Nothing accepted yet
        assert not assay.all_answers_accepted

        # Accept first
        answers[0].accepted = True
        answers[0].save(update_fields=["accepted"])
        assay.refresh_from_db()
        assert not assay.all_answers_accepted

        # Accept second
        answers[1].accepted = True
        answers[1].save(update_fields=["accepted"])
        assay.refresh_from_db()
        assert assay.all_answers_accepted

        # Un-accept one → back to False
        answers[0].accepted = False
        answers[0].save(update_fields=["accepted"])
        assay.refresh_from_db()
        assert not assay.all_answers_accepted
