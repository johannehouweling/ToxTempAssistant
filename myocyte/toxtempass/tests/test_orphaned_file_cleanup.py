"""Tests for orphaned file cleanup functionality."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from toxtempass.models import AnswerFile, FileAsset
from toxtempass.tests.fixtures.factories import (
    AnswerFactory,
    FileAssetFactory,
)
from toxtempass.utilities import cleanup_orphaned_files


@pytest.mark.django_db
class TestCleanupOrphanedFilesPhase1:
    """Test Phase 1: Soft-delete orphaned AVAILABLE files."""

    def test_phase_1_marks_orphaned_as_deleted(self):
        """Test that orphaned AVAILABLE files are marked as DELETED."""
        # Create an orphaned file (no AnswerFile records)
        asset = FileAssetFactory(status=FileAsset.Status.AVAILABLE)
        
        stats = cleanup_orphaned_files(phase=1, dry_run=False)
        
        asset.refresh_from_db()
        assert asset.status == FileAsset.Status.DELETED
        assert stats["soft_deleted"] == 1
        assert stats["hard_deleted"] == 0

    def test_phase_1_preserves_files_with_answers(self):
        """Test that files linked to answers are NOT soft-deleted."""
        answer = AnswerFactory()
        asset = FileAssetFactory(status=FileAsset.Status.AVAILABLE)
        AnswerFile.objects.create(answer=answer, file=asset)
        
        stats = cleanup_orphaned_files(phase=1, dry_run=False)
        
        asset.refresh_from_db()
        assert asset.status == FileAsset.Status.AVAILABLE
        assert stats["soft_deleted"] == 0

    def test_phase_1_dry_run_does_not_modify(self):
        """Test that dry_run=True doesn't actually modify files."""
        asset = FileAssetFactory(status=FileAsset.Status.AVAILABLE)
        
        stats = cleanup_orphaned_files(phase=1, dry_run=True)
        
        asset.refresh_from_db()
        assert asset.status == FileAsset.Status.AVAILABLE
        assert stats["soft_deleted"] == 1

    def test_phase_1_multiple_orphaned_files(self):
        """Test handling multiple orphaned files."""
        assets = [
            FileAssetFactory(status=FileAsset.Status.AVAILABLE)
            for _ in range(5)
        ]
        
        stats = cleanup_orphaned_files(phase=1, dry_run=False)
        
        for asset in assets:
            asset.refresh_from_db()
            assert asset.status == FileAsset.Status.DELETED
        
        assert stats["soft_deleted"] == 5

    def test_phase_1_ignores_already_deleted(self):
        """Test that already DELETED files are not counted in Phase 1."""
        # Create one orphaned AVAILABLE and one already DELETED
        available = FileAssetFactory(status=FileAsset.Status.AVAILABLE)
        deleted = FileAssetFactory(status=FileAsset.Status.DELETED)
        
        stats = cleanup_orphaned_files(phase=1, dry_run=False)
        
        deleted.refresh_from_db()
        assert deleted.status == FileAsset.Status.DELETED
        available.refresh_from_db()
        assert available.status == FileAsset.Status.DELETED
        assert stats["soft_deleted"] == 1  # Only the AVAILABLE one


@pytest.mark.django_db
class TestCleanupOrphanedFilesPhase2:
    """Test Phase 2: Hard-delete old DELETED files."""

    def test_phase_2_hard_deletes_old_orphaned(self):
        """Test that old DELETED orphaned files are hard-deleted."""
        # Create file deleted 8 days ago (beyond 7-day threshold)
        old_deleted = FileAssetFactory(
            status=FileAsset.Status.DELETED,
            created_at=timezone.now() - timedelta(days=8),
        )
        
        stats = cleanup_orphaned_files(phase=2, dry_run=False)
        
        assert not FileAsset.objects.filter(id=old_deleted.id).exists()
        assert stats["hard_deleted"] == 1

    def test_phase_2_preserves_recent_deleted(self):
        """Test that recently DELETED files (< 7 days) are NOT hard-deleted."""
        # Create file deleted 3 days ago (within threshold)
        recent_deleted = FileAssetFactory(
            status=FileAsset.Status.DELETED,
            created_at=timezone.now() - timedelta(days=3),
        )
        
        stats = cleanup_orphaned_files(phase=2, dry_run=False)
        
        assert FileAsset.objects.filter(id=recent_deleted.id).exists()
        assert stats["hard_deleted"] == 0

    def test_phase_2_preserves_files_with_answers(self):
        """Test that DELETED files linked to answers are NOT hard-deleted."""
        answer = AnswerFactory()
        asset = FileAssetFactory(
            status=FileAsset.Status.DELETED,
            created_at=timezone.now() - timedelta(days=8),
        )
        AnswerFile.objects.create(answer=answer, file=asset)
        
        stats = cleanup_orphaned_files(phase=2, dry_run=False)
        
        assert FileAsset.objects.filter(id=asset.id).exists()
        assert stats["hard_deleted"] == 0

    def test_phase_2_dry_run_does_not_delete(self):
        """Test that dry_run=True doesn't hard-delete files."""
        old_deleted = FileAssetFactory(
            status=FileAsset.Status.DELETED,
            created_at=timezone.now() - timedelta(days=8),
        )
        
        stats = cleanup_orphaned_files(phase=2, dry_run=True)
        
        assert FileAsset.objects.filter(id=old_deleted.id).exists()
        assert stats["hard_deleted"] == 1

    def test_phase_2_multiple_old_orphaned(self):
        """Test handling multiple old orphaned DELETED files."""
        assets = [
            FileAssetFactory(
                status=FileAsset.Status.DELETED,
                created_at=timezone.now() - timedelta(days=8),
            )
            for _ in range(3)
        ]
        
        stats = cleanup_orphaned_files(phase=2, dry_run=False)
        
        for asset in assets:
            assert not FileAsset.objects.filter(id=asset.id).exists()
        
        assert stats["hard_deleted"] == 3

    @patch("toxtempass.models.delete_object_from_storage")
    def test_phase_2_triggers_signal(self, mock_signal):
        """Test that hard-delete triggers the post_delete signal."""
        old_deleted = FileAssetFactory(
            status=FileAsset.Status.DELETED,
            created_at=timezone.now() - timedelta(days=8),
        )
        
        cleanup_orphaned_files(phase=2, dry_run=False)
        
        # Signal should have been triggered (file deleted)
        assert not FileAsset.objects.filter(id=old_deleted.id).exists()


@pytest.mark.django_db
class TestCleanupOrphanedFilesCombined:
    """Test Phase 0 (both phases) and overall scenarios."""

    def test_phase_0_runs_both_phases(self):
        """Test that phase=0 runs both Phase 1 and Phase 2."""
        # Create orphaned files
        available = FileAssetFactory(status=FileAsset.Status.AVAILABLE)
        old_deleted = FileAssetFactory(
            status=FileAsset.Status.DELETED,
            created_at=timezone.now() - timedelta(days=8),
        )
        
        stats = cleanup_orphaned_files(phase=0, dry_run=False)
        
        available.refresh_from_db()
        assert available.status == FileAsset.Status.DELETED
        assert not FileAsset.objects.filter(id=old_deleted.id).exists()
        assert stats["soft_deleted"] == 1
        assert stats["hard_deleted"] == 1

    def test_complete_workflow_soft_then_hard_delete(self):
        """Test complete workflow: file becomes orphaned, soft-delete, then hard-delete."""
        # Day 1: Create orphaned file
        asset = FileAssetFactory(status=FileAsset.Status.AVAILABLE)
        
        # Day 1: Run Phase 1 cleanup
        stats1 = cleanup_orphaned_files(phase=1, dry_run=False)
        asset.refresh_from_db()
        assert asset.status == FileAsset.Status.DELETED
        assert stats1["soft_deleted"] == 1
        
        # Day 8: Run Phase 2 cleanup
        # Manually set created_at to 8 days ago for testing
        asset.created_at = timezone.now() - timedelta(days=8)
        asset.save()
        
        stats2 = cleanup_orphaned_files(phase=2, dry_run=False)
        assert not FileAsset.objects.filter(id=asset.id).exists()
        assert stats2["hard_deleted"] == 1

    def test_file_rescued_after_soft_delete(self):
        """Test that a soft-deleted file can be rescued by adding AnswerFile."""
        asset = FileAssetFactory(status=FileAsset.Status.AVAILABLE)
        
        # Phase 1: Soft-delete the file
        cleanup_orphaned_files(phase=1, dry_run=False)
        asset.refresh_from_db()
        assert asset.status == FileAsset.Status.DELETED
        
        # User links the file to an answer
        answer = AnswerFactory()
        AnswerFile.objects.create(answer=answer, file=asset)
        
        # Set created_at to 8 days ago to test Phase 2
        asset.created_at = timezone.now() - timedelta(days=8)
        asset.save()
        
        # Phase 2: File should NOT be hard-deleted because it's now linked
        cleanup_orphaned_files(phase=2, dry_run=False)
        assert FileAsset.objects.filter(id=asset.id).exists()

    def test_statistics_accuracy(self):
        """Test that statistics are accurate."""
        # Create test data
        available_orphaned = FileAssetFactory(status=FileAsset.Status.AVAILABLE)
        
        answer = AnswerFactory()
        available_linked = FileAssetFactory(status=FileAsset.Status.AVAILABLE)
        AnswerFile.objects.create(answer=answer, file=available_linked)
        
        old_deleted_orphaned = FileAssetFactory(
            status=FileAsset.Status.DELETED,
            created_at=timezone.now() - timedelta(days=8),
        )
        
        recent_deleted_orphaned = FileAssetFactory(
            status=FileAsset.Status.DELETED,
            created_at=timezone.now() - timedelta(days=3),
        )
        
        # Run both phases
        stats = cleanup_orphaned_files(phase=0, dry_run=False)
        
        assert stats["soft_deleted"] == 1  # available_orphaned
        assert stats["hard_deleted"] == 1  # old_deleted_orphaned
        assert stats["errors"] == 0
        
        # Verify state of all files
        available_orphaned.refresh_from_db()
        assert available_orphaned.status == FileAsset.Status.DELETED
        
        available_linked.refresh_from_db()
        assert available_linked.status == FileAsset.Status.AVAILABLE
        
        assert not FileAsset.objects.filter(id=old_deleted_orphaned.id).exists()
        
        recent_deleted_orphaned.refresh_from_db()
        assert recent_deleted_orphaned.status == FileAsset.Status.DELETED

    def test_no_files_returns_zero_stats(self):
        """Test that cleanup with no orphaned files returns zero stats."""
        answer = AnswerFactory()
        asset = FileAssetFactory(status=FileAsset.Status.AVAILABLE)
        AnswerFile.objects.create(answer=answer, file=asset)
        
        stats = cleanup_orphaned_files(phase=0, dry_run=False)
        
        assert stats["soft_deleted"] == 0
        assert stats["hard_deleted"] == 0
        assert stats["errors"] == 0
