from langchain_openai import ChatOpenAI
import logging
from typing import Literal
from toxtempass import config, LLM_API_KEY, LLM_ENDPOINT
from langchain_core.messages import BaseMessage
from pydantic import Field, model_validator


# Get logger
logger = logging.getLogger("llm")

# Initialize language models based on environment variables
llm = None

if LLM_API_KEY and LLM_ENDPOINT:
    llm = ChatOpenAI(
        api_key=LLM_API_KEY,
        base_url=config.url,
        temperature=config.temperature,
        model=config.model,
        default_headers=config.extra_headers,
        # base_url=config.url,
    )
    logger.info(f"Using ({config.model}) at {LLM_ENDPOINT}.")
else:
    logger.error("Required environment variables are missing")



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
        content = values.get("content")
        filename = values.get("filename")
        if not content:
            raise ValueError("Image content must be provided.")
        if not filename:
            raise ValueError("Filename must be provided.")
        return values

    def to_dict(self) -> dict:
        return {"type": self.type, "content": self.content, "filename": self.filename}

    @classmethod
    def from_dict(cls, data: dict) -> "ImageMessage":
        return cls(content=data["content"], filename=data["filename"])


chain = llm
