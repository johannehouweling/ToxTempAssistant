from django import forms
from toxtempass.models import Investigation, Study, Assay, Question, Section, Answer
from toxtempass.widgets import (
    BootstrapSelectWithButtonsWidget,
)  # Import the custom widget
# Form to submit answers to fixed questions for an assay


class StartingForm(forms.Form):
    investigation = forms.ModelChoiceField(
        queryset=Investigation.objects.all(),
        required=True,
        help_text="Select the Investigation",
        widget=BootstrapSelectWithButtonsWidget(
            button_url_names=[
                "create_investigation",
                "",
                "",
            ],  # URL name for adding new investigation
            button_labels=[
                "Create",
                "Modifiy",
                "Delete",
            ],  # Label for the button,
            button_classes=[
                "d-flex align-items-center btn btn-outline-secondary",
                "d-flex align-items-center btn btn-outline-secondary disabled",  # have to be enabled via js on page
                "d-flex align-items-center btn btn-outline-danger rounded-end disabled",
            ],
        ),
    )
    study = forms.ModelChoiceField(
        queryset=Study.objects.all(),
        required=True,
        widget=BootstrapSelectWithButtonsWidget(
            button_url_names=["create_study", "", ""],  # URL name for adding new study
            button_labels=["Create", "Modifiy", "Delete"],  # Label for the button
            button_classes=[
                "d-flex align-items-center btn btn-outline-secondary",
                "d-flex align-items-center btn btn-outline-secondary disabled",
                "d-flex align-items-center btn btn-outline-danger rounded-end disabled",
            ],
        ),
    )
    assay = forms.ModelChoiceField(
        queryset=Assay.objects.all(),
        required=True,
        widget=BootstrapSelectWithButtonsWidget(
            button_url_names=["create_assay", "", ""],  # URL name for adding new assay
            button_labels=["Create", "Modifiy", "Delete"],  # Label for the button
            button_classes=[
                "d-flex align-items-center btn btn-outline-secondary",
                "d-flex align-items-center btn btn-outline-secondary disabled",
                "d-flex align-items-center btn btn-outline-danger rounded-end disabled",
            ],
        ),
    )


# Form to create an Investigation
class InvestigationForm(forms.ModelForm):
    class Meta:
        model = Investigation
        fields = ["title", "description", "public_release_date"]
        widgets = {
            "public_release_date": forms.DateTimeInput(
                attrs={"type": "datetime-local"}
            ),
        }


# Form to create a Study
class StudyForm(forms.ModelForm):
    class Meta:
        model = Study
        fields = ["investigation", "title", "description"]


# Form to create an Assay
class AssayForm(forms.ModelForm):
    class Meta:
        model = Assay
        fields = ["study", "title", "description"]


class AssayAnswerForm(forms.Form):
    def __init__(self, *args, **kwargs):
        # Get the assay object passed from the view
        self.assay = kwargs.pop("assay")
        super(AssayAnswerForm, self).__init__(*args, **kwargs)

        # Iterate over sections and subsections, adding a form field for each question
        sections = Section.objects.all().prefetch_related("subsections__questions")

        for section in sections:
            for subsection in section.subsections.all():
                for question in subsection.questions.all():
                    # Create a field for each question dynamically
                    field_name = f"question_{question.id}"
                    self.fields[field_name] = forms.CharField(
                        label=question.question_text,
                        required=False,
                        widget=forms.Textarea(attrs={"rows": 2}),
                    )
                    # Add an initial value if an answer already exists for this question and assay
                    try:
                        answer = Answer.objects.get(assay=self.assay, question=question)
                        self.fields[field_name].initial = answer.answer_text
                    except Answer.DoesNotExist:
                        self.fields[field_name].initial = ""

    def save(self):
        # Save each answer for the corresponding assay and question
        for field_name, answer_text in self.cleaned_data.items():
            question_id = field_name.split("_")[1]
            question = Question.objects.get(pk=question_id)

            # Get or create the answer object
            answer, created = Answer.objects.get_or_create(
                assay=self.assay,
                question=question,
                defaults={"answer_text": answer_text},
            )
            # Update the answer if it already exists
            if not created:
                answer.answer_text = answer_text
                answer.save()
