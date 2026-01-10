# Implementation Plan: S3/MinIO File Storage with Consent

## [Overview]
Implement file storage to S3/MinIO for user-uploaded context documents, respecting user consent via the `share_files_for_development` checkbox on the StartingForm. Files are stored immediately upon form submission (if consent is given), with FileAsset records created and linked to Answer objects through the AnswerFile junction table. A management command cleans up orphaned FileAsset records that were never linked to answers.

### Key Design Decisions
- **Timing:** Files stored immediately on StartingForm submission if `share_files_for_development=True`
- **S3 Naming:** Use UUID-based object keys in S3; original filename stored in DB only
- **Orphan Cleanup:** Periodic cleanup of FileAsset records not linked to any Answer (e.g., if LLM processing fails)
- **Admin Feature:** Download all files associated with an assay from admin panel
- **Consent:** Default to opt-in (`initial=True`), remove `consent_acknowledged` validation for simpler UX

## [Types]
New/Modified models and type definitions:

**FileAsset Model (existing):**
- `id` (UUIDField): Primary key
- `bucket` (CharField): S3 bucket name
- `object_key` (CharField): UUID-based S3 object key
- `original_filename` (CharField): Original user-provided filename
- `content_type` (CharField): MIME type
- `size_bytes` (BigIntegerField): File size
- `sha256` (CharField): File hash for integrity
- `status` (CharField): 'available' or 'deleted'
- `uploaded_by` (ForeignKey to Person): User who uploaded
- `created_at` (DateTimeField): Upload timestamp

**AnswerFile Model (existing):**
- Junction table linking Answer to FileAsset
- `answer` (ForeignKey): Related Answer
- `file` (ForeignKey): Related FileAsset
- `label` (CharField): Optional metadata
- `created_at` (DateTimeField): Link timestamp

**Answer Model (modified):**
- `files` (ManyToManyField): Through AnswerFile to FileAsset

## [Files]

### Existing files to be modified:

1. **`myocyte/toxtempass/views.py`**
   - Modify `new_form_view()`:
     - Extract `share_files_for_development` from cleaned form data
     - If True: upload files to S3 and collect FileAsset IDs
     - Pass FileAsset IDs to `process_llm_async()` along with existing doc_dict
   - Modify `process_llm_async()`:
     - Accept new optional `file_asset_ids` parameter
     - When saving Answer objects: link FileAssets to Answers via AnswerFile
     - Handle missing FileAssets gracefully if deleted during processing

2. **`myocyte/toxtempass/forms.py`**
   - Remove `consent_acknowledged` field from StartingForm
   - Remove validation for `consent_acknowledged` in `clean()` method
   - Keep `share_files_for_development` with `initial=True`

### New files to be created:

1. **`myocyte/toxtempass/fileops.py`**
   - New utility module for all S3 file operations
   - Functions:
     - `upload_file_to_s3(uploaded_file, user) → FileAsset`
     - `link_files_to_answer(answer, file_asset_ids) → list[AnswerFile]`
     - `get_orphaned_file_assets(days=7) → QuerySet[FileAsset]`
     - `delete_orphaned_file_assets(file_assets) → tuple[int, dict]`
     - `download_assay_files(assay) → BytesIO`
     - `compute_sha256(file_obj) → str`

2. **`myocyte/toxtempass/management/commands/cleanup_orphaned_files.py`**
   - Django management command
   - Find FileAssets older than N days with no AnswerFile links
   - Delete both FileAsset records and S3 objects
   - Log all deletions for auditing

3. **`myocyte/toxtempass/tests/test_file_storage_s3.py`**
   - Comprehensive test suite for file storage operations
   - Mock S3 backend for unit tests
   - Test upload, linking, orphan detection, cleanup, and download

## [Functions]

### New functions in `myocyte/toxtempass/fileops.py`:

1. **`upload_file_to_s3(uploaded_file: UploadedFile, user: Person) → FileAsset`**
   - Upload Django UploadedFile to default S3 storage
   - Generate UUID-based object key
   - Compute SHA256 hash
   - Create and save FileAsset record with metadata
   - Return FileAsset instance

2. **`link_files_to_answer(answer: Answer, file_asset_ids: list[UUID]) → list[AnswerFile]`**
   - Create AnswerFile records for each FileAsset ID
   - Handle duplicate links gracefully (get_or_create)
   - Log any FileAssets that no longer exist
   - Return list of created/retrieved AnswerFile instances

3. **`get_orphaned_file_assets(days: int = 7) → QuerySet[FileAsset]`**
   - Query FileAssets created before `days` ago
   - Filter to those with no related AnswerFile records
   - Return QuerySet for further processing

4. **`delete_orphaned_file_assets(file_assets: QuerySet[FileAsset]) → tuple[int, dict]`**
   - Delete S3 objects for each FileAsset
   - Delete FileAsset records
   - Track and return count of deleted objects
   - Return dict of errors if any S3 deletions fail

5. **`download_assay_files(assay: Assay) → BytesIO`**
   - Collect all FileAssets linked to assay's answers
   - Create ZIP file containing all files
   - Organize by question within ZIP (optional)
   - Return BytesIO ready for download response

6. **`compute_sha256(file_obj: File) → str`**
   - Helper function to compute SHA256 hash of file
   - Handle chunked reading for large files
   - Return hex digest string

### Modified functions in `myocyte/toxtempass/views.py`:

7. **`new_form_view(request: HttpRequest) → HttpResponse | JsonResponse`**
   - After form validation: check `share_files_for_development`
   - If True and files uploaded:
     - Call `upload_file_to_s3()` for each file
     - Collect FileAsset IDs in list
     - Pass list to `process_llm_async()` as new parameter
   - Preserve existing doc_dict processing logic

8. **`process_llm_async(assay_id, doc_dict=None, extract_images=False, answer_ids=None, chatopenai=None, verbose=False, file_asset_ids=None)`**
   - Add new optional parameter: `file_asset_ids: list[UUID] | None = None`
   - After generating and saving each Answer:
     - If `file_asset_ids` provided: call `link_files_to_answer(answer, file_asset_ids)`
     - Log success/failure of linking
   - Maintain backward compatibility with existing calls

## [Classes]

### Modified classes:

**FileAsset (in `myocyte/toxtempass/models.py`):**
- No changes needed to model fields
- Add custom manager: `FileAssetManager`

### New classes:

**FileAssetManager (in `myocyte/toxtempass/models.py`):**
```python
class FileAssetManager(models.Manager):
    def get_orphaned(self, days: int = 7) -> QuerySet:
        """Get FileAssets created before N days ago with no answer links."""
        from toxtempass.fileops import get_orphaned_file_assets
        return get_orphaned_file_assets(days)
    
    def cleanup_orphaned(self, days: int = 7) -> tuple[int, dict]:
        """Delete orphaned FileAssets and their S3 objects."""
        from toxtempass.fileops import delete_orphaned_file_assets
        orphans = self.get_orphaned(days)
        return delete_orphaned_file_assets(orphans)
```

## [Dependencies]
No new dependencies required. Using existing packages:
- `django-storages[s3]` - Already installed for S3 backend
- `boto3` - Dependency of django-storages
- Django's `default` storage backend - Already configured as S3Storage

## [Testing]

### New test file: `myocyte/toxtempass/tests/test_file_storage_s3.py`
Test cases:
1. Test `upload_file_to_s3()` with various file types (PDF, DOCX, CSV, images)
2. Test SHA256 computation correctness
3. Test `link_files_to_answer()` creates AnswerFile records
4. Test linking same FileAsset to multiple Answers
5. Test `get_orphaned_file_assets()` correctly identifies orphans
6. Test `delete_orphaned_file_assets()` removes records and S3 objects
7. Test `download_assay_files()` generates valid ZIP
8. Mock S3 storage for unit tests (use Django's InMemoryStorage)

### Modified test files:

**`myocyte/toxtempass/tests/test_file_uploads.py`:**
- Add test: StartingForm with `share_files_for_development=True` triggers upload
- Add test: StartingForm with `share_files_for_development=False` skips upload
- Add test: Verify FileAsset records created when consent is given

**`myocyte/toxtempass/tests/test_process_llm_async.py`:**
- Add test: FileAssets linked to Answer objects after LLM processing
- Add test: Graceful handling if FileAsset deleted during processing
- Add test: Multiple answers can share same FileAsset

## [Implementation Order]

1. **Remove `consent_acknowledged` from StartingForm**
   - File: `myocyte/toxtempass/forms.py`
   - Remove field definition and validation

2. **Create `myocyte/toxtempass/fileops.py`**
   - Implement `compute_sha256()`
   - Implement `upload_file_to_s3()`
   - Implement `link_files_to_answer()`
   - Implement `get_orphaned_file_assets()`
   - Implement `delete_orphaned_file_assets()`
   - Implement `download_assay_files()`

3. **Update FileAsset model with custom manager**
   - File: `myocyte/toxtempass/models.py`
   - Add FileAssetManager class
   - Set `objects = FileAssetManager()` on FileAsset

4. **Modify `new_form_view()` in views.py**
   - Check `share_files_for_development` after form validation
   - Upload files to S3 and collect FileAsset IDs
   - Pass FileAsset IDs to `process_llm_async()`

5. **Modify `process_llm_async()` in views.py**
   - Add `file_asset_ids` parameter
   - Link FileAssets to Answers after saving

6. **Create management command**
   - File: `myocyte/toxtempass/management/commands/cleanup_orphaned_files.py`
   - Implement command with configurable `days` argument
   - Add logging and dry-run option

7. **Create comprehensive test suite**
   - File: `myocyte/toxtempass/tests/test_file_storage_s3.py`
   - Implement all test cases with mocked S3

8. **Update existing test files**
   - Add tests to `test_file_uploads.py`
   - Add tests to `test_process_llm_async.py`

9. **Manual testing**
   - Test full flow: upload with consent → LLM processing → files linked
   - Test upload without consent → no S3 storage
   - Test orphan cleanup command
   - Verify S3 buckets contain files with UUID keys

---

**Implementation complete. Ready to proceed with Act Mode coding.**
