import threading
from types import SimpleNamespace

import pytest
from openai import RateLimitError

from toxtempass.tests.fixtures.factories import AssayFactory
from toxtempass.models import QuestionSet, Section, Subsection, Question, Answer
from toxtempass.views import process_llm_async


class RateLimitThenSuccessFake:
    """Fake ChatOpenAI that raises a RateLimitError once, then returns a successful response."""

    def __init__(self):
        self._lock = threading.Lock()
        self._calls = 0

    def invoke(self, messages):
        with self._lock:
            self._calls += 1
            call_num = self._calls

        if call_num == 1:
            # Build a RateLimitError and attach a response.json() that contains a retry hint
            err = RateLimitError("rate limited")
            class Resp:
                def json(self_non):
                    return {"error": {"message": "Rate limit. please try again in 0.01s"}}
            err.response = Resp()
            raise err

        # Subsequent calls succeed
        return SimpleNamespace(content="Recovered answer after rate limit")


@pytest.mark.django_db
def test_process_llm_async_retries_on_ratelimit_and_succeeds():
    """
    Ensure process_llm_async retries when a RateLimitError is raised and eventually writes an answer.
    The fake waits are short (0.01s) to keep the test fast.
    """
    assay = AssayFactory()

    qs = QuestionSet.objects.create(display_name="rl-test", created_by=assay.study.investigation.owner)
    section = Section.objects.create(question_set=qs, title="Sec RL")
    subsection = Subsection.objects.create(section=section, title="Subsec RL")

    q1 = Question.objects.create(subsection=subsection, question_text="RL Q1?")
    q2 = Question.objects.create(subsection=subsection, question_text="RL Q2?")

    # Seed Answer rows
    a1 = Answer.objects.create(assay=assay, question=q1)
    a2 = Answer.objects.create(assay=assay, question=q2)

    doc_dict = {}

    fake = RateLimitThenSuccessFake()

    # Run synchronously with fake; should retry and then write at least one non-empty answer
    process_llm_async(assay.id, doc_dict=doc_dict, chatopenai=fake)

    refreshed = list(Answer.objects.filter(assay=assay).order_by("id"))
    assert any(a.answer_text and a.answer_text.strip() for a in refreshed), "No answers were populated after rate limit recovery"
