from pathlib import Path
from django.core.files.uploadedfile import (
    TemporaryUploadedFile,
    UploadedFile,
    InMemoryUploadedFile,
)
import tempfile

# from toxtempass.utilis import calculate_md5_multiplefiles, combine_dicts
from toxtempass.llm import get_text_or_bytes_filepaths


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
) -> dict[str, str]:
    """Get text dictionary from uploaded files.
    {Path(filename.pdf): {'text': 'lorem ipsum'} or {"bytes": b"dskhasdhak"}
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
    text_dict = get_text_or_bytes_filepaths(files)
    return text_dict
