"""Tests for context-window guard in process_llm_async and the
token-estimation / truncation utilities in filehandling.
"""

import threading
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from toxtempass.filehandling import (
    estimate_token_count,
    truncate_context_to_token_limit,
)
from toxtempass.models import (
    Answer,
    Question,
    QuestionSet,
    Section,
    Subsection,
)
from toxtempass.tests.fixtures.factories import AssayFactory
from toxtempass.views import process_llm_async


# ---------------------------------------------------------------------------
# Unit tests for the utility functions
# ---------------------------------------------------------------------------


def test_estimate_token_count_empty():
    assert estimate_token_count("") == 0


def test_estimate_token_count_short():
    count = estimate_token_count("Hello world")
    assert count > 0


def test_truncate_context_no_truncation_needed():
    text = "short text"
    result, was_truncated = truncate_context_to_token_limit(text, max_tokens=10_000)
    assert result == text
    assert was_truncated is False


def test_truncate_context_truncates_long_text():
    # Build a text that is definitely over 10 tokens
    long_text = "word " * 1000  # ~1000+ tokens
    result, was_truncated = truncate_context_to_token_limit(long_text, max_tokens=50)
    assert was_truncated is True
    assert len(result) < len(long_text)
    assert "truncated" in result.lower()


def test_truncate_context_empty_string():
    result, was_truncated = truncate_context_to_token_limit("", max_tokens=100)
    assert result == ""
    assert was_truncated is False


def test_truncate_context_result_within_limit():
    long_text = "token " * 5000  # well over any small limit
    result, was_truncated = truncate_context_to_token_limit(long_text, max_tokens=200)
    assert was_truncated is True
    actual_tokens = estimate_token_count(result)
    # Allow a small overage due to the appended marker
    assert actual_tokens <= 200 + 50


# ---------------------------------------------------------------------------
# Integration test: process_llm_async adds warning when context is truncated
# ---------------------------------------------------------------------------


class _SimpleFakeLLM:
    """Minimal fake LLM that always returns a fixed answer."""

    def __init__(self):
        self._lock = threading.Lock()
        self._calls = 0

    def invoke(self, messages):
        with self._lock:
            self._calls += 1
        return SimpleNamespace(content="Generated answer.")


@pytest.mark.django_db
def test_process_llm_async_warns_when_context_truncated():
    """process_llm_async should write a truncation warning into status_context
    when the document context exceeds the available token budget.
    The budget is derived from the model's context_window minus headroom, or
    fallback - headroom when no context_window tag is set.
    """
    assay = AssayFactory()
    qs = QuestionSet.objects.create(
        display_name="qs", created_by=assay.study.investigation.owner
    )
    section = Section.objects.create(question_set=qs, title="S1")
    subsection = Subsection.objects.create(section=section, title="Sub1")
    q = Question.objects.create(subsection=subsection, question_text="What is this?")
    Answer.objects.create(assay=assay, question=q)

    # A doc_dict whose text content greatly exceeds a 10-token limit
    large_text = "This is some document content. " * 500  # ~several thousand tokens
    doc_dict = {
        "bigfile.txt": {
            "text": large_text,
            "source_document": "bigfile.txt",
            "origin": "document",
        }
    }

    fake_llm = _SimpleFakeLLM()

    # Drive the fallback budget very low (headroom=10, fallback=20 → budget=10)
    with (
        patch("toxtempass.views.config.context_window_headroom_tokens", new=10),
        patch("toxtempass.views.config.context_window_fallback_tokens", new=20),
    ):
        process_llm_async(
            assay.id,
            doc_dict=doc_dict,
            extract_images=False,
            chatopenai=fake_llm,
        )

    assay.refresh_from_db()

    assert assay.status_context, "status_context should not be empty after truncation"
    assert "truncated" in assay.status_context.lower(), (
        "status_context should mention truncation; got: " + assay.status_context
    )


@pytest.mark.django_db
def test_process_llm_async_no_warning_when_context_fits():
    """process_llm_async should NOT modify status_context when the context
    fits within the available token budget.
    """
    assay = AssayFactory()
    qs = QuestionSet.objects.create(
        display_name="qs", created_by=assay.study.investigation.owner
    )
    section = Section.objects.create(question_set=qs, title="S1")
    subsection = Subsection.objects.create(section=section, title="Sub1")
    q = Question.objects.create(subsection=subsection, question_text="What is this?")
    Answer.objects.create(assay=assay, question=q)

    doc_dict = {
        "small.txt": {
            "text": "Short text.",
            "source_document": "small.txt",
            "origin": "document",
        }
    }

    fake_llm = _SimpleFakeLLM()

    # Use a generous fallback so short text is never truncated
    with (
        patch("toxtempass.views.config.context_window_headroom_tokens", new=1_000),
        patch("toxtempass.views.config.context_window_fallback_tokens", new=1_000_000),
    ):
        process_llm_async(
            assay.id,
            doc_dict=doc_dict,
            extract_images=False,
            chatopenai=fake_llm,
        )

    assay.refresh_from_db()

    # status_context may still be None/empty; there should be no truncation notice
    ctx = assay.status_context or ""
    assert "truncated" not in ctx.lower(), (
        "Unexpected truncation warning in status_context: " + ctx
    )


@pytest.mark.django_db
def test_process_llm_async_uses_model_context_window_tag():
    """When llm_model resolves to a ModelEntry with a context_window tag,
    the budget is computed as context_window - headroom (not the fallback).
    """
    from unittest.mock import MagicMock

    assay = AssayFactory()
    qs = QuestionSet.objects.create(
        display_name="qs", created_by=assay.study.investigation.owner
    )
    section = Section.objects.create(question_set=qs, title="S1")
    subsection = Subsection.objects.create(section=section, title="Sub1")
    q = Question.objects.create(subsection=subsection, question_text="What is this?")
    Answer.objects.create(assay=assay, question=q)

    # Build a large context that would exceed a 100-token budget but fit 200 k
    large_text = "word " * 500  # well over 100 tokens
    doc_dict = {
        "doc.txt": {
            "text": large_text,
            "source_document": "doc.txt",
            "origin": "document",
        }
    }

    fake_llm = _SimpleFakeLLM()

    # Fabricate a ModelEntry-like mock whose context_window is 150 tokens
    mock_model_entry = MagicMock()
    mock_model_entry.context_window = 150  # tiny, so truncation kicks in
    mock_model_entry.model_id = "fake-model"

    mock_ep = MagicMock()

    with (
        patch("toxtempass.views.config.context_window_headroom_tokens", new=50),
        patch("toxtempass.views.config.context_window_fallback_tokens", new=1_000_000),
        patch(
            "toxtempass.views._get_model",
            return_value=(mock_ep, mock_model_entry),
            create=True,
        ),
    ):
        # We use a real llm_model key so the resolution branch is entered.
        # The patch above overrides _get_model inside the scope of the test.
        # Because the import inside the guard uses a local alias, we patch at
        # the azure_registry level instead.
        with patch(
            "toxtempass.azure_registry.get_model",
            return_value=(mock_ep, mock_model_entry),
        ):
            process_llm_async(
                assay.id,
                doc_dict=doc_dict,
                extract_images=False,
                chatopenai=fake_llm,
                llm_model="1:FAKE",
            )

    assay.refresh_from_db()

    # Budget was 150 - 50 = 100 tokens; large_text is ~500 tokens → truncated
    assert assay.status_context, "Expected a truncation warning in status_context"
    assert "truncated" in assay.status_context.lower()
