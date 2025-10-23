import threading
from types import SimpleNamespace

import pytest

from toxtempass.tests.fixtures.factories import AssayFactory
from toxtempass.models import (
    QuestionSet,
    Section,
    Subsection,
    Question,
    Answer,
)
from toxtempass.views import process_llm_async


class FakeChatOpenAI:
    """A very small fake that returns a non-empty answer only for the first invoke call."""

    def __init__(self):
        self._lock = threading.Lock()
        self._calls = 0

    def invoke(self, messages):
        with self._lock:
            self._calls += 1
            call_num = self._calls

        # Return a non-empty answer only on the first call, empty afterwards
        if call_num == 1:
            return SimpleNamespace(content="This is a generated test answer.")
        return SimpleNamespace(content="")


@pytest.mark.django_db
def test_process_llm_async_stops_when_one_answered():
    """
    Ensure process_llm_async updates at least one Answer.answer_text (i.e. not empty)
    when the ChatOpenAI returns a non-empty content for a single question.
    """
    # Create an assay (factory creates owner/investigation/study too)
    assay = AssayFactory()

    # Create a QuestionSet + structure and attach several questions so process_llm_async
    # has Answer rows to operate on.
    qs = QuestionSet.objects.create(display_name="test-qs", created_by=assay.study.investigation.owner)

    section = Section.objects.create(question_set=qs, title="Sec 1")
    subsection = Subsection.objects.create(section=section, title="Subsec 1")

    # Create multiple questions so the function has several answers to process.
    q1 = Question.objects.create(subsection=subsection, question_text="Q1?")
    q2 = Question.objects.create(subsection=subsection, question_text="Q2?")
    q3 = Question.objects.create(subsection=subsection, question_text="Q3?")

    # Seed Answer rows (initially empty answer_text)
    a1 = Answer.objects.create(assay=assay, question=q1)
    a2 = Answer.objects.create(assay=assay, question=q2)
    a3 = Answer.objects.create(assay=assay, question=q3)

    # Provide minimal document dict (empty is acceptable)
    doc_dict = {}

    fake_llm = FakeChatOpenAI()

    # Run the function synchronously (we pass our fake chatopenai)
    process_llm_async(assay.id, doc_dict=doc_dict, chatopenai=fake_llm)

    # Refresh from DB
    refreshed = list(Answer.objects.filter(assay=assay).order_by("id"))
    # Assert at least one answer was filled (non-empty)
    assert any(a.answer_text and a.answer_text.strip() for a in refreshed), "No answers were populated by process_llm_async"
