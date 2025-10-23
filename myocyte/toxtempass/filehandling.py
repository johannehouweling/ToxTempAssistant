import base64
import csv
import json
import logging
import mimetypes
import shutil
import tempfile
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

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
from PIL import Image
from pypdf import PdfReader
from pypdf._page import PageObject

from toxtempass import config
from toxtempass.llm import ImageMessage

try:
    import openpyxl
except ImportError:  # pragma: no cover - optional dependency
    openpyxl = None

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

DEFAULT_IMAGE_MIME = "image/png"
MAX_TABLE_ROWS = 50


def _extract_images_from_pdf_page(
    page: PageObject, source_path: Path, page_number: int
) -> dict[str, dict[str, str]]:
    """Extract images from a single PDF page into the document dictionary format."""
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
        mime_type = mimetypes.guess_type(image_name)[0]
        if not mime_type and image_format:
            mime_type = f"image/{image_format.lower()}"

        encoded = base64.b64encode(image_bytes).decode("utf-8")
        key = (
            f"{str(source_path)}#page{page_number}_"
            f"{image_name if image_name else f'image{idx}'}"
        )
        images[key] = {
            "encodedbytes": encoded,
            "mime_type": mime_type or DEFAULT_IMAGE_MIME,
            "source_document": str(source_path),
            "origin": "embedded",
        }

    return images


def _extract_images_from_docx(path: Path) -> dict[str, dict[str, str]]:
    """Extract embedded images from a DOCX file."""
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
                mime_type = mimetypes.guess_type(filename)[0] or DEFAULT_IMAGE_MIME
                encoded = base64.b64encode(data).decode("utf-8")
                key = f"{str(path)}#{filename}"
                images[key] = {
                    "encodedbytes": encoded,
                    "mime_type": mime_type,
                    "source_document": str(path),
                    "origin": "embedded",
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
    dict: A dictionary where keys are filenames and values are the loaded document
    content or encoded bytes for images.

    """
    # coherce paths of type str to Path elements:
    document_filenames: list[Path] = [Path(path) for path in document_filenames]
    document_contents = {}

    for context_filename in document_filenames:
        text = None
        img_bytestring = None
        mime_type = None
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
                        images = (
                            _extract_images_from_pdf_page(
                                page, context_filename, page_number
                            )
                            if extract_images
                            else {}
                        )
                        if images:
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
                images = _extract_images_from_docx(context_filename) if extract_images else {}
                if images:
                    document_contents.update(images)

            elif suffix == ".json":
                text = _read_json_file(context_filename)

            elif suffix == ".csv":
                text = _read_csv_file(context_filename)

            elif suffix == ".xlsx":
                text = _read_xlsx_file(context_filename)

            elif suffix in config.image_accept_files:
                with Image.open(context_filename) as img:
                    target_format = IMAGE_SUFFIX_FORMATS.get(
                        suffix, (img.format or "PNG").upper()
                    )
                    if target_format == "JPEG" and img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    s = BytesIO()
                    img.save(s, format=target_format)
                    img_bytestring = base64.b64encode(s.getvalue()).decode("utf-8")
                mime_type = (
                    mimetypes.guess_type(context_filename.name)[0]
                    or f"image/{target_format.lower()}"
                )

            if text:
                document_contents[str(context_filename)] = {
                    "text": text,
                    "source_document": str(context_filename),
                    "origin": "document",
                }
                logger.info(f"The file '{context_filename}' was read successfully.")
            elif img_bytestring:
                document_contents[str(context_filename)] = {
                    "encodedbytes": img_bytestring,
                    "mime_type": mime_type or DEFAULT_IMAGE_MIME,
                    "source_document": str(context_filename),
                    "origin": "uploaded_image",
                }
                logger.info(f"The file '{context_filename}' was read successfully.")

        except Exception as e:
            logger.error(f"Error reading '{context_filename}': {e}")
        # Here let's remove the files after reading them.
        if unlink:
            context_filename.unlink()

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


def image_dict_to_messages(image_dict: dict[str, dict[str, str]]) -> list[ImageMessage]:
    """Convert an image dictionary to ImageMessage instances."""
    messages: list[ImageMessage] = []
    for path_str, meta in image_dict.items():
        encoded = meta.get("encodedbytes")
        if not encoded:
            continue
        filename = Path(path_str).name
        mime = meta.get("mime_type")
        if not mime:
            mime, _ = mimetypes.guess_type(filename)
        messages.append(
            ImageMessage(
                content=encoded,
                filename=filename,
                mime_type=mime or DEFAULT_IMAGE_MIME,
            )
        )
    return messages


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
