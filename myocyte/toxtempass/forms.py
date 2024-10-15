from django import forms
from toxtempass.models import Investigation, Study, Assay, Question, Section, Answer
from toxtempass.widgets import (
    BootstrapSelectWithButtonsWidget,
)  # Import the custom widget
# Form to submit answers to fixed questions for an assay


class MultipleFileInput(forms.ClearableFileInput):
    """FileInput for multiple files."""

    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        return result


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
    files = forms.FileField(
        widget=MultipleFileInput(attrs={"multiple": True}),
        required=False,
        help_text="Upload documents as context for the LLM to draft answers. Only allowed during first draft.",
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
                        widget=forms.Textarea(
                            attrs={
                                "rows": 2,
                                "oninput": 'this.style.height = "";this.style.height = this.scrollHeight + 3 + "px"',
                            }
                        ),
                    )
                    # Add an initial value if an answer already exists for this question and assay
                    try:
                        answer = Answer.objects.get(assay=self.assay, question=question)
                        self.fields[field_name].initial = answer.answer_text
                    except Answer.DoesNotExist:
                        self.fields[field_name].initial = ""
                        answer = None

                    ## add accepted option
                    accepted_field_name = f"accepted_{question.id}"
                    self.fields[accepted_field_name] = forms.BooleanField(
                        label="Accepted",
                        required=False,
                    )
                    # Set initial value for 'accepted' field only if answer exists
                    if answer:
                        self.fields[accepted_field_name].initial = answer.accepted
                    else:
                        self.fields[accepted_field_name].initial = False

    def save(self):
        # Save each answer for the corresponding assay and question
        for field_name, value in self.cleaned_data.items():
            # Extract the question ID from the field name (assuming the format is 'question_<id>')
            field_name_split = field_name.split("_")
            if "question" in field_name_split:
                question_id = field_name_split[1]
                question = Question.objects.get(pk=question_id)

                # Get or create the answer object for this assay and question
                answer, created = Answer.objects.get_or_create(
                    assay=self.assay,
                    question=question,
                    defaults={
                        "answer_text": value
                    },  # This only sets the text if the answer is being created
                )

                # Only update if the answer_text is different from the existing one
                if not created and answer.answer_text != value:
                    answer.answer_text = value
                    answer.save()
            if "accepted" in field_name_split:
                accepted_id = field_name_split[1]
                question = Question.objects.get(pk=accepted_id)

                # Get or create the answer object for this assay and question
                answer, created = Answer.objects.get_or_create(
                    assay=self.assay,
                    question=question,
                    defaults={
                        "accepted": False
                    },  # This only sets the text if the answer is being created
                )

                # Only update if the answer_text is different from the existing one
                if not created and answer.accepted != value:
                    answer.accepted = value
                    answer.save()
