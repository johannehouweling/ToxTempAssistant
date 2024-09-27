import os
from dotenv import load_dotenv
from langchain_openai import OpenAI, AzureChatOpenAI
import logging
from pathlib import Path
from myocyte import settings
from toxtempass import config
from langchain_community.document_loaders import (
    BSHTMLLoader,
    TextLoader,
    UnstructuredWordDocumentLoader,
)
from pypdf import PdfReader
from langchain_core.prompts import PromptTemplate


# Load environment variables from the .env file
load_dotenv(Path(settings.BASE_DIR).with_name(".env"))

# Get logger
logger = logging.getLogger("langchain")

# Access environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LOCAL_OPENAI_API_KEY = os.getenv("LOCAL_OPENAI_API_KEY")
LOCAL_OPENAI_ENDPOINT = os.getenv("LOCAL_OPENAI_ENDPOINT")
LOCAL_OPENAI_DEPLOYMENT_ID = os.getenv("LOCAL_OPENAI_DEPLOYMENT_ID")
LOCAL_OPENAI_API_VERSION = os.getenv("LOCAL_OPENAI_API_VERSION")

# Initialize language models based on environment variables
if OPENAI_API_KEY:
    llm = OpenAI(
        api_key=OPENAI_API_KEY,
        temperature=config.temperature,
    )
    logger.info("LLM (OpenAI) loaded")
elif (
    LOCAL_OPENAI_API_KEY
    and LOCAL_OPENAI_ENDPOINT
    and LOCAL_OPENAI_DEPLOYMENT_ID
    and LOCAL_OPENAI_API_VERSION
):
    llm = AzureChatOpenAI(
        azure_endpoint=LOCAL_OPENAI_ENDPOINT,
        api_key=LOCAL_OPENAI_API_KEY,
        api_version=LOCAL_OPENAI_API_VERSION,
        azure_deployment=LOCAL_OPENAI_DEPLOYMENT_ID,
        temperature=config.temperature,
    )
    logger.info("LLM (Local OpenAI) loaded")
else:
    logger.error("Required environment variables are missing")


# Set up logging
logger = logging.getLogger("document_loader")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def get_text_filepaths(document_filenames: list[str | Path]):
    """
    Load content from a list of documents and return a dictionary mapping filenames to their content.

    Args:
    document_filenames (list of str): List of file paths to the documents.

    Returns:
    dict: A dictionary where keys are filenames and values are the loaded document content.
    """
    # coherce paths of type str to Path elements:
    document_filenames: list[Path] = [Path(path) for path in document_filenames]
    document_contents = {}

    for context_filename in document_filenames:
        text = None
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
                loader = UnstructuredWordDocumentLoader(context_filename)
                text = loader.load()[0].page_content

            if text:
                document_contents[context_filename] = text
                logger.info(f"The file '{context_filename}' was read successfully.")

        except Exception as e:
            logger.error(f"Error reading '{context_filename}': {e}")

    return document_contents


prompt = PromptTemplate.from_template(config.base_prompt)

chain = prompt | llm
