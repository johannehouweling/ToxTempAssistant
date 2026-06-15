"""Tests for the trivial / non-trivial / abstention labels in ``parse_answer``.

Covers prose, structured-JSON, and the *non-trivial abstention* case (a model that
prints a "not found" marker but still answers). ``is_trivial`` drives cosine/embedding
exclusion and completeness; ``is_abstention`` flags the not-found signal. The legacy
``not_found`` flag keeps its old exact-string meaning.
"""

import pytest

from toxtempass.evaluation.real_world.answer_utils import parse_answer

NOT_FOUND = "Answer not found in documents."


# ── (is_trivial, is_abstention) classification ────────────────────────────────
@pytest.mark.parametrize(
    "text, trivial, abstention",
    [
        # empty -> trivial, no abstention signal
        ("", True, False),
        ("   ", True, False),
        # plain answers -> non-trivial, no abstention
        ("Primary human umbilical vein endothelial cells (HUVECs). _(Source: sop.pdf)_",
         False, False),
        ("HepG2 hepatocellular carcinoma cells.", False, False),
        # clean abstentions (exact + paraphrased) -> trivial + abstention
        (NOT_FOUND, True, True),
        ("No relevant information is available in the source documents.", True, True),
        ("This detail could not be found in the provided documents.", True, True),
        # non-trivial abstention ("hedged"): marker present but still answers
        ("The exposure duration is not stated in the documents. However, based on the "
         "protocol, cells are exposed to the compound for 24 hours. _(Source: sop.pdf)_",
         False, True),
        ("Answer not found in documents. That said, the assay uses a 96-well plate "
         "format with three biological replicates per condition.",
         False, True),
        # marker + only trivial leftover -> still a (trivial) abstention
        ("Not found in the documents. N/A.", True, True),
    ],
)
def test_prose_labels(text, trivial, abstention):
    parsed = parse_answer(text)
    assert parsed["is_trivial"] is trivial
    assert parsed["is_abstention"] is abstention


@pytest.mark.parametrize(
    "payload, trivial, abstention, not_found",
    [
        ('{"answerable":"yes","answer":"HepG2 cells","confidence":"high"}',
         False, False, False),
        ('{"answerable":"no","answer":null,"supporting_quotes":[]}',
         True, True, True),
        ('{"answerable":"partial","answer":"Cells exposed for 24 h","confidence":"low"}',
         False, True, False),
        # contradiction: says "no" yet returns an answer -> non-trivial abstention
        ('{"answerable":"no","answer":"Actually exposed for 24 h"}',
         False, True, True),
        # answerable yes but empty answer -> trivial, no abstention
        ('{"answerable":"yes","answer":""}', True, False, True),
    ],
)
def test_structured_labels(payload, trivial, abstention, not_found):
    parsed = parse_answer(payload)
    assert parsed["is_structured"] is True
    assert parsed["is_trivial"] is trivial
    assert parsed["is_abstention"] is abstention
    assert parsed["not_found"] is not_found


# ── abstention marker vs legacy not_found divergence ──────────────────────────
def test_paraphrased_abstention_sets_marker_but_not_legacy_not_found():
    """A paraphrased abstention trips the new marker but not the exact-string flag."""
    parsed = parse_answer("No relevant information is available in the documents.")
    assert parsed["is_abstention"] is True
    assert parsed["is_trivial"] is True
    assert parsed["not_found"] is False  # exact not_found_string absent


# ── substantive_text extraction ───────────────────────────────────────────────
def test_nontrivial_abstention_substantive_text_strips_marker_and_citation():
    text = ("The donor age is not specified in the documents. However, the cells are "
            "primary human hepatocytes from a single donor. _(Source: protocol.pdf)_")
    parsed = parse_answer(text)
    assert parsed["is_trivial"] is False and parsed["is_abstention"] is True
    sub = parsed["substantive_text"]
    assert "primary human hepatocytes" in sub
    assert "not specified" not in sub          # abstention sentence removed
    assert "Source:" not in sub                # citation removed


def test_plain_answer_substantive_text_drops_citation():
    parsed = parse_answer("HepG2 cells. _(Source: sop.pdf)_")
    assert parsed["is_trivial"] is False and parsed["is_abstention"] is False
    assert "HepG2 cells" in parsed["substantive_text"]
    assert "Source:" not in parsed["substantive_text"]


# ── answer_scenario (the 4 reduced scenarios) ─────────────────────────────────
@pytest.mark.parametrize(
    "text, scenario",
    [
        # abstention marker (exact or paraphrased), no content -> abstained
        (NOT_FOUND, "abstained"),
        ("No relevant information is available in the source documents.", "abstained"),
        # abstention marker (exact or paraphrased) + content -> hedged
        ("Answer not found in documents. That said, the assay uses a 96-well plate "
         "format with three biological replicates per condition.", "hedged"),
        ("The exposure duration is not stated in the documents. However, based on the "
         "protocol, cells are exposed to the compound for 24 hours.", "hedged"),
        # plain answer
        ("HepG2 hepatocellular carcinoma cells.", "answered"),
        # blank
        ("", "empty"),
    ],
)
def test_answer_scenario(text, scenario):
    assert parse_answer(text)["answer_scenario"] == scenario


@pytest.mark.parametrize(
    "payload, scenario",
    [
        ('{"answerable":"no","answer":null}', "abstained"),
        ('{"answerable":"partial","answer":"24 h exposure"}', "hedged"),
        ('{"answerable":"yes","answer":"HepG2 cells"}', "answered"),
        ('{"answerable":"yes","answer":""}', "empty"),
    ],
)
def test_answer_scenario_structured(payload, scenario):
    assert parse_answer(payload)["answer_scenario"] == scenario


# ── back-compat: existing keys preserved ──────────────────────────────────────
def test_legacy_keys_present():
    parsed = parse_answer("HepG2 cells.")
    for key in ("answerable", "answer", "supporting_quotes", "confidence", "source",
                "not_found", "is_structured"):
        assert key in parsed
