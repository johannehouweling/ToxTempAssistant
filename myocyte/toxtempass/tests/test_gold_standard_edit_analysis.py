"""Unit tests for the Django-free gold-standard edit-analysis logic.

The cosine signal is injected, so these run with no embeddings/API — semantic similarity
is supplied directly to exercise the classification thresholds.
"""

from datetime import date

from toxtempass import config
from toxtempass.evaluation.gold_standard.edit_analysis import (
    analyze_answer_history,
    classify_edit,
)

# Use the central sentinel (toxtempass/__init__.py Config) so the test never drifts.
NF = config.not_found_string


def test_classify_none():
    assert classify_edit("abc", "abc", 1.0, NF)["edit_type"] == "none"


def test_classify_abstain_to_answer():
    # Model abstained, scientist supplied a real answer = a confirmed recall gap.
    # Sentinel check precedes cosine, so even a low cosine still classifies correctly.
    assert classify_edit(NF, "a real grounded answer", 0.2, NF)[
        "edit_type"
    ] == "abstain_to_answer"


def test_classify_answer_to_abstain():
    # Scientist replaced a (likely hallucinated) answer with the abstention sentinel.
    assert classify_edit("a confident wrong answer", NF, 0.2, NF)[
        "edit_type"
    ] == "answer_to_abstain"


def test_classify_rewrite_low_cosine():
    # Low semantic cosine ⇒ meaning changed ⇒ rewrite, regardless of surface overlap.
    assert classify_edit("alpha beta gamma", "totally different now", 0.4, NF)[
        "edit_type"
    ] == "rewrite"


def test_classify_cosmetic_high_lexical():
    # High cosine + tiny surface change (unit symbol) ⇒ cosmetic.
    r = classify_edit("The value is 5 uM.", "The value is 5 µM.", 0.99, NF)
    assert r["edit_type"] == "cosmetic"


def test_classify_expand():
    # Meaning preserved (cosine high), draft kept, substantial content added ⇒ expand.
    r = classify_edit("short", "short text with much more detail added here", 0.9, NF)
    assert r["edit_type"] == "expand"
    assert r["chars_added"] > 0


def test_classify_trim():
    r = classify_edit(
        "a long original answer with extra detail", "a long original answer", 0.92, NF
    )
    assert r["edit_type"] == "trim"
    assert r["chars_removed"] > 0


def test_classify_reword_is_edit():
    # Same meaning (cosine ok) but reworded (low surface ratio) and similar length ⇒ edit.
    r = classify_edit("the cells were treated now", "cells got treatment ok", 0.85, NF)
    assert r["edit_type"] == "edit"


def _row(text, htype, uid, d):
    return {
        "answer_text": text, "history_type": htype, "history_user_id": uid,
        "history_date": d,
    }


def test_history_pre_cutoff_draft_recoverable():
    # Pre-2025-09-13: gpt-4o-mini wrote via answer.save() -> draft is the first non-blank
    # snapshot; the human edit is a later snapshot.
    pre = date(2025, 1, 1)
    rows = [
        _row("", "+", 1, pre),
        _row("the gpt-4o-mini draft", "~", None, pre),
        _row("scientist edited final", "~", 7, pre),
    ]
    a = analyze_answer_history(rows, "scientist edited final", NF, lambda x, y: 0.4)
    assert a["draft_in_history"] is True
    assert a["draft_text"] == "the gpt-4o-mini draft"
    assert a["draft_source"] == "history"
    assert a["n_human_edits"] == 1
    assert a["reviewer_ids"] == [7]
    assert a["edit_type"] == "rewrite"        # injected cosine 0.4 < REWRITE_MAX_COSINE
    assert a["cosine"] == 0.4


def test_history_post_cutoff_draft_invisible():
    # On/after 2025-09-13: draft written via .update() -> not in history; first non-blank
    # snapshot is the human edit, so no draft and no edit-typing (cosine_fn never called).
    post = date(2026, 1, 1)
    rows = [
        _row("", "+", 9, post),
        _row("human final answer", "~", 9, post),
    ]
    b = analyze_answer_history(rows, "human final answer", NF, lambda x, y: 1.0)
    assert b["draft_in_history"] is False
    assert b["edit_type"] == "n/a"
    assert b["n_human_edits"] == 1


def test_history_sync_era_draft_user_not_counted_as_edit():
    # Early sync era: the draft-save row carries history_user=owner. It must be treated as
    # the draft, NOT a human edit; identical accept-save ⇒ accepted verbatim ('none').
    pre = date(2025, 2, 1)
    rows = [
        _row("", "+", 3, pre),
        _row("draft from model", "~", 3, pre),   # draft-save, owner-attributed
        _row("draft from model", "~", 3, pre),   # accept-save, unchanged text
    ]
    a = analyze_answer_history(rows, "draft from model", NF, lambda x, y: 1.0)
    assert a["draft_in_history"] is True
    assert a["draft_text"] == "draft from model"
    assert a["edit_type"] == "none"           # accepted verbatim
