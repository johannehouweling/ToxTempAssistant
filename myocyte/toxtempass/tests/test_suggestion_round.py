"""Tests for the optional round-2 "suggestion tier" (out-of-context answers).

Covers the pipeline phase (targeting, non-destructiveness, idempotency, opt-in
gating), the tolerant ``parse_suggestion`` parser, the multi-choice
``suggestion_sources`` validation, and the form-driven promote flow.

Run from ``myocyte/`` with:
    DJANGO_SETTINGS_MODULE=myocyte.settings PYTHONPATH=myocyte poetry run pytest \
        toxtempass/tests/test_suggestion_round.py -v
"""

import concurrent.futures
import threading
from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError

from toxtempass import config
from toxtempass.forms import AssayAnswerForm
from toxtempass.models import (
    Answer,
    Question,
    QuestionSet,
    Section,
    Subsection,
    SuggestionSource,
)
from toxtempass.tests.fixtures.factories import AssayFactory
from toxtempass.views import parse_suggestion, process_llm_async

# A well-formed round-2 response: an answer, a numeric certainty, and two tagged
# sources (one general-knowledge, one document). "MISS" in a question text makes
# the fake's STRICT pass return the not-found sentinel for that question.
DEFAULT_SUGGESTION = (
    "Answer: Incubate at 37 C with 5% CO2.\n"
    "Certainty: 0.8\n"
    "Sources: guidance|OECD GD211|https://www.oecd.org/gd211, document|methods.pdf|"
)


class _SyncExecutor:
    """Drop-in for ThreadPoolExecutor that runs each task in the calling thread.

    The pipeline reads/writes the DB from worker threads; under in-memory
    shared-cache SQLite that raises SQLITE_LOCKED and can silently drop a write.
    Running tasks synchronously on one connection makes the DB-touching tests
    deterministic. Production is unaffected (real threads, Postgres).
    """

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def submit(self, fn, *args, **kwargs):
        fut = concurrent.futures.Future()
        try:
            fut.set_result(fn(*args, **kwargs))
        except BaseException as exc:  # noqa: BLE001
            fut.set_exception(exc)
        return fut


class FakeChat:
    """Fake chat model that answers strict vs suggestion passes differently.

    The two passes are told apart by the ``Certainty:`` instruction that only the
    suggestion prompt carries. STRICT pass returns the not-found sentinel for any
    question whose text contains ``MISS`` (else a documented answer); SUGGESTION
    pass returns ``suggestion_response``.
    """

    def __init__(self, suggestion_response: str = DEFAULT_SUGGESTION):
        self.suggestion_response = suggestion_response
        self.strict_calls = 0
        self.suggestion_calls = 0
        self._lock = threading.Lock()

    def invoke(self, messages):  # noqa: ANN001, ANN201
        text = " ".join(
            m.content if isinstance(m.content, str) else str(m.content)
            for m in messages
        )
        is_suggestion = "Certainty:" in text and "Sources:" in text
        with self._lock:
            if is_suggestion:
                self.suggestion_calls += 1
                return SimpleNamespace(content=self.suggestion_response)
            self.strict_calls += 1
            if "MISS" in text:
                return SimpleNamespace(content=config.not_found_string)
            return SimpleNamespace(content="Documented answer.")


def _build_assay(question_texts):
    """Create an assay + question_set with one Answer row per question text."""
    assay = AssayFactory()
    owner = assay.study.investigation.owner
    qs = QuestionSet.objects.create(display_name="suggest-qs", created_by=owner)
    section = Section.objects.create(question_set=qs, title="Sec")
    subsection = Subsection.objects.create(section=section, title="Sub")
    assay.question_set = qs
    assay.save()
    questions = [
        Question.objects.create(subsection=subsection, question_text=t)
        for t in question_texts
    ]
    answers = [Answer.objects.create(assay=assay, question=q) for q in questions]
    return assay, owner, questions, answers


@pytest.fixture(autouse=True)
def _suggestion_test_env(monkeypatch):
    """Keep the suite offline and deterministic.

    * Treat every citation URL as resolving (no network). Individual tests can
      re-stub ``_url_resolves`` to exercise the drop path.
    * Run the answering pool in the calling thread: in-memory SQLite raises
      SQLITE_LOCKED on concurrent access, which can silently drop a write.
      Production runs on Postgres with real threads; this is a test-harness
      concern only.
    """
    monkeypatch.setattr(
        "toxtempass.views._url_resolves", lambda url, timeout=4.0: True
    )
    monkeypatch.setattr("toxtempass.views.ThreadPoolExecutor", _SyncExecutor)


# ── pipeline phase ────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_suggestions_target_only_not_found():
    """The suggestion phase runs only for the rows that came back not-found."""
    assay, _owner, questions, _ = _build_assay(
        ["Q1 documented?", "Q2 MISS?", "Q3 MISS?"]
    )
    fake = FakeChat()
    process_llm_async(
        assay.id, doc_dict={}, extract_images=False, chatopenai=fake,
        do_suggestions=True,
    )
    a1, a2, a3 = (Answer.objects.get(assay=assay, question=q) for q in questions)
    assert fake.suggestion_calls == 2  # only the two MISS rows
    assert a1.suggestion_text == ""  # documented row got no suggestion
    assert a2.suggestion_text and a3.suggestion_text
    assert a2.suggestion_certainty == 0.8


@pytest.mark.django_db(transaction=True)
def test_suggestions_do_not_clobber_strict_answer():
    """answer_text/accepted are untouched; the suggestion lives in its own field."""
    assay, _owner, questions, _ = _build_assay(["Q MISS?"])
    fake = FakeChat()
    process_llm_async(
        assay.id, doc_dict={}, extract_images=False, chatopenai=fake,
        do_suggestions=True,
    )
    a = Answer.objects.get(assay=assay, question=questions[0])
    assert config.not_found_string in a.answer_text  # sentinel preserved
    assert a.accepted is None  # acceptance untouched
    assert a.suggestion_text  # stored separately
    assert a.has_pending_suggestion is True


@pytest.mark.django_db(transaction=True)
def test_not_found_count_unchanged_and_pending_count():
    """Round 2 never reduces number_answers_not_found; it drives pending count."""
    assay, _owner, _questions, _ = _build_assay(["A?", "B MISS?", "C MISS?"])
    process_llm_async(
        assay.id, doc_dict={}, extract_images=False, chatopenai=FakeChat(),
        do_suggestions=True,
    )
    assay.refresh_from_db()
    assert assay.number_answers_not_found == 2
    assert assay.number_pending_suggestions == 2


@pytest.mark.django_db(transaction=True)
def test_suggestions_disabled_by_default():
    """Without the opt-in, the suggestion phase makes zero LLM calls."""
    assay, _owner, questions, _ = _build_assay(["Q MISS?"])
    fake = FakeChat()
    process_llm_async(assay.id, doc_dict={}, extract_images=False, chatopenai=fake)
    assert fake.suggestion_calls == 0
    a = Answer.objects.get(assay=assay, question=questions[0])
    assert a.suggestion_text == ""


@pytest.mark.django_db(transaction=True)
def test_suggestions_idempotent_on_rerun():
    """Re-running never re-bills a row that already has a suggestion."""
    assay, _owner, _questions, _ = _build_assay(["Q MISS?"])
    fake = FakeChat()
    process_llm_async(
        assay.id, doc_dict={}, extract_images=False, chatopenai=fake,
        do_suggestions=True,
    )
    first = fake.suggestion_calls
    assert first == 1
    process_llm_async(
        assay.id, doc_dict={}, extract_images=False, chatopenai=fake,
        do_suggestions=True,
    )
    assert fake.suggestion_calls == first  # no new suggestion calls


@pytest.mark.django_db(transaction=True)
def test_suggestion_sources_multichoice_and_validation():
    """suggestion_sources is a deduped, enum-valid tier set; clean() rejects junk."""
    assay, _owner, questions, _ = _build_assay(["Q MISS?"])
    process_llm_async(
        assay.id, doc_dict={}, extract_images=False, chatopenai=FakeChat(),
        do_suggestions=True,
    )
    a = Answer.objects.get(assay=assay, question=questions[0])
    assert isinstance(a.suggestion_sources, list)
    assert "knowledge" in a.suggestion_sources  # always present for round 2
    assert "document" in a.suggestion_sources  # derived from the cited document
    assert set(a.suggestion_sources) <= set(SuggestionSource.values)

    a.suggestion_sources = ["knowledge", "bogus-tier"]
    with pytest.raises(ValidationError):
        a.clean()


@pytest.mark.django_db(transaction=True)
def test_nonresolving_url_is_dropped(monkeypatch):
    """A citation URL that doesn't resolve is blanked; the label survives."""
    monkeypatch.setattr(
        "toxtempass.views._url_resolves", lambda url, timeout=4.0: False
    )
    assay, _owner, questions, _ = _build_assay(["Q MISS?"])
    process_llm_async(
        assay.id, doc_dict={}, extract_images=False, chatopenai=FakeChat(),
        do_suggestions=True,
    )
    a = Answer.objects.get(assay=assay, question=questions[0])
    assert a.suggestion_citations  # citations are kept
    assert all(c["url"] == "" for c in a.suggestion_citations)  # links dropped
    assert any("OECD GD211" in c["label"] for c in a.suggestion_citations)


# ── SSRF guard (no DB, no network) ────────────────────────────────────────────


def test_is_public_http_host_blocks_internal_targets():
    from toxtempass.views import _is_public_http_host

    assert _is_public_http_host("https://www.oecd.org/x") is True
    assert _is_public_http_host("http://localhost/x") is False
    assert _is_public_http_host("http://127.0.0.1/x") is False
    assert _is_public_http_host("http://169.254.169.254/latest/meta-data/") is False
    assert _is_public_http_host("http://10.0.0.5/x") is False
    assert _is_public_http_host("http://192.168.1.1/x") is False
    assert _is_public_http_host("http://db.internal/x") is False


# ── parser (no DB) ────────────────────────────────────────────────────────────


def test_parse_suggestion_wellformed():
    answer, certainty, citations = parse_suggestion(DEFAULT_SUGGESTION)
    assert answer == "Incubate at 37 C with 5% CO2."
    assert certainty == 0.8
    assert citations[0] == {
        "kind": "guidance",
        "label": "OECD GD211",
        "url": "https://www.oecd.org/gd211",
    }
    assert citations[1] == {"kind": "document", "label": "methods.pdf", "url": ""}


def test_parse_suggestion_missing_certainty():
    _answer, certainty, _citations = parse_suggestion(
        "Answer: foo\nSources: knowledge:x"
    )
    assert certainty is None


def test_parse_suggestion_missing_sources():
    _answer, _certainty, citations = parse_suggestion(
        "Answer: foo\nCertainty: 0.5"
    )
    assert citations == []


def test_parse_suggestion_chatty_without_labels():
    """A model that ignores the format yields the whole text as the answer."""
    answer, certainty, citations = parse_suggestion(
        "I think you should incubate the cells at 37 C."
    )
    assert answer == "I think you should incubate the cells at 37 C."
    assert certainty is None
    assert citations == []


def test_parse_suggestion_clamps_and_tolerates_certainty():
    _a, certainty, _c = parse_suggestion(
        "Answer: foo\nCertainty: 1.5\nSources: knowledge:x"
    )
    assert certainty == 1.0  # clamped to [0, 1]
    _a2, certainty2, _c2 = parse_suggestion(
        "Answer: foo\nCertainty: high\nSources: knowledge:x"
    )
    assert certainty2 is None  # non-numeric -> None, never raises


def test_parse_suggestion_unknown_kind_falls_back_to_knowledge():
    _a, _c, citations = parse_suggestion(
        "Answer: foo\nCertainty: 0.3\nSources: nonsense|thing|"
    )
    assert citations == [{"kind": "knowledge", "label": "thing", "url": ""}]


def test_parse_suggestion_rejects_unsafe_url():
    """A non-http(s) scheme is dropped so it can never reach an href."""
    _a, _c, citations = parse_suggestion(
        "Answer: x\nCertainty: 0.2\nSources: knowledge|bad actor|javascript:alert(1)"
    )
    assert citations[0]["url"] == ""
    assert citations[0]["label"] == "bad actor"


def test_parse_suggestion_legacy_colon_format():
    """Old 'kind:label' entries still parse (url defaults to empty)."""
    _a, _c, citations = parse_suggestion(
        "Answer: x\nCertainty: 0.5\nSources: knowledge:OECD GD211"
    )
    assert citations == [{"kind": "knowledge", "label": "OECD GD211", "url": ""}]


def test_parse_suggestion_keeps_inline_markdown_and_source_markers():
    """New format: Markdown + inline _(Source: LABEL)_ survive in the answer prose.

    The inline LABEL matches the Sources-line label, so the renderer can turn the
    marker into a footnote linked to the verified URL.
    """
    text = (
        "Answer: Use the **MTT viability** assay _(Source: OECD TG 487)_.\n"
        "Certainty: 0.7\n"
        "Sources: guidance|OECD TG 487|https://www.oecd.org/tg487"
    )
    answer, certainty, citations = parse_suggestion(text)
    assert answer == "Use the **MTT viability** assay _(Source: OECD TG 487)_."
    assert certainty == 0.7
    assert citations == [
        {
            "kind": "guidance",
            "label": "OECD TG 487",
            "url": "https://www.oecd.org/tg487",
        }
    ]


# ── promote flow (form) ───────────────────────────────────────────────────────


@pytest.mark.django_db
def test_promote_copies_suggestion_into_answer_text():
    """Promoting copies suggestion_text -> answer_text, accepts it, keeps provenance."""
    assay, owner, questions, answers = _build_assay(["Q MISS?"])
    q = questions[0]
    a = answers[0]
    a.answer_text = config.not_found_string
    a.suggestion_text = "Promoted suggestion content."
    a.suggestion_certainty = 0.6
    a.suggestion_sources = ["knowledge"]
    a.save()

    data = {
        f"promote_{q.id}": "true",
        f"accepted_{q.id}": "on",
        # textarea still shows the sentinel (JS-disabled path); the server falls
        # back to suggestion_text rather than persisting the not-found sentinel.
        f"question_{q.id}": config.not_found_string,
    }
    form = AssayAnswerForm(data, assay=assay, user=owner)
    assert form.is_valid(), form.errors
    form.save()

    a.refresh_from_db()
    assert a.answer_text == "Promoted suggestion content."
    assert a.accepted is True
    assert a.suggestion_text == "Promoted suggestion content."  # retained
    assert a.has_pending_suggestion is False  # card disappears


@pytest.mark.django_db
def test_promote_without_accept_lands_as_unaccepted_draft():
    """Using a suggestion without ticking accept lands it as a draft, NOT accepted."""
    assay, owner, questions, answers = _build_assay(["Q MISS?"])
    q = questions[0]
    a = answers[0]
    a.answer_text = config.not_found_string
    a.suggestion_text = "Draft suggestion content."
    a.suggestion_sources = ["knowledge"]
    a.save()

    data = {
        f"promote_{q.id}": "true",
        # No accepted_ field: the scientist has used but not yet accepted it.
        f"question_{q.id}": config.not_found_string,
    }
    form = AssayAnswerForm(data, assay=assay, user=owner)
    assert form.is_valid(), form.errors
    form.save()

    a.refresh_from_db()
    assert a.answer_text == "Draft suggestion content."
    assert a.accepted is False  # NOT auto-accepted — a draft awaiting review
    assert a.has_pending_suggestion is False  # card gone (sentinel overwritten)


@pytest.mark.django_db
def test_promote_honours_edited_draft_text():
    """Edits to the staged draft before saving are preserved, not clobbered."""
    assay, owner, questions, answers = _build_assay(["Q MISS?"])
    q = questions[0]
    a = answers[0]
    a.answer_text = config.not_found_string
    a.suggestion_text = "Original suggestion."
    a.suggestion_sources = ["knowledge"]
    a.save()

    data = {
        f"promote_{q.id}": "true",
        f"accepted_{q.id}": "on",
        # The scientist refined the staged draft in the textarea before saving.
        f"question_{q.id}": "Refined by the scientist.",
    }
    form = AssayAnswerForm(data, assay=assay, user=owner)
    assert form.is_valid(), form.errors
    form.save()

    a.refresh_from_db()
    assert a.answer_text == "Refined by the scientist."  # edit preserved
    assert a.suggestion_text == "Original suggestion."  # provenance retained


@pytest.mark.django_db
def test_dismiss_clears_suggestion_keeps_sentinel():
    """Dismissing clears the suggestion fields but keeps the strict answer."""
    assay, owner, questions, answers = _build_assay(["Q MISS?"])
    q = questions[0]
    a = answers[0]
    a.answer_text = config.not_found_string
    a.suggestion_text = "Some suggestion."
    a.suggestion_sources = ["knowledge"]
    a.save()

    data = {
        f"dismiss_{q.id}": "true",
        f"question_{q.id}": config.not_found_string,
    }
    form = AssayAnswerForm(data, assay=assay, user=owner)
    assert form.is_valid(), form.errors
    form.save()

    a.refresh_from_db()
    assert a.suggestion_text == ""
    assert a.suggestion_sources == []
    assert config.not_found_string in a.answer_text
    assert a.has_pending_suggestion is False
