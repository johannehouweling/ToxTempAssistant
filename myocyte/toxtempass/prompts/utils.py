"""Utility functions for assembling ToxTempAssistant prompts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

PROMPTS_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = PROMPTS_DIR / "versions" / "v1.0" / "manifest.yaml"

DEFAULTS: dict[str, str] = {
    "version": "unversioned",
    "system_role": "blocks/system/role.txt",
    "global_constraints": "blocks/global/constraints.txt",
    "assay_context": "blocks/assay_context/base.txt",
    "process": "blocks/process/default.txt",
    "output.default": "blocks/output/base.txt",
    "output.boolean": "blocks/output/boolean.txt",
    "question_types.boolean": "blocks/question_types/boolean.txt",
    "question_types.descriptive": "blocks/question_types/descriptive.txt",
    "sections.biological_model": "blocks/sections/biological_model.txt",
    "sections.validity": "blocks/sections/validity.txt",
}

DEFAULT_SECTIONS: dict[str, str] = {
    "biological_model": "blocks/sections/biological_model.txt",
    "validity": "blocks/sections/validity.txt",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def replace_placeholders(text: str, replacements: Mapping[str, str]) -> str:
    updated = text
    for needle, value in replacements.items():
        updated = updated.replace(needle, value)
    return updated


def load_manifest() -> dict[str, Any]:
    """Load the prompt manifest if present; return empty dict otherwise."""
    if not MANIFEST_PATH.exists():
        return {}
    return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8")) or {}


def path_for(key: str, manifest: Mapping[str, Any]) -> Path:
    """Resolve a manifest key to a Path."""
    parts = key.split(".")
    value: Any = manifest
    for part in parts:
        if isinstance(value, Mapping) and part in value:
            value = value[part]
        else:
            value = None
            break
    rel_path = value if isinstance(value, str) else DEFAULTS.get(key)
    if not rel_path:
        raise KeyError(f"Missing path for key '{key}' in manifest defaults.")
    return PROMPTS_DIR / rel_path


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    """Validate manifest paths exist and are files."""

    def ensure_exists(key: str) -> None:
        path = path_for(key, manifest)
        if not path.is_file():
            raise FileNotFoundError(f"Prompt file not found for key '{key}': {path}")

    # Base required blocks
    for key in ("system_role", "global_constraints", "assay_context", "process"):
        ensure_exists(key)

    # Question types
    qt_manifest = manifest.get("question_types", {}) if isinstance(manifest, Mapping) else {}
    qt_keys = qt_manifest.keys() or ("descriptive",)
    for qt in qt_keys:
        ensure_exists(f"question_types.{qt}")

    # Sections
    sections_manifest = manifest.get("sections", {}) if isinstance(manifest, Mapping) else {}
    section_keys = sections_manifest.keys() or DEFAULT_SECTIONS.keys()
    for sec in section_keys:
        ensure_exists(f"sections.{sec}")

    # Output contracts
    output_manifest = manifest.get("output", {}) if isinstance(manifest, Mapping) else {}
    output_keys = output_manifest.keys() or ("default",)
    for out in output_keys:
        ensure_exists(f"output.{out}")
