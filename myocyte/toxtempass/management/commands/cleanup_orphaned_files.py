"""Django management command to clean up orphaned FileAssets.

This command finds and deletes FileAsset records that:
- Were created more than N days ago (default 7)
- Have no AnswerFile links (i.e., never used in any Answer)
- Are in 'available' status

Both the database records and corresponding S3 objects are deleted.
"""

import logging

from django.core.management.base import BaseCommand, CommandParser

from toxtempass.models import FileAsset

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Clean up orphaned FileAsset records and their S3 objects"

    def add_arguments(self, parser: CommandParser) -> None:
        """Add command-line arguments."""
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Delete FileAssets older than this many days (default: 7)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )

    def handle(self, *args, **options) -> None:
        """Execute the cleanup command."""
        days = options["days"]
        dry_run = options["dry_run"]

        self.stdout.write(
            self.style.SUCCESS(
                f"{'[DRY RUN] ' if dry_run else ''}Finding FileAssets older than {days} days with no Answer links..."
            )
        )

        # Get orphaned FileAssets using the custom manager
        orphaned = FileAsset.objects.get_orphaned(days=days)
        count = orphaned.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("No orphaned FileAssets found."))
            return

        self.stdout.write(
            self.style.WARNING(f"Found {count} orphaned FileAsset(s) to delete:")
        )

        # Display what will be deleted
        for file_asset in orphaned:
            age_days = (file_asset.created_at.date() - file_asset.created_at.date()).days
            self.stdout.write(
                f"  - {file_asset.id}: {file_asset.original_filename} "
                f"({file_asset.size_bytes or 0} bytes, created {file_asset.created_at})"
            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\n[DRY RUN] Would delete {count} FileAsset(s) and their S3 objects."
                )
            )
            return

        # Confirm deletion
        self.stdout.write("\n")
        confirm = input(
            f"Are you sure you want to delete {count} FileAsset(s) "
            "and their S3 objects? [y/N]: "
        )

        if confirm.lower() != "y":
            self.stdout.write(self.style.ERROR("Operation cancelled."))
            return

        # Perform deletion
        deleted_count, errors = FileAsset.objects.cleanup_orphaned(days=days)

        if errors:
            self.stdout.write(
                self.style.ERROR(
                    f"\nDeleted {deleted_count} FileAsset(s) with {len(errors)} error(s):"
                )
            )
            for file_asset_id, error_msg in errors.items():
                self.stdout.write(f"  - FileAsset {file_asset_id}: {error_msg}")
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSuccessfully deleted {deleted_count} orphaned FileAsset(s) "
                    "and their S3 objects."
                )
            )

        # Log the operation
        logger.info(
            "Cleanup command completed: deleted %d FileAssets, %d errors",
            deleted_count,
            len(errors),
        )
