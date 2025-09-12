import hashlib
from pathlib import Path


def calculate_md5(pdf_file_path:Path)-> str:
    """Calculate MD5 hash for a given PDF file."""
    md5_hash = hashlib.md5(usedforsecurity=False)

    # Open the PDF file in binary mode and read it in chunks
    with open(pdf_file_path, "rb") as pdf_file:
        # Read in chunks of 4096 bytes
        for chunk in iter(lambda: pdf_file.read(4096), b""):
            md5_hash.update(chunk)

    # Return the hexadecimal digest of the hash
    return md5_hash.hexdigest()


def calculate_md5_multiplefiles(files: list) -> dict:
    """Calculate MD5 has for multiple pdf files."""
    md5dict = {}
    for file in files:
        md5dict[Path(file)] = calculate_md5(file)
    return md5dict


def combine_dicts(dict1: dict, dict2: dict) -> dict:
    """Combine two dicts."""
    combined = {}

    # Get all keys from both dictionaries
    keys = set(dict1.keys()).union(dict2.keys())

    for key in keys:
        if key in dict1 and key in dict2:
            # If both values are dictionaries, recursively combine them
            if isinstance(dict1[key], dict) and isinstance(dict2[key], dict):
                combined[key] = combine_dicts(dict1[key], dict2[key])
            else:
                # If they are not dictionaries, you can decide how to handle conflicts
                combined[key] = dict1[key]  # or dict2[key] or a tuple of both, etc.
        elif key in dict1:
            # If the key is only in the first dictionary
            combined[key] = dict1[key]
        else:
            # If the key is only in the second dictionary
            combined[key] = dict2[key]

    return combined
