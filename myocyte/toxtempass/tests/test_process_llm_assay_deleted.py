"""Verify that ``process_llm_async`` stops cleanly when the assay is deleted mid-flight."""

import threading
from types import SimpleNamespace

import pytest

from toxtempass.models import (
    Answer,
    Assay,
    Question,
    QuestionSet,
    Section,
    Subsection,
)
from toxtempass.tests.fixtures.factories import AssayFactory
from toxtempass.views import process_llm_async


class BlockingFakeLLM:
    """Fake LLM whose first ``invoke`` blocks until ``release`` is set.

    Used to deterministically simulate a long-running LLM call during which the
    calling code can delete the assay.
    """

    def __init__(self):
        self.release = threading.Event()
        self.first_invoke_started = threading.Event()
        self._lock = threading.Lock()
        self._calls = 0

    def invoke(self, messages):
        with self._lock:
            self._calls += 1
            is_first = self._calls == 1
        if is_first:
            self.first_invoke_started.set()
            # Block long enough for the test thread to delete the assay.
            self.release.wait(timeout=5)
        return SimpleNamespace(content="fake answer")


@pytest.mark.django_db(transaction=True)
def test_process_llm_async_stops_when_assay_deleted_mid_flight():
    """Deleting the assay while the worker is inside an ``invoke`` must:

    * let the worker finish without raising,
    * cancel pending futures / skip saves,
    * leave no lingering Answer rows (they cascade with the Assay anyway).
    """
    assay = AssayFactory()
    qs = QuestionSet.objects.create(
        display_name="test-qs-delete", created_by=assay.study.investigation.owner,
    )
    section = Section.objects.create(question_set=qs, title="Sec 1")
    subsection = Subsection.objects.create(section=section, title="Subsec 1")

    # Two questions so multiple futures run; first one will block.
    q1 = Question.objects.create(subsection=subsection, question_text="Q1?")
    q2 = Question.objects.create(subsection=subsection, question_text="Q2?")
    Answer.objects.create(assay=assay, question=q1)
    Answer.objects.create(assay=assay, question=q2)

    fake = BlockingFakeLLM()
    errors: list[Exception] = []

    def run_task():
        try:
            process_llm_async(
                assay.id,
                doc_dict={},
                extract_images=False,
                chatopenai=fake,
            )
        except Exception as exc:  # pragma: no cover - should not happen
            errors.append(exc)

    worker = threading.Thread(target=run_task)
    worker.start()

    # Wait until the worker is blocked inside the LLM call, then delete the assay.
    assert fake.first_invoke_started.wait(timeout=5), "LLM invoke never started"
    Assay.objects.filter(pk=assay.id).delete()

    # Let the blocking LLM call return; subsequent saves should be skipped because
    # the assay is gone, and the task should exit cleanly.
    fake.release.set()
    worker.join(timeout=10)

    assert not worker.is_alive(), "Worker did not exit after assay deletion"
    assert not errors, f"Worker raised unexpectedly: {errors}"
    assert not Answer.objects.filter(assay_id=assay.id).exists()
