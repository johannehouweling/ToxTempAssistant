"""File operations module for S3/MinIO storage of user-uploaded files.

This module provides utilities for:
- Uploading files to S3 storage with FileAsset record creation
- Linking FileAssets to Answer objects via AnswerFile junction table
- Detecting and cleaning up orphaned FileAssets
- Downloading all files associated with an assay as a ZIP
"""

import hashlib
import logging
from io import BytesIO
from pathlib import Path
from typing import IO
from uuid import UUID
from zipfile import ZipFile

from django.core.files.base import File
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from django.db.models import QuerySet
from django.utils import timezone

logger = logging.getLogger("fileops")


def compute_sha256(file_obj: IO[bytes]) -> str:
    """Compute SHA256 hash of a file object.
    
    Args:
        file_obj: File-like object to hash (must support seek/read)
        
    Returns:
        Hexadecimal digest string of SHA256 hash
    """
    sha256_hash = hashlib.sha256()
    
    # Save current position and rewind
    if hasattr(file_obj, 'seek'):
        original_position = file_obj.tell()
        file_obj.seek(0)
    
    # Read file in chunks for memory efficiency
    for chunk in iter(lambda: file_obj.read(8192), b''):
        sha256_hash.update(chunk)
    
    # Restore original position
    if hasattr(file_obj, 'seek'):
        file_obj.seek(original_position)
    
    return sha256_hash.hexdigest()


def upload_file_to_s3(uploaded_file: UploadedFile, user: "Person") -> "FileAsset":
    """Upload a Django UploadedFile to S3 storage and create FileAsset record.
    
    Args:
        uploaded_file: Django UploadedFile from request.FILES
        user: Person instance who uploaded the file
        
    Returns:
        FileAsset instance with S3 metadata
        
    Raises:
        Exception: If S3 upload fails
    """
    from toxtempass.models import FileAsset
    
    # Create FileAsset record first to get UUID
    file_asset = FileAsset(
        original_filename=uploaded_file.name,
        content_type=uploaded_file.content_type or '',
        size_bytes=uploaded_file.size,
        uploaded_by=user,
    )
    
    # Compute SHA256 hash
    try:
        file_asset.sha256 = compute_sha256(uploaded_file.file)
    except Exception as exc:
        logger.warning("Failed to compute SHA256 for %s: %s", uploaded_file.name, exc)
        file_asset.sha256 = ''
    
    # Generate S3 object key using UUID
    file_extension = Path(uploaded_file.name).suffix
    object_key = f"uploads/{file_asset.id}{file_extension}"
    
    # Upload to S3 using Django's default storage
    try:
        # Ensure we're at the beginning of the file
        if hasattr(uploaded_file, 'seek'):
            uploaded_file.seek(0)
        
        # Save to storage
        stored_path = default_storage.save(object_key, uploaded_file)
        
        # Update FileAsset with S3 metadata
        file_asset.object_key = stored_path
        file_asset.bucket = getattr(default_storage, 'bucket_name', '')
        file_asset.status = FileAsset.Status.AVAILABLE
        file_asset.save()
        
        logger.info(
            "Uploaded file %s to S3 as %s (FileAsset %s)",
            uploaded_file.name,
            stored_path,
            file_asset.id,
        )
        
        return file_asset
        
    except Exception as exc:
        logger.exception("Failed to upload file %s to S3", uploaded_file.name)
        # Clean up the FileAsset record if upload failed
        if file_asset.pk:
            file_asset.delete()
        raise


def link_files_to_answer(answer: "Answer", file_asset_ids: list[UUID]) -> list["AnswerFile"]:
    """Link FileAssets to an Answer via AnswerFile junction table.
    
    Args:
        answer: Answer instance to link files to
        file_asset_ids: List of FileAsset UUIDs to link
        
    Returns:
        List of AnswerFile instances (created or existing)
    """
    from toxtempass.models import AnswerFile, FileAsset
    
    answer_files = []
    
    for file_asset_id in file_asset_ids:
        try:
            file_asset = FileAsset.objects.get(pk=file_asset_id)
            answer_file, created = AnswerFile.objects.get_or_create(
                answer=answer,
                file=file_asset,
            )
            answer_files.append(answer_file)
            
            if created:
                logger.info(
                    "Linked FileAsset %s (%s) to Answer %s",
                    file_asset.id,
                    file_asset.original_filename,
                    answer.id,
                )
            else:
                logger.debug(
                    "FileAsset %s already linked to Answer %s",
                    file_asset.id,
                    answer.id,
                )
                
        except FileAsset.DoesNotExist:
            logger.warning(
                "FileAsset %s no longer exists, skipping link to Answer %s",
                file_asset_id,
                answer.id,
            )
            continue
        except Exception as exc:
            logger.exception(
                "Failed to link FileAsset %s to Answer %s: %s",
                file_asset_id,
                answer.id,
                exc,
            )
            continue
    
    return answer_files


def get_orphaned_file_assets(days: int = 7) -> QuerySet["FileAsset"]:
    """Find FileAssets created before N days ago with no AnswerFile links.
    
    Args:
        days: Number of days threshold (default 7)
        
    Returns:
        QuerySet of orphaned FileAsset instances
    """
    from toxtempass.models import FileAsset
    
    cutoff_date = timezone.now() - timezone.timedelta(days=days)
    
    # Find FileAssets with no related AnswerFile records
    orphaned = FileAsset.objects.filter(
        created_at__lt=cutoff_date,
        status=FileAsset.Status.AVAILABLE,
    ).exclude(
        answerfile__isnull=False  # Exclude those with any AnswerFile links
    )
    
    return orphaned


def delete_orphaned_file_assets(file_assets: QuerySet["FileAsset"]) -> tuple[int, dict]:
    """Delete FileAsset records and their corresponding S3 objects.
    
    Args:
        file_assets: QuerySet of FileAsset instances to delete
        
    Returns:
        Tuple of (count of deleted records, dict of errors if any)
    """
    deleted_count = 0
    errors = {}
    
    for file_asset in file_assets:
        try:
            # Delete S3 object first
            if file_asset.object_key:
                try:
                    default_storage.delete(file_asset.object_key)
                    logger.info(
                        "Deleted S3 object %s for FileAsset %s",
                        file_asset.object_key,
                        file_asset.id,
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to delete S3 object %s: %s",
                        file_asset.object_key,
                        exc,
                    )
                    errors[str(file_asset.id)] = f"S3 deletion failed: {exc}"
            
            # Delete FileAsset record
            file_asset_id = file_asset.id
            file_asset.delete()
            deleted_count += 1
            logger.info("Deleted orphaned FileAsset %s", file_asset_id)
            
        except Exception as exc:
            logger.exception("Failed to delete FileAsset %s: %s", file_asset.id, exc)
            errors[str(file_asset.id)] = str(exc)
    
    return deleted_count, errors


def download_assay_files(assay: "Assay") -> BytesIO:
    """Generate a ZIP file containing all files linked to an assay's answers.
    
    Args:
        assay: Assay instance to collect files from
        
    Returns:
        BytesIO object containing ZIP file data
        
    Raises:
        Exception: If ZIP creation fails
    """
    from toxtempass.models import FileAsset
    
    zip_buffer = BytesIO()
    
    # Collect all unique FileAssets linked to this assay's answers
    file_assets = FileAsset.objects.filter(
        answerfile__answer__assay=assay,
        status=FileAsset.Status.AVAILABLE,
    ).distinct()
    
    if not file_assets.exists():
        logger.warning("No files found for assay %s", assay.id)
        # Return empty ZIP
        with ZipFile(zip_buffer, 'w') as zip_file:
            pass
        zip_buffer.seek(0)
        return zip_buffer
    
    # Create ZIP file
    try:
        with ZipFile(zip_buffer, 'w') as zip_file:
            for file_asset in file_assets:
                try:
                    # Download file from S3
                    if not file_asset.object_key:
                        logger.warning(
                            "FileAsset %s has no object_key, skipping",
                            file_asset.id,
                        )
                        continue
                    
                    # Open file from storage
                    with default_storage.open(file_asset.object_key, 'rb') as s3_file:
                        file_data = s3_file.read()
                    
                    # Add to ZIP with original filename
                    # Avoid name collisions by prepending FileAsset ID if needed
                    zip_filename = file_asset.original_filename
                    
                    # Check if filename already exists in ZIP
                    if zip_filename in zip_file.namelist():
                        # Prepend UUID to make unique
                        name = Path(zip_filename)
                        zip_filename = f"{file_asset.id}_{name.stem}{name.suffix}"
                    
                    zip_file.writestr(zip_filename, file_data)
                    logger.debug("Added %s to ZIP", zip_filename)
                    
                except Exception as exc:
                    logger.warning(
                        "Failed to add FileAsset %s to ZIP: %s",
                        file_asset.id,
                        exc,
                    )
                    continue
        
        logger.info(
            "Created ZIP archive with %d files for assay %s",
            len(file_assets),
            assay.id,
        )
        
        zip_buffer.seek(0)
        return zip_buffer
        
    except Exception as exc:
        logger.exception("Failed to create ZIP for assay %s: %s", assay.id, exc)
        raise
