import base64
import logging
from pathlib import Path
from django.core.files.uploadedfile import (
    TemporaryUploadedFile,
    UploadedFile,
    InMemoryUploadedFile,
)
import tempfile

logger = logging.getLogger("llm")


# from toxtempass.utilis import calculate_md5_multiplefiles, combine_dicts
from toxtempass.llm import get_text_or_bytes_perfile_dict


def convert_to_temporary(file: InMemoryUploadedFile) -> tuple[str, Path]:
    """
    Convert an InMemoryUploadedFile to a TemporaryUploadedFile by creating a temporary file on disk
    with the correct file extension.

    Args:
    file (InMemoryUploadedFile): The file in memory to convert.

    Returns:
    str: Path to the new temporary file
    """
    # Create a temporary file with the same extension
    Path("/tmp/toxtempass").mkdir(parents=True, exist_ok=True)
    temp_file = Path(tempfile.mkdtemp(dir="/tmp/toxtempass")) / file.name

    # Write the contents of the InMemoryUploadedFile to the temporary file
    with temp_file.open("wb") as f:
        for chunk in file.chunks():
            f.write(chunk)
            f.flush()

    return str(temp_file)


def get_text_or_imagebytes_from_django_uploaded_file(
    files: UploadedFile,
) -> dict[str,dict[str, str]]:
    """Get text dictionary from uploaded files.
    {Path(filename.pdf): {'text': 'lorem ipsum'} or {"encodedbytes": "dskhasdhak"}
    """
    temp_files = [
        # rename the temporary-file to keep the user provided filename even for the tempfile
        str(Path(file.temporary_file_path()).rename(file.name))
        for file in files
        if isinstance(file, TemporaryUploadedFile)
    ]
    tempmem_files = [
        convert_to_temporary(file)
        for file in files
        if isinstance(file, InMemoryUploadedFile)
    ]
    files = temp_files + tempmem_files
    # md5_dict = calculate_md5_multiplefiles(files)
    text_dict = get_text_or_bytes_perfile_dict(files)
    return text_dict


def split_doc_dict_by_type(dict:dict[str,dict[str,str]],decode=True)-> tuple[dict[str,dict[str,str]], dict[str,dict[str,str]]]:
    """
    Split the dictionary into two dictionaries: one for text and one for bytes.

    Args:
    dict (dict): The input dictionary to split.

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
                    bytes_dict[pathstr] = {"bytes": base64.b64decode(sub_dict["encodedbytes"])}
                except Exception as e:
                    logging.error(f"Error decoding base64: {e}")
            else: 
                bytes_dict[pathstr]= sub_dict
    return text_dict, bytes_dict