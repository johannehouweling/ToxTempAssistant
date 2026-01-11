import logging
from io import BytesIO

from django.contrib import admin
from django.http import FileResponse

from toxtempass.filehandling import download_assay_files_as_zip
from toxtempass.models import (
    Answer,
    Assay,
    Feedback,
    Investigation,
    Person,
    Question,
    QuestionSet,
    Section,
    Study,
    Subsection,
    FileAsset
)

logger = logging.getLogger(__name__)


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "email", "orcid_id")
    search_fields = ("first_name", "last_name", "email", "orcid_id")


@admin.register(Investigation)
class InvestigationAdmin(admin.ModelAdmin):
    list_display = ("title", "submission_date")
    search_fields = ("title",)


@admin.register(Study)
class StudyAdmin(admin.ModelAdmin):
    list_display = ("title", "investigation", "submission_date")
    search_fields = ("title", "investigation__name")


@admin.register(Assay)
class AssayAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "study",
        "submission_date",
        "feedback__feedback_text",
        "number_answers_not_found",
    )
    search_fields = ("title", "study__name")
    actions = ["download_assay_files"]

    def download_assay_files(self, request, queryset):
        """Custom admin action to download files associated with selected assays."""
        if not request.user.is_staff or not request.user.is_superuser:
            self.message_user(request, "You do not have permission to download files.", level="error")
            return

        if queryset.count() != 1:
            self.message_user(request, "Please select exactly one assay.", level="error")
            return

        assay = queryset.first()
        try:
            zip_bytes, filename = download_assay_files_as_zip(assay, request.user, request)

            if not zip_bytes:
                self.message_user(request, "No files found for this assay.", level="warning")
                return

            # Wrap zip_bytes in BytesIO for FileResponse
            response = FileResponse(BytesIO(zip_bytes), content_type="application/zip")
            response["Content-Disposition"] = f'attachment; filename="{filename}"'

            logger.info(
                "User %s downloaded files for assay %s",
                request.user.email,
                assay.id,
            )

            return response

        except Exception as exc:
            logger.exception("Failed to download files for assay %s: %s", assay.id, exc)
            self.message_user(
                request,
                f"Failed to download files: {str(exc)}",
                level="error",
            )

    download_assay_files.short_description = "Download assay files as ZIP"


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("title",)
    search_fields = ("title",)


@admin.register(Subsection)
class SubsectionAdmin(admin.ModelAdmin):
    list_display = ("title", "section")
    search_fields = ("title", "section__title")


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "question_text", "subsection", "answer")
    search_fields = ("question_text", "subsection__title")


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ("assay", "question", "preview_text", "accepted")
    search_fields = ("assay__name", "question", "accepted")

@admin.register(FileAsset)
class FileAssetAdmin(admin.ModelAdmin):
    list_display = ("id", "original_filename", "uploaded_by")

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("assay", "user", "feedback_text", "usefulness_rating")
    search_fields = ("assay__name", "user")


@admin.register(QuestionSet)
class QuestionSetAdmin(admin.ModelAdmin):
    list_display = ("id", "label", "display_name", "created_at", "is_visible")
    search_fields = (
        "label",
        "display_name",
    )
    ordering = ("display_name", "created_at")
    list_filter = ("is_visible",)
