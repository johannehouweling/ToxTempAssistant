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


def test_baseline_model_draft_is_exact():
    # A non-blank '~' snapshot with history_user_id=None is the gpt-4o-mini draft → the
    # baseline is that draft and the delta is EXACT (true draft→accepted).
    d = date(2025, 1, 1)
    rows = [
        _row("", "+", 1, d),
        _row("the gpt-4o-mini draft", "~", None, d),   # model draft (no request user)
        _row("scientist edited final", "~", 7, d),
    ]
    a = analyze_answer_history(rows, "scientist edited final", NF, lambda x, y: 0.4)
    assert a["baseline_kind"] == "model_draft"
    assert a["delta_exact"] is True
    assert a["baseline_answer"] == "the gpt-4o-mini draft"
    assert a["n_human_edits"] == 1 and a["reviewer_ids"] == [7]
    assert a["change_type"] == "rewrite"        # injected cosine 0.4 < REWRITE_MAX_COSINE
    assert a["cosine_baseline_final"] == 0.4


def test_baseline_first_human_save_is_lower_bound():
    # No user=None snapshot (draft written via .update(), unrecorded) → baseline is the
    # first human save and the delta is a LOWER BOUND (delta_exact False).
    d = date(2026, 1, 1)
    rows = [
        _row("", "+", 9, d),
        _row("human first save", "~", 9, d),
        _row("human final answer after more edits", "~", 9, d),
    ]
    b = analyze_answer_history(rows, "human final answer after more edits", NF,
                               lambda x, y: 0.9)
    assert b["baseline_kind"] == "first_human_save"
    assert b["delta_exact"] is False
    assert b["baseline_answer"] == "human first save"
    assert b["change_type"] != "n/a"            # a delta IS computed (lower bound)


def test_saved_once_lower_bound_zero_delta():
    # Saved once (first non-blank == final): lower-bound delta is 0 (no post-save edits),
    # but it's still flagged lower-bound — not provably the verbatim draft.
    d = date(2026, 1, 1)
    rows = [_row("", "+", 9, d), _row("only version", "~", 9, d)]
    a = analyze_answer_history(rows, "only version", NF, lambda x, y: 1.0)
    assert a["baseline_kind"] == "first_human_save"
    assert a["delta_exact"] is False
    assert a["change_type"] == "none"
