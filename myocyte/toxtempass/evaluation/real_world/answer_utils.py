"""Shared answer-normalization helpers for the Tier 3 (real-world) evaluation.

Kept dependency-light (only stdlib + ``toxtempass.config``) so both the generation
pipeline (`real_world.py`) and the metrics step (`tier3_metrics.py`) can import it
without pulling in the heavy answering stack.
"""

import json
import re

from toxtempass import config


def parse_answer(answer_text: str | None) -> dict:
    """Normalize a raw model answer (prose OR structured JSON) to common fields.

    The structured-output experiment makes the model emit a JSON object per
    question; the default prompt yields prose. This returns a uniform dict so
    both shapes compare on equal footing::

        {answerable, answer, supporting_quotes, confidence, source,
         not_found, is_structured}

    ``not_found`` is True when the answer is empty, equals the production
    ``not_found_string`` (prose), or the structured answer is ``answerable: no``
    / ``answer: null``.
    """
    text = (answer_text or "").strip()
    result = {
        "answerable": "",
        "answer": text,
        "supporting_quotes": [],
        "confidence": "",
        "source": "",
        "not_found": False,
        "is_structured": False,
    }
    if not text:
        result["not_found"] = True
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
        result.update(
            is_structured=True,
            answerable=str(parsed.get("answerable") or "").strip().lower(),
            answer="" if ans is None else str(ans),
            supporting_quotes=[str(q) for q in quotes],
            confidence=str(parsed.get("confidence") or "").strip().lower(),
            source=str(parsed.get("source") or "").strip(),
        )
        # not_found when explicitly unanswerable OR the answer is null / empty /
        # whitespace-only / a non-string that stringifies to nothing.
        result["not_found"] = (
            result["answerable"] == "no" or not result["answer"].strip()
        )
        return result

    # Prose fallback.
    result["not_found"] = config.not_found_string in text
    return result
