import logging

from django.core.management.base import BaseCommand, CommandParser

from toxtempass.utilities import cleanup_orphaned_files

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Management command for cleaning up orphaned FileAsset records."""

    help = (
        "Clean up orphaned FileAsset records in phases. "
        "Phase 1: Soft-delete (status=AVAILABLE without AnswerFile). "
        "Phase 2: Hard-delete (status=DELETED for 7+ days without AnswerFile)."
    )

    def add_arguments(self, parser: CommandParser)->None:
        """Add command-line arguments."""
        parser.add_argument(
            "--phase",
            type=int,
            default=1,
            choices=[1, 2],
            help="Which cleanup phase to run (default: 1). Use 1 for soft-delete, 2 for hard-delete.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without making them.",
        )

    def handle(self, *args:Any, **options:Any)-> None:
        """Execute the cleanup command."""
        phase = options.get("phase", 1)
        dry_run = options.get("dry_run", False)

        mode = "[DRY RUN]" if dry_run else "[EXECUTE]"
        self.stdout.write(
            self.style.HTTP_INFO(
                f"{mode} Running orphaned file cleanup Phase {phase}..."
            )
        )

        stats = cleanup_orphaned_files(phase=phase, dry_run=dry_run)

        # Display results
        self.stdout.write(
            self.style.SUCCESS("Cleanup Statistics:")
        )
        self.stdout.write(f"  Soft-deleted: {stats['soft_deleted']}")
        self.stdout.write(f"  Hard-deleted: {stats['hard_deleted']}")
        if stats["errors"]:
            self.stdout.write(
                self.style.ERROR(f"  Errors: {stats['errors']}")
            )
        else:
            self.stdout.write(self.style.SUCCESS("  Errors: 0"))

        if dry_run:
            self.stdout.write(
                self.style.HTTP_INFO(
                    "\nDry run completed. No changes were made."
                )
            )
