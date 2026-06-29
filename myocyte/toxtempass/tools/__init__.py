"""LLM tooling for ToxTempAssistant (prompts and related helpers).

Prompt text lives in :mod:`toxtempass.tools.prompts`, extracted out of
``toxtempass.Config`` so the wording sits in one place separate from app
constants. ``Config`` re-exports the prompts (``config.base_prompt`` etc.) so
existing call sites keep working unchanged.
"""
