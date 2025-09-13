import logging
import os
from functools import lru_cache
from typing import Literal

from django.core.exceptions import ImproperlyConfigured
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from pydantic import Field, model_validator

# Get logger
logger = logging.getLogger("llm")


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    """Minimal lazy builder; safe at import time. Reads config/env *now*,not earlier, and only constructs when first called."""
    # Import here to avoid early import-time races
    try:
        from toxtempass import config, LLM_API_KEY, LLM_ENDPOINT
    except Exception:
        config = None
        LLM_API_KEY = None
        LLM_ENDPOINT = None

    api_key = (
        LLM_API_KEY
        or (getattr(config, "api_key", None) if config else None)
        or os.getenv("OPENAI_API_KEY")
    )

    base_url = (
        LLM_ENDPOINT
        or (getattr(config, "url", None) if config else None)
        or os.getenv("OPENAI_BASE_URL")
    )

    model = (getattr(config, "model", None) if config else None) or "gpt-4o-mini"
    temperature = (getattr(config, "temperature", None) if config else None) or 0
    extra_headers = getattr(config, "extra_headers", None) if config else None

    if not api_key and not os.getenv("TESTING"): # allow missing key in tests
        raise ImproperlyConfigured(
            "OpenAI API key missing (LLM_API_KEY / config.api_key / OPENAI_API_KEY)."
        )

    logger.info(f"LLM configured: model={model}, base_url={base_url!s}")
    return ChatOpenAI(
        api_key=api_key,
        base_url=base_url,  # fine if None
        model=model,
        temperature=temperature,
        default_headers=extra_headers,
        timeout=30,
    )


image_accept_files = [
    ".png",
]
text_accept_files = [".pdf", ".docx", ".txt", ".md", ".html"]
allowed_mime_types = [
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
    "text/markdown",
    "text/html",
    "image/png",
]


class ImageMessage(BaseMessage):
    type: Literal["image"] = Field(default="image")
    content: str  # Base64-encoded image string
    filename: str

    @model_validator(mode="before")
    def validate_fields(cls, values: dict) -> dict:
        """Validate that content and filename are provided."""
        content = values.get("content")
        filename = values.get("filename")
        if not content:
            raise ValueError("Image content must be provided.")
        if not filename:
            raise ValueError("Filename must be provided.")
        return values

    def to_dict(self) -> dict:
        """Convert the message to a dictionary."""
        return {"type": self.type, "content": self.content, "filename": self.filename}

    @classmethod
    def from_dict(cls, data: dict) -> "ImageMessage":
        """Create an instance from a dictionary."""
        return cls(content=data["content"], filename=data["filename"])
