"""Shared answer-normalization helpers for the Tier 3 (real-world) evaluation.

Kept dependency-light (only stdlib + ``toxtempass.config``) so both the generation
pipeline (`real_world.py`) and the metrics step (`tier3_metrics.py`) can import it
without pulling in the heavy answering stack.

Two paper-aligned booleans classify every answer (matching the "trivial / non-trivial"
and "abstention" language used in the ToxTemp evaluation):

    is_trivial      -- the answer has no substantive content (an abstention or empty);
                       excluded from cosine agreement; completeness = mean(~is_trivial).
                       Improves on the exact-string ``answer != not_found_string`` test
                       by also catching paraphrased abstentions.
    is_abstention   -- the model signalled "not found" (a not-found marker in prose, or
                       structured ``answerable: no`` / ``partial``).

The two axes are orthogonal, so the four observable cases fall out as:

    non-trivial & not abstention  -> a plain answer
    non-trivial & abstention      -> answered despite abstaining (a "hedged" answer)
    trivial     & abstention      -> a clean abstention
    trivial     & not abstention  -> empty

The refusal/abstention rule lives here, once, so embeddings, cosine agreement,
completeness and judge scoring all filter on the same labels.
"""

import json
import re

from toxtempass import config

# ── abstention detection ──────────────────────────────────────────────────────
# Broad paraphrase set (models rarely emit the exact not_found_string verbatim).
_ABSTENTION_SUBPATTERNS = [
    r"answer not found",
    r"not (?:found|available|present|provided|specified|mentioned|stated|described|"
    r"included|contained|given)\s+(?:in|within)\b",
    r"not found in (?:the )?(?:provided )?(?:documents?|context|sources?|text|material)",
    r"no (?:relevant )?information (?:is )?(?:available|found|provided|given)",
    r"could not (?:find|locate|determine|identify)",
    r"(?:could|can)not be (?:found|located|determined)",
    r"\bnot be (?:found|located|determined)\b",
    r"cannot (?:find|locate|determine|be (?:found|determined))",
    r"unable to (?:find|locate|determine|answer|identify)",
    r"does not (?:contain|mention|provide|specify|include|state)",
    r"(?:is|are|was|were)\s+not\s+(?:specified|mentioned|provided|available|stated|"
    r"described|given|reported)\b",
    r"no mention of",
    r"not addressed (?:in|by) the",
]
_ABSTENTION_RE = re.compile("|".join(_ABSTENTION_SUBPATTERNS), re.IGNORECASE)

# Markdown-style source citations are not substantive content.
_CITATION_RE = re.compile(r"_?\(Sources?:\s*[^)]*\)_?", re.IGNORECASE)

# Split into sentence-ish units on sentence punctuation or newlines.
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")

# Min words remaining (after dropping abstention sentences) to call prose non-trivial.
MIN_SUBSTANTIVE_WORDS = 4


def _has_abstention_marker(text: str, extra_marker: str | None) -> bool:
    """True if the text contains any abstention phrase (pattern set or the exact marker)."""
    if _ABSTENTION_RE.search(text):
        return True
    return bool(extra_marker) and extra_marker.lower() in text.lower()


def _substantive_prose(text: str, extra_marker: str | None) -> str:
    """Return the content left after removing citations and abstention sentences."""
    stripped = _CITATION_RE.sub(" ", text)
    kept = []
    for part in _SENT_SPLIT_RE.split(stripped):
        p = part.strip()
        if not p:
            continue
        if _ABSTENTION_RE.search(p) or (extra_marker and extra_marker.lower() in p.lower()):
            continue
        kept.append(p)
    return " ".join(kept).strip()


def _scenario(is_abstention: bool, is_trivial: bool) -> str:
    """Name the answer scenario from the (abstention x trivial) axes.

    Returns one of::

        answered   -- substantive content, no abstention marker
        hedged     -- abstention marker BUT substantive content
        abstained  -- abstention marker, no substantive content
        empty      -- blank answer (no content, no marker)
    """
    if not is_abstention:
        return "empty" if is_trivial else "answered"
    return "abstained" if is_trivial else "hedged"


def parse_answer(answer_text: str | None) -> dict:
    """Normalize a raw model answer (prose OR structured JSON) to common fields.

    Returns a uniform dict::

        {answerable, answer, supporting_quotes, confidence, source,
         not_found, is_structured,
         is_trivial, is_abstention, substantive_text}

    ``not_found`` keeps its legacy meaning (empty, prose ``not_found_string``
    present, or structured ``answerable: no`` / null answer) for back-compat.
    Prefer ``is_trivial`` / ``is_abstention`` in new code.
    """
    text = (answer_text or "").strip()
    not_found_string = config.not_found_string
    result = {
        "answerable": "",
        "answer": text,
        "supporting_quotes": [],
        "confidence": "",
        "source": "",
        "not_found": False,
        "is_structured": False,
        "is_trivial": False,
        "is_abstention": False,
        "answer_scenario": "answered",
        "substantive_text": text,
    }

    if not text:
        result.update(not_found=True, is_trivial=True, substantive_text="",
                      answer_scenario="empty")
        return result

    # Structured JSON? Strip code fences first (some models wrap output).
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    parsed = None
    if cleaned.startswith("{"):
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            parsed = None

    if isinstance(parsed, dict) and ("answerable" in parsed or "answer" in parsed):
        ans = parsed.get("answer")
        quotes = parsed.get("supporting_quotes") or []
        if not isinstance(quotes, list):
            quotes = [str(quotes)]
        answerable = str(parsed.get("answerable") or "").strip().lower()
        answer = "" if ans is None else str(ans)
        result.update(
            is_structured=True,
            answerable=answerable,
            answer=answer,
            supporting_quotes=[str(q) for q in quotes],
            confidence=str(parsed.get("confidence") or "").strip().lower(),
            source=str(parsed.get("source") or "").strip(),
            substantive_text=answer.strip(),
        )
        result["not_found"] = answerable == "no" or not answer.strip()
        result["is_abstention"] = answerable in {"no", "partial"}
        result["is_trivial"] = not answer.strip()
        result["answer_scenario"] = _scenario(
            result["is_abstention"], result["is_trivial"]
        )
        return result

    # Prose fallback.
    marker = _has_abstention_marker(text, not_found_string)
    result["not_found"] = not_found_string in text  # legacy semantics, unchanged
    result["is_abstention"] = marker
    if not marker:
        result["is_trivial"] = False
        result["substantive_text"] = _CITATION_RE.sub(" ", text).strip() or text
        result["answer_scenario"] = "answered"
        return result

    substantive = _substantive_prose(text, not_found_string)
    result["substantive_text"] = substantive
    result["is_trivial"] = len(substantive.split()) < MIN_SUBSTANTIVE_WORDS
    result["answer_scenario"] = _scenario(True, result["is_trivial"])
    return result


# ── embedding normalization (cross-model agreement only) ──────────────────────
# Provenance prefixes from the open_knowledge prompt; markdown bits. (Source tags
# are handled by the shared _CITATION_RE above.)
_PROVENANCE_PREFIX_RE = re.compile(r"\[(?:DOC|KNOWLEDGE)\]", re.IGNORECASE)
_HEADER_RE = re.compile(r"(?m)^\s{0,3}#{1,6}\s*")   # markdown ATX headers
_HR_RE = re.compile(r"(?m)^\s*-{3,}\s*$")           # horizontal rule (--- line)
_BULLET_RE = re.compile(r"(?m)^\s*[-+]\s+")         # leading list bullets (- / +)
_WS_RE = re.compile(r"\s+")


def normalize_for_embedding(text: str | None) -> str:
    """Strip markdown + provenance for cross-model AGREEMENT embeddings.

    Makes embeddings compare semantic content, not citation style or formatting.
    Removes source citations (shared ``_CITATION_RE``), ``[DOC]``/``[KNOWLEDGE]``
    prefixes, markdown emphasis (``*``/``**``), inline-code backticks, ATX headers,
    leading list bullets and ``---`` rules, then collapses whitespace. Underscores
    are intentionally NOT stripped wholesale — markdown italic ``_x_`` is rare here
    and removing ``_`` would mangle snake_case terms / filenames; only the
    underscores wrapping a source tag are removed (by ``_CITATION_RE``).

    Use ONLY for the agreement (pairwise-cosine) path — NOT for quality/faithfulness
    scoring, which must see the real answer (citations included). Apply to the
    answer's ``substantive_text`` (already citation/abstention-stripped) or raw
    ``answer``; it is idempotent w.r.t. citation removal.
    """
    if not text:
        return ""
    t = _CITATION_RE.sub(" ", text)
    t = _PROVENANCE_PREFIX_RE.sub(" ", t)
    t = t.replace("*", "").replace("`", "")  # bold/italic asterisks + inline code
    t = _HEADER_RE.sub("", t)
    t = _HR_RE.sub(" ", t)
    t = _BULLET_RE.sub("", t)
    return _WS_RE.sub(" ", t).strip()
