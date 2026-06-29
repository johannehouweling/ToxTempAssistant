from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.utils.datastructures import MultiValueDict
from PIL import Image

from toxtempass.forms import AssayAnswerForm
from toxtempass.models import (
    Answer,
    AnswerFile,
    Question,
    QuestionSet,
    Section,
    Subsection,
)
from toxtempass.tests.fixtures.factories import (
    AssayFactory,
    FileAssetFactory,
    InvestigationFactory,
    PersonFactory,
    StudyFactory,
)


class FileUploadTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = PersonFactory()
        # Ensure the investigation/assay are owned by the user so permission checks pass
        self.investigation = InvestigationFactory(owner=self.user)
        self.study = StudyFactory(investigation=self.investigation)
        self.assay = AssayFactory(study=self.study)

    @staticmethod
    def _png_file(name="answer.png"):
        image_buffer = BytesIO()
        Image.new("RGB", (2, 2), color="white").save(image_buffer, format="PNG")
        return SimpleUploadedFile(
            name,
            image_buffer.getvalue(),
            content_type="image/png",
        )

    def test_answer_view_accepts_multiple_files(self):
        """
        Form-level test: instantiate AssayAnswerForm with two uploaded files and
        assert the processing functions are invoked. This avoids test-client
        upload mechanics which can be brittle in tests.
        """
        qs = QuestionSet.objects.create(
            display_name="test-qs", created_by=self.assay.study.investigation.owner
        )
        section = Section.objects.create(question_set=qs, title="Sec")
        subsection = Subsection.objects.create(section=section, title="Subsec")
        question = Question.objects.create(subsection=subsection, question_text="Q1?")
        Answer.objects.get_or_create(assay=self.assay, question=question)
        self.assay.question_set = qs
        self.assay.save()

        dummy_doc = {
            "a.txt": {"text": "alpha", "source_document": "a.txt", "origin": "document"}
        }

        f1 = SimpleUploadedFile("a.txt", b"alpha", content_type="text/plain")
        f2 = SimpleUploadedFile("b.txt", b"beta", content_type="text/plain")

        files = MultiValueDict({"file_upload": [f1, f2]})

        with patch(
            "toxtempass.forms.get_text_or_imagebytes_from_django_uploaded_file",
            return_value=(dummy_doc, []),
        ) as mock_get_text, patch("toxtempass.forms.async_task") as mock_async:
            form = AssayAnswerForm(
                data={f"earmarked_{question.id}": True},
                files=files,
                assay=self.assay,
                user=self.user,
            )
            self.assertTrue(form.is_valid(), msg=f"Form errors: {form.errors}")
            queued = form.save()

            mock_get_text.assert_called_once()
            mock_async.assert_called_once()
            self.assertTrue(queued)
            self.assertTrue(getattr(form, "async_enqueued", False))

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

    def test_assayanswerform_rejects_legacy_doc_mime_type(self):
        """
        application/msword (.doc) is no longer in ALLOWED_MIME_TYPES because
        the old Word format cannot be parsed.  Uploading such a file must
        trigger a validation error at the form-cleaning stage.
        """
        f = SimpleUploadedFile(
            "report.doc", b"PK\x03\x04dummy", content_type="application/msword"
        )
        files = MultiValueDict({"file_upload": [f]})

        form = AssayAnswerForm(data={}, files=files, assay=self.assay, user=self.user)
        self.assertFalse(form.is_valid())
        error_str = str(form.errors)
        self.assertIn("unsupported file type", error_str.lower())

    def test_assayanswerform_save_warns_on_unreadable_file(self):
        """
        When get_text_or_imagebytes_from_django_uploaded_file reports that a
        file could not be parsed, save() must add a user-visible alert on the
        assay and still proceed if at least one other file was readable.
        """
        qs = QuestionSet.objects.create(
            display_name="test-qs", created_by=self.assay.study.investigation.owner
        )
        section = Section.objects.create(question_set=qs, title="Sec")
        subsection = Subsection.objects.create(section=section, title="Subsec")
        question = Question.objects.create(subsection=subsection, question_text="Q1?")
        Answer.objects.get_or_create(assay=self.assay, question=question)
        self.assay.question_set = qs
        self.assay.save()

        dummy_doc = {
            "good.txt": {
                "text": "readable content",
                "source_document": "good.txt",
                "origin": "document",
            }
        }

        f1 = SimpleUploadedFile("good.txt", b"readable", content_type="text/plain")
        f2 = SimpleUploadedFile("bad.pdf", b"corrupt", content_type="application/pdf")
        files = MultiValueDict({"file_upload": [f1, f2]})

        with patch(
            "toxtempass.forms.get_text_or_imagebytes_from_django_uploaded_file",
            return_value=(dummy_doc, ["bad.pdf"]),
        ), patch("toxtempass.forms.async_task"):
            form = AssayAnswerForm(
                data={f"earmarked_{question.id}": True},
                files=files,
                assay=self.assay,
                user=self.user,
            )
            self.assertTrue(form.is_valid(), msg=f"Form errors: {form.errors}")
            result = form.save()

        self.assertTrue(result)
        self.assay.refresh_from_db()
        alerts = self.assay.user_alerts or []
        alert_messages = [a["message"] for a in alerts]
        self.assertTrue(
            any("bad.pdf" in msg for msg in alert_messages),
            msg=f"Expected 'bad.pdf' warning in user_alerts, got: {alert_messages}",
        )

    def test_assayanswerform_save_blocks_when_all_files_unreadable(self):
        """
        When every uploaded file fails to parse (all unreadable), save() must
        add a form error and return False instead of queuing an async task.
        """
        qs = QuestionSet.objects.create(
            display_name="test-qs2", created_by=self.assay.study.investigation.owner
        )
        section = Section.objects.create(question_set=qs, title="Sec2")
        subsection = Subsection.objects.create(section=section, title="Subsec2")
        question = Question.objects.create(subsection=subsection, question_text="Q2?")
        Answer.objects.get_or_create(assay=self.assay, question=question)
        self.assay.question_set = qs
        self.assay.save()

        f = SimpleUploadedFile("broken.pdf", b"notapdf", content_type="application/pdf")
        files = MultiValueDict({"file_upload": [f]})

        with patch(
            "toxtempass.forms.get_text_or_imagebytes_from_django_uploaded_file",
            return_value=({}, ["broken.pdf"]),
        ), patch("toxtempass.forms.async_task") as mock_async:
            form = AssayAnswerForm(
                data={f"earmarked_{question.id}": True},
                files=files,
                assay=self.assay,
                user=self.user,
            )
            self.assertTrue(form.is_valid(), msg=f"Form errors: {form.errors}")
            result = form.save()

        self.assertFalse(result)
        mock_async.assert_not_called()
        error_str = str(form.errors)
        self.assertIn("none of the uploaded files could be read", error_str.lower())

    def test_assayanswerform_save_stores_answer_image(self):
        qs = QuestionSet.objects.create(
            display_name="test-qs-image", created_by=self.assay.study.investigation.owner
        )
        section = Section.objects.create(question_set=qs, title="Sec")
        subsection = Subsection.objects.create(section=section, title="Subsec")
        question = Question.objects.create(
            subsection=subsection, question_text="Q image?"
        )
        self.assay.question_set = qs
        self.assay.save()

        stored_asset = FileAssetFactory(
            original_filename="answer.png",
            content_type="image/png",
            uploaded_by=self.user,
        )
        uploaded_image = self._png_file()

        with patch(
            "toxtempass.forms.store_files_to_storage",
            return_value=[stored_asset],
        ) as mock_store:
            form = AssayAnswerForm(
                data={f"question_{question.id}": "", f"accepted_{question.id}": True},
                files=MultiValueDict({f"answer_image_{question.id}": [uploaded_image]}),
                assay=self.assay,
                user=self.user,
            )
            self.assertTrue(form.is_valid(), msg=f"Form errors: {form.errors}")
            saved = form.save()

        self.assertFalse(saved)
        mock_store.assert_called_once()
        answer = Answer.objects.get(assay=self.assay, question=question)
        answer_file = AnswerFile.objects.get(answer=answer, file=stored_asset)
        self.assertEqual(answer_file.label, "answer_image")
        self.assertTrue(answer.accepted)

    def test_assayanswerform_shows_existing_answer_image_names(self):
        qs = QuestionSet.objects.create(
            display_name="test-qs-existing-image",
            created_by=self.assay.study.investigation.owner,
        )
        section = Section.objects.create(question_set=qs, title="Sec")
        subsection = Subsection.objects.create(section=section, title="Subsec")
        question = Question.objects.create(
            subsection=subsection, question_text="Q image?"
        )
        answer = Answer.objects.create(assay=self.assay, question=question)
        asset = FileAssetFactory(
            original_filename="existing-image.png",
            content_type="image/png",
            uploaded_by=self.user,
        )
        AnswerFile.objects.create(answer=answer, file=asset, label="answer_image")
        self.assay.question_set = qs
        self.assay.save()

        form = AssayAnswerForm(data={}, assay=self.assay, user=self.user)

        self.assertIn(
            "existing-image.png",
            form.fields[f"answer_image_{question.id}"].help_text,
        )
