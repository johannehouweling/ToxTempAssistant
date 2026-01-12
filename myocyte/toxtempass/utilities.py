import hashlib
import logging
from datetime import timedelta
from pathlib import Path

from django.utils import timezone

from toxtempass.models import FileAsset, Person

logger = logging.getLogger(__name__)

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


# --- Beta utilities (token generation, verification, preference helpers) ---
from typing import Optional


def generate_beta_token(person_id: int) -> str:
    """Generate a time-signed token for admitting a person to the beta program.

    The returned token is created with Django's signing machinery and should be
    safe to embed in approval links. It encodes a small payload containing the
    person's id. Verification should be done with verify_beta_token.
    """
    # Import locally to avoid making this module import Django at top-level
    from django.core.signing import dumps

    payload = {"person_id": person_id}
    return dumps(payload, salt="toxtempass-beta")


def verify_beta_token(token: str, max_age_days: int = 30) -> Optional[dict]:
    """Verify a beta token and return the payload on success, otherwise None.

    max_age_days controls how long the token is valid (default 30 days).
    """
    from django.core.signing import loads, BadSignature, SignatureExpired

    max_age_seconds = int(max_age_days) * 24 * 60 * 60
    try:
        data = loads(token, salt="toxtempass-beta", max_age=max_age_seconds)
        return data
    except SignatureExpired:
        return None
    except BadSignature:
        return None


def set_beta_requested(person, comment: Optional[str] = None) -> None:
    """Mark a Person as having requested access to the beta program.

    Safely handles person.preferences == None. Sets:
      - beta_signup = True
      - beta_requested_at = ISO timestamp
      - beta_admitted = False (if not present)
      - beta_comment = comment (if provided)

    Saves the Person model updating only the preferences field.
    """
    from django.utils import timezone

    prefs = person.preferences or {}
    prefs["beta_signup"] = True
    prefs["beta_requested_at"] = timezone.now().isoformat()
    prefs.setdefault("beta_admitted", False)
    if comment is not None:
        prefs["beta_comment"] = comment
    person.preferences = prefs
    # update_fields to avoid touching other fields / updated timestamps unless desired
    person.save(update_fields=["preferences"])


def set_beta_admitted(person:Person, admitted: bool, comment: Optional[str] = None) -> None:
    """Admit or revoke a Person's beta status.

    Sets:
      - beta_admitted = bool(admitted)
      - beta_admitted_at = ISO timestamp when admitted, or None when revoked
      - beta_comment = comment (if provided)

    Saves the Person model updating only the preferences field.
    """
    from django.utils import timezone

    prefs = person.preferences or {}
    prefs["beta_admitted"] = bool(admitted)
    prefs["beta_admitted_at"] = timezone.now().isoformat() if admitted else None
    if comment is not None:
        prefs["beta_comment"] = comment
    person.preferences = prefs
    person.save(update_fields=["preferences"])


# --- File storage cleanup utilities ---
def cleanup_orphaned_files(
    phase: int = 1,
    dry_run: bool = False,
) -> dict[str, int]:
    """Clean up orphaned FileAsset records in phases.

    Phase 1: Find FileAssets with status=AVAILABLE and no AnswerFile records,
             mark them as DELETED.

    Phase 2: Find FileAssets with status=DELETED created >7 days ago and still
             no AnswerFile records, perform hard delete (removes DB record and
             S3 object via signal).

    Args:
        phase: Which phase(s) to run (1, 2, or 0 for both)
        dry_run: If True, log what would be done without making changes

    Returns:
        Dictionary with stats: {'soft_deleted': int, 'hard_deleted': int, 'errors': int}
    """
    stats = {"soft_deleted": 0, "hard_deleted": 0, "errors": 0}

    try:
        # Phase 1: Soft delete orphaned AVAILABLE files
        if phase in (0, 1):
            logger.info("Starting Phase 1: Soft-delete orphaned AVAILABLE files")

            # Find all AVAILABLE FileAssets with no AnswerFile records
            orphaned = FileAsset.objects.filter(
                status=FileAsset.Status.AVAILABLE
            ).exclude(answerfile__isnull=False)

            count = orphaned.count()
            logger.info(f"Found {count} orphaned AVAILABLE FileAssets")

            if dry_run:
                logger.info(f"[DRY RUN] Would soft-delete {count} files")
                stats["soft_deleted"] = count
            else:
                try:
                    orphaned.update(status=FileAsset.Status.DELETED)
                    stats["soft_deleted"] = count
                    logger.info(f"Soft-deleted {count} orphaned files")
                except Exception as e:
                    logger.exception(f"Error during Phase 1 soft-delete: {e}")
                    stats["errors"] += 1

        # Phase 2: Hard delete DELETED files older than threshold
        if phase in (0, 2):
            logger.info("Starting Phase 2: Hard-delete old DELETED files")

            # Calculate threshold (7 days ago)
            threshold = timezone.now() - timedelta(days=7)

            # Find DELETED FileAssets created before threshold with no AnswerFile
            old_orphaned = FileAsset.objects.filter(
                status=FileAsset.Status.DELETED,
                created_at__lt=threshold,
            ).exclude(answerfile__isnull=False)

            count = old_orphaned.count()
            logger.info(f"Found {count} old orphaned DELETED FileAssets")

            if dry_run:
                logger.info(f"[DRY RUN] Would hard-delete {count} files")
                stats["hard_deleted"] = count
            else:
                try:
                    # Iterate and delete (so signal fires for each)
                    for asset in old_orphaned:
                        asset_id = asset.id
                        asset.delete()
                        logger.debug(f"Hard-deleted FileAsset: {asset_id}")
                    stats["hard_deleted"] = count
                    logger.info(f"Hard-deleted {count} old orphaned files")
                except Exception as e:
                    logger.exception(f"Error during Phase 2 hard-delete: {e}")
                    stats["errors"] += 1

    except Exception as e:
        logger.exception(f"Fatal error in cleanup_orphaned_files: {e}")
        stats["errors"] += 1

    return stats
