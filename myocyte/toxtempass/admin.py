from django.contrib import admin
from toxtempass.models import Assay, Answer, Question, Section, Subsection, Investigation, Study

@admin.register(Investigation)
class InvestigationAdmin(admin.ModelAdmin):
    list_display = ('title',  'submission_date')
    search_fields = ('title',)

@admin.register(Study)
class StudyAdmin(admin.ModelAdmin):
    list_display = ('title', 'investigation', 'submission_date')
    search_fields = ('title', 'investigation__name')

@admin.register(Assay)
class AssayAdmin(admin.ModelAdmin):
    list_display = ('title', 'study', 'submission_date')
    search_fields = ('title', 'study__name')

@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('title',)
    search_fields = ('title',)

@admin.register(Subsection)
class SubsectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'section')
    search_fields = ('title', 'section__title')

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('question_text', 'subsection')
    search_fields = ('question_text', 'subsection__title')

@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('assay', 'question', 'answer_text')
    search_fields = ('assay__name', 'question', 'answer_text')



# Register your models here.
