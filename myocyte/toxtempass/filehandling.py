import base64
import csv
import hashlib
import json
import logging
import mimetypes
import shutil
import tempfile
import warnings
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING
from zipfile import ZipFile

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import (
    InMemoryUploadedFile,
    TemporaryUploadedFile,
    UploadedFile,
)
from langchain_community.document_loaders import (
    BSHTMLLoader,
    TextLoader,
    UnstructuredWordDocumentLoader,
)
from langchain_core.messages import HumanMessage, SystemMessage
from PIL import Image
from pypdf import PdfReader
from pypdf._page import PageObject

from toxtempass import config
from toxtempass.llm import get_llm

if TYPE_CHECKING:
    from toxtempass.models import Assay, FileAsset, Person

try:
    import openpyxl
except ImportError:  # pragma: no cover - optional dependency
    openpyxl = None

# Suppress PyPDF warnings about image and mask size mismatches
# These are benign warnings that don't affect functionality
warnings.filterwarnings(
    "ignore",
    message=".*image and mask size not matching.*",
    category=UserWarning,
)

logger = logging.getLogger("llm")


IMAGE_SUFFIX_FORMATS = {
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".gif": "GIF",
    ".bmp": "BMP",
    ".tiff": "TIFF",
    ".webp": "WEBP",
}

# Target format for all image conversions - WebP is most efficient for base64/tokens
# This reduces API costs by minimizing the base64 payload size
TARGET_IMAGE_FORMAT = "WEBP"
TARGET_IMAGE_MIME = "image/webp"
TARGET_IMAGE_QUALITY = 85  # WebP quality (0-100), 85 is good balance of quality/size

DEFAULT_IMAGE_MIME = "image/png"
MAX_TABLE_ROWS = 50


def _truncate_context(text: str | None, limit: int = 1500) -> str | None:
    if not text:
        return None
    cleaned = text.strip()
    if not cleaned:
        return None
    if len(cleaned) > limit:
        return cleaned[:limit] + "…"
    return cleaned


def _describe_image(
    encoded_image: str,
    filename: str,
    mime_type: str | None,
    page_context: str | None = None,
) -> str:
    """Generate a textual description for an image using the configured LLM."""
    mime = mime_type or DEFAULT_IMAGE_MIME
    try:
        llm = get_llm()
        system_message = SystemMessage(content=config.image_description_prompt)
        human_content: list[dict[str, object]] = []
        context = _truncate_context(page_context)
        if context:
            human_content.append({"type": "text", "text": f"PAGE CONTEXT:\n{context}"})
        human_content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime};base64,{encoded_image}",
                    "detail": "high",
                },
            }
        )
        response = llm.invoke([system_message, HumanMessage(content=human_content)])
        description = (getattr(response, "content", "") or "").strip()
        if description:
            normalized = description.strip()
            upper = normalized.upper()
            if upper == "IGNORE_IMAGE":
                logger.info(
                    "Descriptor returned IGNORE_IMAGE for %s; skipping.", filename
                )
                return ""
            if upper.startswith("I'M UNABLE") or upper.startswith("IT SEEMS"):
                return ""
            return normalized
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("Image description failed for %s: %s", filename, exc)

    return ""


def _format_image_description(
    description: str,
    source_document: str,
    page_number: int | None = None,
) -> str:
    doc_name = Path(source_document).name
    if page_number is not None:
        prefix = f"Image summary from {doc_name} (page {page_number})"
    else:
        prefix = f"Image summary from {doc_name}"
    return f"{prefix}:\n{description}"


def summarize_image_entries(doc_dict: dict[str, dict[str, str]]) -> None:
    """Convert encoded image entries in-place to textual summaries."""
    for key in list(doc_dict.keys()):
        meta = doc_dict[key]
        if "encodedbytes" not in meta:
            continue

        description = _describe_image(
            meta.get("encodedbytes", ""),
            Path(key).name,
            meta.get("mime_type"),
            meta.get("page_context"),
        )
        if not description:
            logger.info("Removing image %s due to empty or ignored description.", key)
            doc_dict.pop(key)
            continue

        doc_dict[key] = {
            "text": _format_image_description(
                description,
                meta.get("source_document", key),
                meta.get("page_number"),
            ),
            "source_document": meta.get("source_document", key),
            "origin": "image_description",
        }


def _convert_image_to_webp(
    image_bytes: bytes, source_format: str | None = None
) -> tuple[bytes, str]:
    """Convert image bytes to WebP format for optimal token efficiency.

    WebP provides the best compression ratio, reducing base64 size and API token usage.

    Args:
        image_bytes: Raw image bytes
        source_format: Original format name (for logging)

    Returns:
        Tuple of (converted_bytes, mime_type)

    Raises:
        Exception: If conversion fails
    """
    img = Image.open(BytesIO(image_bytes))
    output = BytesIO()
    # Convert to RGB if necessary (WebP supports RGBA but not all modes)
    if img.mode == "RGBA":
        pass  # WebP supports RGBA
    elif img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.save(output, format=TARGET_IMAGE_FORMAT, quality=TARGET_IMAGE_QUALITY)
    logger.debug(
        "Converted %s image to %s", source_format or "unknown", TARGET_IMAGE_FORMAT
    )
    return output.getvalue(), TARGET_IMAGE_MIME


def _extract_images_from_pdf_page(
    page: PageObject, source_path: Path, page_number: int
) -> dict[str, dict[str, str]]:
    """Extract images from a single PDF page into the document dictionary format.

    All images are converted to WebP format for optimal token efficiency when
    sending to OpenAI's Vision API.
    """
    images: dict[str, dict[str, str]] = {}
    pdf_images = getattr(page, "images", []) or []

    for idx, image_obj in enumerate(pdf_images, start=1):
        image_bytes = getattr(image_obj, "data", None)
        if image_bytes is None and hasattr(image_obj, "get_data"):
            try:
                image_bytes = image_obj.get_data()
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug(
                    "Failed to read PDF image bytes (%s page %s idx %s): %s",
                    source_path,
                    page_number,
                    idx,
                    exc,
                )
                continue
        if not image_bytes:
            continue

        image_name = getattr(image_obj, "name", "") or f"image{idx}"
        image_format = (
            getattr(image_obj, "image_format", None)
            or Path(image_name).suffix.lstrip(".")
            or None
        )

        # Always convert to WebP for optimal token efficiency
        try:
            image_bytes, mime_type = _convert_image_to_webp(image_bytes, image_format)
        except Exception as exc:
            logger.warning(
                "Failed to convert %s image to WebP (%s page %s): %s. Skipping image.",
                image_format or "unknown",
                source_path,
                page_number,
                exc,
            )
            continue

        encoded = base64.b64encode(image_bytes).decode("utf-8")
        key = (
            f"{str(source_path)}#page{page_number}_"
            f"{image_name if image_name else f'image{idx}'}"
        )
        images[key] = {
            "encodedbytes": encoded,
            "mime_type": mime_type,
            "source_document": str(source_path),
            "origin": "embedded",
            "page_number": page_number,
        }

    return images


def _extract_images_from_docx(path: Path) -> dict[str, dict[str, str]]:
    """Extract embedded images from a DOCX file.

    All images are converted to WebP format for optimal token efficiency.
    """
    images: dict[str, dict[str, str]] = {}
    try:
        with ZipFile(path) as docx_zip:
            for info in docx_zip.infolist():
                if not info.filename.startswith("word/media/"):
                    continue
                filename = Path(info.filename).name
                data = docx_zip.read(info)
                if not data:
                    continue

                # Convert to WebP for optimal token efficiency
                original_format = Path(filename).suffix.lstrip(".")
                try:
                    data, mime_type = _convert_image_to_webp(data, original_format)
                except Exception as exc:
                    logger.warning(
                        "Failed to convert DOCX image %s to WebP: %s. Skipping.",
                        filename,
                        exc,
                    )
                    continue

                encoded = base64.b64encode(data).decode("utf-8")
                key = f"{str(path)}#{filename}"
                images[key] = {
                    "encodedbytes": encoded,
                    "mime_type": mime_type,
                    "source_document": str(path),
                    "origin": "embedded",
                    "page_number": None,
                }
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Failed to extract images from DOCX %s: %s", path, exc)
    return images


def _read_json_file(path: Path) -> str:
    """Read a JSON file and return a pretty-printed string representation."""
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse JSON %s: %s. Returning raw text.", path, exc)
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Unexpected error reading JSON %s: %s", path, exc)
        return path.read_text(encoding="utf-8", errors="replace")


def _read_csv_file(path: Path, max_rows: int = MAX_TABLE_ROWS) -> str:
    """Read a CSV file and return a truncated textual representation."""
    lines: list[str] = []
    truncated = False
    try:
        with path.open("r", encoding="utf-8", newline="", errors="replace") as f:
            reader = csv.reader(f)
            for idx, row in enumerate(reader):
                if idx >= max_rows:
                    truncated = True
                    break
                lines.append(", ".join(row))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to read CSV %s: %s", path, exc)
        return path.read_text(encoding="utf-8", errors="replace")

    if not lines:
        lines.append("(empty csv)")
    if truncated:
        lines.append(f"... (truncated after {max_rows} rows)")
    return "\n".join(lines)


def _read_xlsx_file(path: Path, max_rows: int = MAX_TABLE_ROWS) -> str:
    """Read an XLSX workbook and return a textual summary per sheet."""
    if openpyxl is None:
        logger.warning("openpyxl not installed; cannot process %s", path)
        return "Excel parsing unavailable (openpyxl not installed)."

    try:
        workbook = openpyxl.load_workbook(
            path, read_only=True, data_only=True, keep_links=False
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to open XLSX %s: %s", path, exc)
        return "Unable to read Excel file."

    sheet_texts: list[str] = []
    try:
        for sheet in workbook.worksheets:
            lines: list[str] = []
            truncated = False
            for idx, row in enumerate(sheet.iter_rows(values_only=True)):
                if idx >= max_rows:
                    truncated = True
                    break
                formatted = ", ".join("" if cell is None else str(cell) for cell in row)
                lines.append(formatted)
            if not lines:
                lines.append("(empty sheet)")
            if truncated:
                lines.append(f"... (truncated after {max_rows} rows)")
            sheet_texts.append(f"Sheet: {sheet.title}\n" + "\n".join(lines))
    finally:
        workbook.close()

    return "\n\n".join(sheet_texts) if sheet_texts else "(no sheets found)"


def stringyfy_text_dict(text_dict: dict[str, dict[str, str]]) -> str:
    """Convert text dictionary to a single string."""
    return "\n\n".join(
        f"--- {Path(fp).name} ---\n{meta['text']}"
        for fp, meta in text_dict.items()
        if "text" in meta
    )


def get_text_or_bytes_perfile_dict(
    document_filenames: list[str | Path], unlink: bool = True, extract_images: bool = True
) -> dict[str, dict[str, str]]:
    """Load content from a list of documents.

    Args:
    document_filenames (list of str): List of file paths to the documents.
    unlink (bool): if files shall be deleted afterwards
    extract_images (bool): whether to extract images from PDFs and DOCX files

    Returns:
    dict: A dictionary where keys are filenames (or synthetic identifiers) and values
    are dictionaries containing extracted text. When ``extract_images`` is True,
    images are summarized into text entries instead of returning raw bytes.

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
                    paragraphs: list[str] = []
                    for page_number, page in enumerate(reader.pages, start=1):
                        try:
                            page_text = page.extract_text() or ""
                        except Exception as exc:  # pragma: no cover - defensive
                            logger.debug(
                                "Failed to extract text from %s page %s: %s",
                                context_filename,
                                page_number,
                                exc,
                            )
                            page_text = ""
                        if page_text.strip():
                            paragraphs.append(page_text.strip())

                        if extract_images:
                            images = _extract_images_from_pdf_page(
                                page, context_filename, page_number
                            )
                            if images:
                                page_context = _truncate_context(page_text)
                                for key in images:
                                    images[key]["page_context"] = page_context
                                document_contents.update(images)

                    text = "\n".join(paragraphs)

            elif suffix in [".txt", ".md"]:
                loader = TextLoader(file_path=context_filename, autodetect_encoding=True)
                text = loader.load()[0].page_content

            elif suffix == ".html":
                loader = BSHTMLLoader(context_filename, open_encoding="utf-8")
                text = loader.load().page_content.replace("\n", "")

            elif suffix == ".docx":
                loader = UnstructuredWordDocumentLoader(str(context_filename))
                text = loader.load()[0].page_content
                if extract_images:
                    images = _extract_images_from_docx(context_filename)
                    if images:
                        doc_context = _truncate_context(text)
                        for key in images:
                            images[key]["page_context"] = doc_context
                        document_contents.update(images)

            elif suffix == ".json":
                text = _read_json_file(context_filename)

            elif suffix == ".csv":
                text = _read_csv_file(context_filename)

            elif suffix == ".xlsx":
                text = _read_xlsx_file(context_filename)

            elif suffix in config.image_accept_files:
                # Convert all uploaded images to WebP for optimal token efficiency
                with open(context_filename, "rb") as img_file:
                    image_bytes = img_file.read()
                try:
                    image_bytes, mime_type = _convert_image_to_webp(image_bytes, suffix)
                except Exception as exc:
                    logger.warning(
                        "Failed to convert uploaded image %s to WebP: %s. Skipping.",
                        context_filename,
                        exc,
                    )
                    continue
                encoded = base64.b64encode(image_bytes).decode("utf-8")
                document_contents[str(context_filename)] = {
                    "encodedbytes": encoded,
                    "mime_type": mime_type,
                    "source_document": str(context_filename),
                    "origin": "uploaded_image",
                    "page_number": None,
                    "page_context": None,
                }
                logger.info(
                    f"The image '{context_filename}' was read and converted to WebP."
                )
                continue

            if text:
                document_contents[str(context_filename)] = {
                    "text": text,
                    "source_document": str(context_filename),
                    "origin": "document",
                }
                logger.info(f"The file '{context_filename}' was read successfully.")

        except Exception as e:
            logger.error(f"Error reading '{context_filename}': {e}")
        finally:
            if unlink:
                try:
                    context_filename.unlink()
                except FileNotFoundError:
                    pass

    if extract_images:
        summarize_image_entries(document_contents)

    return document_contents


def convert_to_temporary(file: InMemoryUploadedFile) -> tuple[str, Path]:
    """Convert an InMemoryUploadedFile to a TemporaryUploadedFile.

    by creating a temporary file on disk with the correct file extension.

    Args:
    file (InMemoryUploadedFile): The file in memory to convert.

    Returns:
    str: Path to the new temporary file

    """
    # Create a temporary file with the same extension
    tmp_dir = Path(tempfile.mktemp(dir=Path(tempfile.gettempdir()) / "toxtempass"))  # noqa: S306
    tmp_dir.mkdir(parents=True, exist_ok=True)
    temp_file = tmp_dir / file.name

    # Write the contents of the InMemoryUploadedFile to the temporary file
    with temp_file.open("wb") as f:
        for chunk in file.chunks():
            f.write(chunk)
            f.flush()

    return str(temp_file)


def get_text_or_imagebytes_from_django_uploaded_file(
    files: UploadedFile,
    extract_images: bool = False,
) -> dict[str, dict[str, str]]:
    """Get text dictionary from uploaded files.

    {Path(filename.pdf): {'text': 'lorem ipsum'} or {"encodedbytes": "dskhasdhak"}
    """
    temp_files = []
    for file in files:
        if isinstance(file, TemporaryUploadedFile):
            src_path = Path(file.temporary_file_path())
            dest_path = src_path.parent / file.name
            # Copy the temporary file to destination retaining the user-provided filename
            shutil.copy(src_path, dest_path)
            temp_files.append(str(dest_path))
        elif isinstance(file, InMemoryUploadedFile):
            temp_path_str = convert_to_temporary(file)
            temp_files.append(temp_path_str)

    # md5_dict = calculate_md5_multiplefiles(temp_files)
    text_dict = get_text_or_bytes_perfile_dict(temp_files, extract_images=extract_images)
    return text_dict


def split_doc_dict_by_type(
    dict: dict[str, dict[str, str]], decode: bool = True
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    """Split the dictionary into two dictionaries: one for text and one for bytes.

    Args:
    dict (dict): The input dictionary to split.
    decode (bool): if to base64decode the load

    Returns:
    tuple: A tuple containing two dictionaries: one for text and one for bytes.

    """
    text_dict = {}
    bytes_dict = {}
    for pathstr, sub_dict in dict.items():
        if "text" in sub_dict:
            text_dict[pathstr] = sub_dict
        elif "encodedbytes" in sub_dict:
            if decode:
                try:
                    bytes_dict[pathstr] = {
                        "bytes": base64.b64decode(sub_dict["encodedbytes"]),
                    }
                    if "mime_type" in sub_dict:
                        bytes_dict[pathstr]["mime_type"] = sub_dict["mime_type"]
                except Exception as e:
                    logging.error(f"Error decoding base64: {e}")
            else:
                bytes_dict[pathstr] = sub_dict
    return text_dict, bytes_dict


def collect_source_documents(doc_dict: dict[str, dict[str, str]]) -> list[str]:
    """Return unique source document names for a document dictionary."""
    seen: set[str] = set()
    ordered: list[str] = []
    for key, meta in doc_dict.items():
        origin = meta.get("origin")
        source = meta.get("source_document")
        if origin == "embedded" and source:
            name = Path(source).name
        else:
            name = Path(source or key).name
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def _calculate_sha256(file_bytes: bytes) -> str:
    """Calculate SHA256 hash for file bytes."""
    return hashlib.sha256(file_bytes).hexdigest()


def store_files_to_storage(
    files: list[UploadedFile],
    user: "Person",
    assay: "Assay",
    consent: bool,
) -> list["FileAsset"]:
    """Store uploaded files to S3/MinIO if user consented.

    Args:
        files: List of uploaded files from the form
        user: Person object (uploader)
        assay: Assay object associated with the files
        consent: Whether user consented to file storage

    Returns:
        List of created FileAsset objects (empty if no consent)

    Raises:
        Exception: If file storage fails (propagates after logging)
    """
    from toxtempass.models import FileAsset
    import uuid

    if not consent:
        logger.debug("User did not consent to file storage; skipping storage.")
        return []

    if not files:
        logger.debug("No files provided for storage.")
        return []

    created_assets: list[FileAsset] = []

    for file in files:
        try:
            # Read file content
            file_content = b""
            for chunk in file.chunks():
                file_content += chunk

            # Calculate metadata
            file_size = len(file_content)
            sha256_hash = _calculate_sha256(file_content)
            content_type = (
                getattr(file, "content_type", "")
                or mimetypes.guess_type(file.name)[0]
                or ""
            )

            # Generate S3 object key using user/assay structure
            # Format: consent_user_documents/{user.email}/{assay.id}/{uuid}/{filename}
            object_key = (
                f"consent_user_documents/{user.email}/assay/{assay.id}/"
                f"{uuid.uuid4()}/"
                f"{Path(file.name).name}"
            )

            # Upload to storage
            default_storage.save(object_key, file)
            logger.info(
                "Successfully uploaded file %s to storage: %s",
                file.name,
                object_key,
            )

            # Create FileAsset record
            asset = FileAsset.objects.create(
                object_key=object_key,
                original_filename=file.name,
                content_type=content_type,
                size_bytes=file_size,
                sha256=sha256_hash,
                status=FileAsset.Status.AVAILABLE,
                uploaded_by=user,
            )
            created_assets.append(asset)
            logger.debug("Created FileAsset record: id=%s, key=%s", asset.id, object_key)

        except Exception as exc:
            logger.exception(
                "Failed to store file %s for user %s on assay %s: %s",
                file.name,
                user.email,
                assay.id,
                exc,
            )
            raise

    logger.info(
        "Stored %d files for user %s on assay %s", len(created_assets), user.email, assay.id
    )
    return created_assets
