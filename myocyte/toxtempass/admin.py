from django.contrib import admin
from django.http import FileResponse, HttpRequest

from toxtempass.models import (
    Answer,
    Assay,
    Feedback,
    FileAsset,
    Investigation,
    Person,
    Question,
    QuestionSet,
    Section,
    Study,
    Subsection,
)


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
    actions = ["download_assay_files_action"]

    @admin.action(description="Download all files for selected assays")
    def download_assay_files_action(self, request: HttpRequest, queryset):
        """Admin action to download all files for selected assays as ZIP archives."""
        from toxtempass.fileops import download_assay_files
        
        # For simplicity, we'll handle single assay selection
        # Multiple assays would require creating a combined ZIP or multiple downloads
        if queryset.count() != 1:
            self.message_user(
                request,
                "Please select exactly one assay to download files.",
                level="warning",
            )
            return
        
        assay = queryset.first()
        
        try:
            # Generate ZIP file
            zip_buffer = download_assay_files(assay)
            
            # Check if ZIP has any files
            if zip_buffer.getbuffer().nbytes == 0:
                self.message_user(
                    request,
                    f"No files found for assay '{assay.title}'.",
                    level="warning",
                )
                return
            
            # Return ZIP as download
            response = FileResponse(
                zip_buffer,
                as_attachment=True,
                filename=f"assay_{assay.id}_{assay.title[:50]}_files.zip",
            )
            return response
            
        except Exception as exc:
            self.message_user(
                request,
                f"Error downloading files: {exc}",
                level="error",
            )
            return


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


@admin.register(FileAsset)
class FileAssetAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "original_filename",
        "size_bytes",
        "status",
        "uploaded_by",
        "created_at",
        "answer_count",
    )
    list_filter = ("status", "created_at")
    search_fields = ("original_filename", "object_key", "uploaded_by__email")
    readonly_fields = (
        "id",
        "object_key",
        "sha256",
        "created_at",
        "answer_count",
    )
    ordering = ("-created_at",)
    
    @admin.display(description="Linked Answers")
    def answer_count(self, obj):
        """Display count of answers this file is linked to."""
        return obj.answerfile_set.count()
