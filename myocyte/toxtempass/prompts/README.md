# ToxTempAssistant Prompt Stack

This directory contains the deterministic, auditable prompt stack for ToxTempAssistant. Prompts are assembled from modular text blocks (no few-shot examples, no self-reflection) using the manifest in `versions/v1.0/manifest.yaml`.

## Layout
- `blocks/` – runtime prompt blocks
  - `system/` – role definition
  - `global/` – global constraints (source-bounded, abstention)
  - `assay_context/` – assay-aware framing (scope, non-assumptions)
  - `process/` – internal checklist
  - `question_types/` – per-question-type rules (boolean, descriptive)
  - `sections/` – domain constraints (biological model, validity)
  - `output/` – output contracts (base, boolean)
- `versions/v1.0/manifest.yaml` – references all blocks; assembly order is fixed.
- `__init__.py` / `utils.py` – prompt assembly utilities and manifest validation.

## Assembly order
SYSTEM ROLE → GLOBAL CONSTRAINTS → ASSAY CONTEXT → SECTION RULES → QUESTION-TYPE RULES → PROCESS → OUTPUT CONTRACT → QUESTION → SOURCE DOCUMENTS.

## Usage
- The app calls `build_base_prompt(not_found_string, question_type)` to assemble the prompt; defaults to descriptive if no question_type is provided.
- `prompt_version` comes from the manifest; `get_prompt_hash` gives a short hash of the assembled prompt for traceability.

## Principles
- Zero-shot, instruction-only; no few-shot or multi-pass logic.
- Source-bounded; abstain with `{not_found_string}` when missing/ambiguous/conflicting.
- Assay-aware framing prevents cross-assay assumptions (no implicit OECD TGs/endpoints).
- Prompts are versioned in Git; freeze releases can be archived (e.g., Zenodo) for reproducibility.
