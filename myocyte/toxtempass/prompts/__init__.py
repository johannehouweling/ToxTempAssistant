"""Prompt stack utilities for ToxTempAssistant."""

from __future__ import annotations

import hashlib
from typing import Mapping

from toxtempass.prompts.utils import (
    DEFAULT_SECTIONS,
    DEFAULTS,
    load_manifest,
    path_for,
    read_text,
    replace_placeholders,
    validate_manifest,
)


def build_base_prompt(not_found_string: str, question_type: str = "descriptive") -> str:
    """Assemble the base prompt from the prompt stack."""

    manifest = load_manifest()
    validate_manifest(manifest or {})
    replacements = {"{not_found_string}": not_found_string}

    sections = []

    def add_block(title: str, path_key: str) -> None:
        path = path_for(path_key, manifest)
        content = replace_placeholders(read_text(path), replacements)
        sections.append(f"{title}\n{content}")

    # Optional system role
    add_block("SYSTEM ROLE", "system_role")

    # Global and assay-aware framing
    add_block("GLOBAL CONSTRAINTS", "global_constraints")
    add_block("ASSAY CONTEXT", "assay_context")

    # Section (domain) constraints
    sections_manifest = manifest.get("sections") if isinstance(manifest, Mapping) else {}
    if isinstance(sections_manifest, Mapping) and sections_manifest:
        for name in sections_manifest.keys():
            add_block(f"SECTION RULES: {name.replace('_', ' ').upper()}", f"sections.{name}")
    else:
        for name in DEFAULT_SECTIONS.keys():
            add_block(f"SECTION RULES: {name.replace('_', ' ').upper()}", f"sections.{name}")

    # Question-type specific instructions
    qt_key = f"question_types.{question_type}"
    qt_manifest = manifest.get("question_types", {}) if isinstance(manifest, Mapping) else {}
    if qt_key not in qt_manifest and qt_key not in DEFAULTS:
        qt_key = "question_types.descriptive"
    add_block(f"QUESTION TYPE: {question_type.upper()}", qt_key)

    # Process instructions
    add_block("PROCESS", "process")

    # Output contract (question-type specific where present)
    output_key = f"output.{question_type}"
    output_manifest = manifest.get("output", {}) if isinstance(manifest, Mapping) else {}
    if output_key not in output_manifest and output_key not in DEFAULTS:
        output_key = "output.default"
    add_block("OUTPUT", output_key)

    return "\n\n".join(sections).strip()


def get_prompt_hash(not_found_string: str, question_type: str = "descriptive") -> str:
    """Return a short hash for the assembled prompt to tag outputs."""
    prompt_text = build_base_prompt(not_found_string, question_type)
    return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:8]


manifest = load_manifest()
prompt_version: str = manifest.get("version", DEFAULTS["version"])
