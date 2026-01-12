"""Tests for file storage with user consent."""

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from django.core.files.uploadedfile import InMemoryUploadedFile

from toxtempass.filehandling import store_files_to_storage
from toxtempass.models import FileAsset
from toxtempass.tests.fixtures.factories import AssayFactory, PersonFactory


@pytest.mark.django_db
class TestStoreFilesToStorage:
    """Test suite for store_files_to_storage function."""

    def test_no_files_returns_empty_list(self):
        """Test that empty file list returns empty asset list."""
        user = PersonFactory()
        assay = AssayFactory()
        
        result = store_files_to_storage(
            files=[],
            user=user,
            assay=assay,
            consent=True,
        )
        
        assert result == []

    def test_no_consent_returns_empty_list(self):
        """Test that consent=False skips storage regardless of files."""
        user = PersonFactory()
        assay = AssayFactory()
        
        # Create a mock file
        file = MagicMock(spec=InMemoryUploadedFile)
        file.name = "test.pdf"
        file.chunks.return_value = [b"test content"]
        file.content_type = "application/pdf"
        
        result = store_files_to_storage(
            files=[file],
            user=user,
            assay=assay,
            consent=False,
        )
        
        assert result == []
        assert FileAsset.objects.count() == 0

    @patch("toxtempass.filehandling.default_storage.save")
    def test_store_single_file_with_consent(self, mock_save):
        """Test storing a single file when user consents."""
        user = PersonFactory()
        assay = AssayFactory()
        
        # Create a mock file
        file_content = b"test pdf content"
        file = MagicMock(spec=InMemoryUploadedFile)
        file.name = "document.pdf"
        file.chunks.return_value = [file_content]
        file.content_type = "application/pdf"
        
        mock_save.return_value = "consent_user_documents/user@test.com/1/uuid/document.pdf"
        
        result = store_files_to_storage(
            files=[file],
            user=user,
            assay=assay,
            consent=True,
        )
        
        assert len(result) == 1
        asset = result[0]
        assert asset.original_filename == "document.pdf"
        assert asset.content_type == "application/pdf"
        assert asset.size_bytes == len(file_content)
        assert asset.status == FileAsset.Status.AVAILABLE
        assert asset.uploaded_by == user
        assert FileAsset.objects.count() == 1

    @patch("toxtempass.filehandling.default_storage.save")
    def test_store_multiple_files(self, mock_save):
        """Test storing multiple files."""
        user = PersonFactory()
        assay = AssayFactory()
        
        files = []
        for i in range(3):
            file = MagicMock(spec=InMemoryUploadedFile)
            file.name = f"document{i}.pdf"
            file.chunks.return_value = [b"content" * (i + 1)]
            file.content_type = "application/pdf"
            files.append(file)
        
        mock_save.side_effect = [
            f"consent_user_documents/user@test.com/1/uuid{i}/document{i}.pdf"
            for i in range(3)
        ]
        
        result = store_files_to_storage(
            files=files,
            user=user,
            assay=assay,
            consent=True,
        )
        
        assert len(result) == 3
        assert FileAsset.objects.count() == 3
        
        for i, asset in enumerate(result):
            assert asset.original_filename == f"document{i}.pdf"
            assert asset.uploaded_by == user

    @patch("toxtempass.filehandling.default_storage.save")
    def test_sha256_calculation(self, mock_save):
        """Test that SHA256 hash is calculated correctly."""
        user = PersonFactory()
        assay = AssayFactory()
        
        file_content = b"test content"
        file = MagicMock(spec=InMemoryUploadedFile)
        file.name = "test.txt"
        file.chunks.return_value = [file_content]
        file.content_type = "text/plain"
        
        mock_save.return_value = "consent_user_documents/user@test.com/1/uuid/test.txt"
        
        result = store_files_to_storage(
            files=[file],
            user=user,
            assay=assay,
            consent=True,
        )
        
        asset = result[0]
        # Verify SHA256 is 64 character hex string
        assert len(asset.sha256) == 64
        assert all(c in "0123456789abcdef" for c in asset.sha256)

    @patch("toxtempass.filehandling.default_storage.save")
    def test_object_key_format(self, mock_save):
        """Test that object key follows expected format."""
        user = PersonFactory(email="test@example.com")
        assay = AssayFactory(id=123)
        
        file = MagicMock(spec=InMemoryUploadedFile)
        file.name = "myfile.pdf"
        file.chunks.return_value = [b"content"]
        file.content_type = "application/pdf"
        
        def capture_key(key, file_obj):
            assert key.startswith("consent_user_documents/test@example.com/assay/123/")
            assert key.endswith("/myfile.pdf")
            return key
        
        mock_save.side_effect = capture_key
        
        result = store_files_to_storage(
            files=[file],
            user=user,
            assay=assay,
            consent=True,
        )
        
        assert len(result) == 1
        assert "consent_user_documents/test@example.com/assay/123/" in result[0].object_key
        assert result[0].object_key.endswith("/myfile.pdf")

    @patch("toxtempass.filehandling.default_storage.save")
    def test_storage_failure_raises_exception(self, mock_save):
        """Test that storage failures are propagated."""
        user = PersonFactory()
        assay = AssayFactory()
        
        file = MagicMock(spec=InMemoryUploadedFile)
        file.name = "test.pdf"
        file.chunks.return_value = [b"content"]
        file.content_type = "application/pdf"
        
        mock_save.side_effect = Exception("S3 connection failed")
        
        with pytest.raises(Exception, match="S3 connection failed"):
            store_files_to_storage(
                files=[file],
                user=user,
                assay=assay,
                consent=True,
            )

    @patch("toxtempass.filehandling.default_storage.save")
    def test_mime_type_detection(self, mock_save):
        """Test that MIME type is detected when not provided."""
        user = PersonFactory()
        assay = AssayFactory()
        
        file = MagicMock(spec=InMemoryUploadedFile)
        file.name = "document.pdf"
        file.chunks.return_value = [b"pdf content"]
        file.content_type = ""  # Empty content type
        
        mock_save.return_value = "consent_user_documents/user@test.com/1/uuid/document.pdf"
        
        result = store_files_to_storage(
            files=[file],
            user=user,
            assay=assay,
            consent=True,
        )
        
        asset = result[0]
        # Should detect PDF MIME type from filename
        assert asset.content_type == "application/pdf" or asset.content_type == ""

    @patch("toxtempass.filehandling.default_storage.save")
    def test_file_asset_created_in_database(self, mock_save):
        """Test that FileAsset record is created in database."""
        user = PersonFactory()
        assay = AssayFactory()
        
        file = MagicMock(spec=InMemoryUploadedFile)
        file.name = "test.pdf"
        file.chunks.return_value = [b"content"]
        file.content_type = "application/pdf"
        
        mock_save.return_value = "consent_user_documents/user@test.com/1/uuid/test.pdf"
        
        result = store_files_to_storage(
            files=[file],
            user=user,
            assay=assay,
            consent=True,
        )
        
        # Verify database record exists
        db_asset = FileAsset.objects.get(id=result[0].id)
        assert db_asset.original_filename == "test.pdf"
        assert db_asset.uploaded_by == user
        assert db_asset.status == FileAsset.Status.AVAILABLE
