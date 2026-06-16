"""Pure (Django-free) logic for gold-standard draft detection and edit-typing.

Scientist-reviewed answers were drafted by gpt-4o-mini, then accepted/edited by a human.
Whether the gpt-4o-mini DRAFT survives in django-simple-history is **era-dependent**
(git-verified):

* Drafts written **before 2025-09-13** used ``answer.save()`` → simple-history snapshotted
  the draft as the earliest non-blank ``~`` row. Detectable + diffable here.
* Drafts written **on/after 2025-09-13** (commit ``5f12fd7``) use queryset ``.update()``,
  which bypasses simple-history → the draft is NOT in history and must be reconstructed by
  re-running gpt-4o-mini (a separate follow-up).

Answer rows are created blank (``forms.py`` get_or_create with answer_text=""), so every
history starts at ``""`` and the draft, when present, is the **first non-blank snapshot**.
In the early *sync* era that draft-save row even carries ``history_user=owner``, so the
first non-blank snapshot is treated as the draft and human-edit counting starts from the
*second* non-blank snapshot.

Edit-typing uses **semantic cosine similarity** (embeddings) as the primary signal for
*meaning* change, with a lexical (difflib) ratio + length only to separate cosmetic tweaks
from expansions/trims. The cosine is **injected** (``cosine_fn``) so this module stays
Django-/API-free and deterministic; the caller wires in the project's SHA-cached embedding
similarity, keeping the analysis reproducible. Tests:
``toxtempass/tests/test_gold_standard_edit_analysis.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from difflib import SequenceMatcher
from typing import Any

# ── tuning constants (defined once, here — the single place to adjust behaviour) ──
# Commit 5f12fd7 (2025-09-13) switched the generation write from answer.save() to
# queryset .update(); drafts written on/after this date are NOT in simple-history.
DRAFT_CUTOFF = date(2025, 9, 13)

# Edit-type thresholds. Cosine is the embedding cosine in [-1, 1] (text-embedding-3-large)
# and lexical_ratio is a difflib ratio in [0, 1]. Tune here, nowhere else.
REWRITE_MAX_COSINE = 0.75   # semantic cosine below this ⇒ meaning changed ⇒ rewrite
COSMETIC_MIN_LEXICAL = 0.9  # surface (char) ratio at/above this ⇒ cosmetic tweak
GROWTH_FACTOR = 1.2         # length multiple for expand (final) / trim (draft)

CosineFn = Callable[[str, str], float]


def _is_abstain(text: str, not_found_str: str) -> bool:
    """Return True if ``text`` is empty or the abstention sentinel ('not found')."""
    t = (text or "").strip()
    return not t or not_found_str.strip().lower() in t.lower()


def classify_edit(
    draft: str, final: str, cosine: float, not_found_str: str
) -> dict[str, Any]:
    """Classify the draft→final change into an edit type, using semantic cosine + surface.

    Types: ``none`` (verbatim), ``abstain_to_answer`` (model abstained, human answered — a
    confirmed recall gap), ``answer_to_abstain`` (human rejected a likely hallucination),
    ``rewrite`` (meaning changed — low cosine), ``cosmetic`` (tiny surface change),
    ``expand`` / ``trim`` (meaning kept, content added/removed), ``edit`` (reword/other).
    """
    d, f = (draft or "").strip(), (final or "").strip()
    lexical_ratio = SequenceMatcher(None, d, f).ratio()
    chars_added = max(0, len(f) - len(d))
    chars_removed = max(0, len(d) - len(f))
    d_abstain, f_abstain = _is_abstain(d, not_found_str), _is_abstain(f, not_found_str)

    # Cosine (meaning) decides rewrite; lexical ratio (surface) decides cosmetic; length
    # decides expand/trim; everything else is a moderate edit (e.g. a reword).
    if d == f:
        etype = "none"
    elif d_abstain and not f_abstain:
        etype = "abstain_to_answer"
    elif f_abstain and not d_abstain:
        etype = "answer_to_abstain"
    elif cosine < REWRITE_MAX_COSINE:
        etype = "rewrite"
    elif lexical_ratio >= COSMETIC_MIN_LEXICAL:
        etype = "cosmetic"
    elif len(f) >= len(d) * GROWTH_FACTOR:
        etype = "expand"
    elif len(d) >= len(f) * GROWTH_FACTOR:
        etype = "trim"
    else:
        etype = "edit"

    return {
        "edit_type": etype,
        "cosine": round(float(cosine), 4),
        "lexical_ratio": round(lexical_ratio, 4),
        "chars_added": chars_added,
        "chars_removed": chars_removed,
    }


def analyze_answer_history(
    rows: list[dict],
    final_text: str,
    not_found_str: str,
    cosine_fn: CosineFn,
    cutoff: date = DRAFT_CUTOFF,
) -> dict[str, Any]:
    """Reconstruct the draft + human-review signal from one answer's history rows.

    ``rows`` are the answer's ``HistoricalAnswer`` records as dicts with keys
    ``answer_text``, ``history_type`` ('+'/'~'/'-'), ``history_user_id``, ``history_date``
    (a ``date``). ``final_text`` is the live accepted answer (gold). ``cosine_fn(a, b)``
    returns the semantic cosine of two texts (inject the project's cached embedding sim).
    Returns draft detection, edit-typing (when the draft is recoverable), and human-edit
    evidence.
    """
    ordered = sorted(rows, key=lambda r: r["history_date"])
    nonblank = [r for r in ordered if (r.get("answer_text") or "").strip()]

    out: dict[str, Any] = {
        "n_history": len(ordered),
        "n_nonblank_snapshots": len(nonblank),
        "draft_in_history": False,
        "draft_source": "none",
        "draft_text": "",
        "draft_date": None,
        "n_human_edits": 0,
        "reviewer_ids": [],
        "edit_type": "n/a",
        "cosine": "",
        "lexical_ratio": "",
        "chars_added": "",
        "chars_removed": "",
    }

    draft_row = None
    if nonblank and nonblank[0]["history_date"] < cutoff:
        draft_row = nonblank[0]
        out.update(
            draft_in_history=True,
            draft_source="history",
            draft_text=draft_row.get("answer_text") or "",
            draft_date=draft_row["history_date"],
        )

    # Human-edit evidence: '~' rows authored by a logged-in user, excluding the draft row.
    human_rows = [
        r
        for r in ordered
        if r.get("history_type") == "~"
        and r.get("history_user_id") is not None
        and r is not draft_row
    ]
    out["n_human_edits"] = len(human_rows)
    out["reviewer_ids"] = sorted({r["history_user_id"] for r in human_rows})

    if out["draft_in_history"]:
        cos = cosine_fn(out["draft_text"], final_text)
        out.update(classify_edit(out["draft_text"], final_text, cos, not_found_str))

    return out
