from __future__ import annotations

import logging

from django.core.files.storage import default_storage
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from myocyte.toxtempass.demo import seed_demo_assay_for_user

from .models import FileAsset, Person

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=FileAsset)
def delete_object_from_storage(sender:FileAsset, instance: FileAsset, **kwargs) -> None:
    """Remove the object from storage (S3/MinIO) after the DB row is deleted."""
    key = (instance.object_key or "").strip()
    if not key:
        return

    try:
        if default_storage.exists(key):
            default_storage.delete(key)
    except Exception:
        # Decide your policy: log and swallow, or re-raise
        logger.exception("Failed to delete storage object: %s", key)

@receiver(post_save, sender=Person, dispatch_uid="person_seed_demo_assay")
def seed_demo(sender:Person, instance: Person, created: bool, **kwargs) -> None:
    """Seed a demo assay for newly created users."""
    if not created:
            return
    seed_demo_assay_for_user(instance)