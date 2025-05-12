from langchain_openai import ChatOpenAI
import logging
from typing import Literal
from pathlib import Path

from toxtempass import config, LLM_API_KEY, LLM_ENDPOINT
from langchain_community.document_loaders import (
    BSHTMLLoader,
    TextLoader,
    UnstructuredWordDocumentLoader,
)
from PIL import Image
from io import BytesIO
from pypdf import PdfReader
from langchain_core.messages import BaseMessage
from pydantic import Field, model_validator

import base64

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


# Set up logging
logger = logging.getLogger("document_loader")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def get_text_or_bytes_perfile_dict(document_filenames: list[str | Path])-> dict[str, dict[str, str ]]:
    """
    Load content from a list of documents and return a dictionary mapping filenames to their content.

    Args:
    document_filenames (list of str): List of file paths to the documents.

    Returns:
    dict: A dictionary where keys are filenames and values are the loaded document content or encoded bytes for images.
    """
    # coherce paths of type str to Path elements:
    document_filenames: list[Path] = [Path(path) for path in document_filenames]
    document_contents = {}

    for context_filename in document_filenames:
        text = None
        img_bytestring = None
        suffix = context_filename.suffix.lower()

        try:
            if suffix == ".pdf":
                with open(context_filename, "rb") as file:
                    reader = PdfReader(file)
                    paragraphs = [
                        p.extract_text().strip()
                        for p in reader.pages
                        if p.extract_text()
                    ]
                    text = "\n".join(paragraphs)

            elif suffix in [".txt", ".md"]:
                loader = TextLoader(
                    file_path=context_filename, autodetect_encoding=True
                )
                text = loader.load()[0].page_content

            elif suffix == ".html":
                loader = BSHTMLLoader(context_filename, open_encoding="utf-8")
                text = loader.load().page_content.replace("\n", "")

            elif suffix == ".docx":
                loader = UnstructuredWordDocumentLoader(str(context_filename))
                text = loader.load()[0].page_content

            elif suffix == ".png":
                img = Image.open(context_filename)
                s = BytesIO()
                img.save(s, "png")
                img_bytestring = base64.b64encode(s.getvalue()).decode("utf-8")

            if text:
                document_contents[str(context_filename)] = {"text": text}
                logger.info(f"The file '{context_filename}' was read successfully.")
            elif img_bytestring:
                document_contents[str(context_filename)] = {"encodedbytes": img_bytestring}
                logger.info(f"The file '{context_filename}' was read successfully.")

        except Exception as e:
            logger.error(f"Error reading '{context_filename}': {e}")
        # Here let's remove the files after reading them.
        context_filename.unlink()

    return document_contents


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
