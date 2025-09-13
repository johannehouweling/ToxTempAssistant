from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.datastructures import MultiValueDict
from unittest.mock import patch

from toxtempass.tests.fixtures.factories import (
    PersonFactory,
    InvestigationFactory,
    StudyFactory,
    AssayFactory,
)
from toxtempass.forms import AssayAnswerForm


class FileUploadTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = PersonFactory()
        # Ensure the investigation/assay are owned by the user so permission checks pass
        self.investigation = InvestigationFactory(owner=self.user)
        self.study = StudyFactory(investigation=self.investigation)
        self.assay = AssayFactory(study=self.study)

    def test_answer_view_accepts_multiple_files(self):
        """
        Form-level test: instantiate AssayAnswerForm with two uploaded files and
        assert the processing functions are invoked. This avoids test-client
        upload mechanics which can be brittle in tests.
        """
        from unittest.mock import patch as _patch
        from django.utils.datastructures import MultiValueDict

        dummy_text = {"a.txt": {"text": "alpha"}, "b.txt": {"text": "beta"}}

        f1 = SimpleUploadedFile("a.txt", b"alpha", content_type="text/plain")
        f2 = SimpleUploadedFile("b.txt", b"beta", content_type="text/plain")

        files = MultiValueDict({"file_upload": [f1, f2]})

        with _patch("toxtempass.forms.get_text_or_imagebytes_from_django_uploaded_file") as mock_get_text, _patch(
            "toxtempass.forms.split_doc_dict_by_type"
        ) as mock_split:
            mock_get_text.return_value = dummy_text
            mock_split.return_value = (dummy_text, {})

            form = AssayAnswerForm(data={}, files=files, assay=self.assay, user=self.user)
            self.assertTrue(form.is_valid(), msg=f"Form errors: {form.errors}")
            form.save()

            # Ensure get_text_or_imagebytes_from_django_uploaded_file was called
            self.assertTrue(mock_get_text.called)
            called_args = mock_get_text.call_args[0][0]
            self.assertEqual(len(list(called_args)), 2)

    def test_assayanswerform_clean_accepts_multiple_files(self):
        """
        Direct form-level test: instantiate AssayAnswerForm with files mapping containing
        two SimpleUploadedFile objects and assert validation passes.
        """
        f1 = SimpleUploadedFile("a.txt", b"alpha", content_type="text/plain")
        f2 = SimpleUploadedFile("b.txt", b"beta", content_type="text/plain")

        files = MultiValueDict({"file_upload": [f1, f2]})

        form = AssayAnswerForm(data={}, files=files, assay=self.assay, user=self.user)
        # The form should validate (no required question fields enforced here)
        self.assertTrue(form.is_valid(), msg=f"Form errors: {form.errors}")
        cleaned = form.cleaned_data.get("file_upload", [])
        self.assertEqual(len(cleaned), 2)

    @patch("toxtempass.forms.config.max_size_mb", new=0.000001)
    def test_assayanswerform_rejects_oversize_file(self):
        """
        Force the configured max_size_mb to a very small value so that a small
        uploaded file becomes oversized and triggers validation error.
        """
        large_content = b"too large"
        f = SimpleUploadedFile("big.txt", large_content, content_type="text/plain")
        files = MultiValueDict({"file_upload": [f]})

        form = AssayAnswerForm(data={}, files=files, assay=self.assay, user=self.user)
        # Cleaning/validation should fail due to oversize
        self.assertFalse(form.is_valid())
        # Ensure the error mentions exceeds
        errors = (
            form.errors.get("__all__") or form.errors.get("file_upload") or form.errors
        )
        # Flatten errors to a string for a robust assertion
        error_str = str(errors)
        self.assertIn("exceeds", error_str.lower())
