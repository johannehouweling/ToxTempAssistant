from django.contrib import admin

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
    list_display = ("assay", "question", "answer_text")
    search_fields = ("assay__name", "question", "answer_text")


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
