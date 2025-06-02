import base64
from pathlib import Path
from django import forms
import logging
from django.core.exceptions import PermissionDenied
from guardian.shortcuts import get_objects_for_user
from toxtempass.models import Investigation, Study, Assay, Question, Section, Answer
from toxtempass.widgets import (
    BootstrapSelectWithButtonsWidget,
)  # Import the custom widget
from django.forms import widgets
from toxtempass.filehandling import get_text_or_imagebytes_from_django_uploaded_file, split_doc_dict_by_type
from toxtempass.llm import ImageMessage
from langchain_core.messages import SystemMessage
from collections import defaultdict
from toxtempass.llm import (
    chain,
    image_accept_files,
    text_accept_files,
    allowed_mime_types,
)
from toxtempass import config
from django.contrib.auth.forms import UserCreationForm
from toxtempass.models import Person

# Form to submit answers to fixed questions for an assay

logger = logging.getLogger("forms")


class LoginForm(forms.Form):
    username = forms.CharField(
        label="Email or ORCID iD",
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "Enter email or ORCID iD"}),
    )
    password = forms.CharField(
        label="Password",
        required=True,
        widget=forms.PasswordInput(attrs={"placeholder": "Enter password"}),
    )

    def clean(self):
        """Clean"""
        cleaned_data = super().clean()
        username = cleaned_data.get("username")
        if username:
            username = cleaned_data.get("username").lower()
            cleaned_data["username"] = username
        return cleaned_data


class SignupFormOrcid(UserCreationForm):
    class Meta:
        model = Person
        # Include fields you want the user to fill in.
        # Since your model only adds an 'orcid_id' to AbstractUser,
        # you might include username, email, first_name, last_name, etc.
        fields = (
            "email",
            "first_name",
            "last_name",
            "organization",
            "orcid_id",
            "has_accepted_tos",
        )
        # if we come through Orcid this is already known and should not be changed
        widgets = {
            "orcid_id": widgets.TextInput(attrs={"disabled": True}),
        }

    def clean(self):
        """Clean"""
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        if email:
            email = cleaned_data.get("email").lower()
            cleaned_data["email"] = email  # make sure we only store lower case emails
        if email and Person.objects.filter(email=email).exists():
            self.add_error("email", "This email address is already in use.")
        # enforce that the user has accepted the terms of service
        has_accepted_tos = cleaned_data.get("has_accepted_tos")
        if not has_accepted_tos:
            self.add_error(
                "has_accepted_tos",
                "You must accept the terms of service to continue.",
            )
        return cleaned_data


class SignupForm(SignupFormOrcid):
    class Meta(SignupFormOrcid.Meta):
        fields = tuple(
            field for field in SignupFormOrcid.Meta.fields if field != "orcid_id"
        )


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
        queryset=Investigation.objects.none(),  # default to none until filtered
        required=True,
        help_text="Select the Investigation or create a new one.",
        widget=BootstrapSelectWithButtonsWidget(
            button_url_names=["create_investigation", "", ""],
            button_labels=["Create", "Modifiy", "Delete"],
            button_classes=[
                "d-flex align-items-center btn btn-outline-secondary",
                "d-flex align-items-center btn btn-outline-secondary disabled",
                "d-flex align-items-center btn btn-outline-danger rounded-end disabled",
            ],
        ),
    )
    study = forms.ModelChoiceField(
        queryset=Study.objects.none(),
        required=True,
        help_text="Select the Study or create a new one.",

        widget=BootstrapSelectWithButtonsWidget(
            button_url_names=["create_study", "", ""],
            button_labels=["Create", "Modifiy", "Delete"],
            button_classes=[
                "d-flex align-items-center btn btn-outline-secondary",
                "d-flex align-items-center btn btn-outline-secondary disabled",
                "d-flex align-items-center btn btn-outline-danger rounded-end disabled",
            ],
        ),
    )
    assay = forms.ModelChoiceField(
        queryset=Assay.objects.none(),
        required=True,
        help_text="Select the Assay or create a new one.",
        widget=BootstrapSelectWithButtonsWidget(
            button_url_names=["create_assay", "", ""],
            button_labels=["Create", "Modifiy", "Delete"],
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

    def __init__(self, *args, user=None, **kwargs):
        """
        Expects a 'user' keyword argument to filter the querysets.
        """
        super().__init__(*args, **kwargs)
        if user is not None:
            # Filter Investigations to those for which the user has view access.
            accessible_investigations = get_objects_for_user(
                user, "toxtempass.view_investigation"
            )
            self.fields["investigation"].queryset = accessible_investigations
            # For Studies, allow only those whose Investigation is accessible.
            self.fields["study"].queryset = Study.objects.filter(
                investigation__in=accessible_investigations
            )
            # For Assays, allow only those whose Study's Investigation is accessible.
            self.fields["assay"].queryset = Assay.objects.filter(
                study__investigation__in=accessible_investigations
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

    def __init__(self, *args, user=None, **kwargs):
        """
        Filter the 'investigation' field to include only those Investigations
        that the user is permitted to view.
        """
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["investigation"].queryset = get_objects_for_user(
                user, "toxtempass.view_investigation"
            )


# Form to create an Assay


class AssayForm(forms.ModelForm):
    class Meta:
        model = Assay
        fields = ["study", "title", "description"]

    def __init__(self, *args, user=None, **kwargs):
        """
        Filter the 'study' field based on accessible Investigations.
        """
        super().__init__(*args, **kwargs)
        if user is not None:
            accessible_investigations = get_objects_for_user(
                user, "toxtempass.view_investigation"
            )
            self.fields["study"].queryset = Study.objects.filter(
                investigation__in=accessible_investigations
            )


class AssayAnswerForm(forms.Form):
    def __init__(self, *args, **kwargs):
        """
        Expects both 'assay' and optionally 'user' to be provided.
        The user is checked against the assay's access permissions.
        """
        self.assay = kwargs.pop("assay")
        user = kwargs.pop("user", None)
        if user is not None and not self.assay.is_accessible_by(user):
            raise PermissionDenied("You do not have access to this assay.")
        super().__init__(*args, **kwargs)

        accepted_files = ",".join(image_accept_files + text_accept_files)
        self.fields["file_upload"] = MultipleFileField(
            widget=MultipleFileInput(
                attrs={
                    "multiple": True,
                    "id": "fileUpload",
                    "accept": accepted_files,
                }
            ),
            required=False,
            help_text=(
                "Context documents for update of selected answers. "
                f"Supported formats: {accepted_files}. Max size: {config.max_size_mb} MB per file."
            ),
        )

        # Dynamically add fields for each question (assuming Sections, Subsections, and Questions are public)
        sections = Section.objects.all().prefetch_related("subsections__questions")
        for section in sections:
            for subsection in section.subsections.all():
                for question in subsection.questions.all():
                    # Create a text field for the answer.
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
                    # Prepopulate if an Answer already exists.
                    try:
                        answer = Answer.objects.get(assay=self.assay, question=question)
                        self.fields[field_name].initial = answer.answer_text
                    except Answer.DoesNotExist:
                        self.fields[field_name].initial = ""
                        answer = None

                    # Add a checkbox for marking the answer as accepted.
                    accepted_field_name = f"accepted_{question.id}"
                    self.fields[accepted_field_name] = forms.BooleanField(
                        widget=forms.CheckboxInput(
                            attrs={
                                "class": "form-check-input",
                                "role": "switch",
                                "type": "checkbox",
                            }
                        ),
                        label="Accepted",
                        required=False,
                    )
                    self.fields[accepted_field_name].initial = (
                        answer.accepted if answer else False
                    )

                    # Add a checkbox for earmarking the answer for GPT update.
                    earmarked_field_name = f"earmarked_{question.id}"
                    self.fields[earmarked_field_name] = forms.BooleanField(
                        label="GPT Update",
                        required=False,
                    )
                    self.fields[earmarked_field_name].initial = False

    def clean_file_upload(self):
        uploaded_files = self.files.getlist("file_upload")
        allowed_types = allowed_mime_types
        max_size = config.max_size_mb * 1024 * 1024  # convert MB to bytes

        for file in uploaded_files:
            if file.content_type not in allowed_types:
                raise forms.ValidationError(
                    f"Unsupported file type: {file.content_type}"
                )
            if file.size > max_size:
                raise forms.ValidationError(
                    f"File size exceeds the limit of {max_size / (1024 * 1024)} MB"
                )
        return uploaded_files

    def save(self):
        """
        Saves the form data:
          - Saves answers and their flags.
          - Processes uploaded files.
          - Invokes GPT for earmarked answers synchronously.
        """
        earmarked_answers = []
        uploaded_files = self.cleaned_data.get("file_upload", [])

        # Extract text from uploaded files.
        if uploaded_files:
            text_dict, img_dict = split_doc_dict_by_type(get_text_or_imagebytes_from_django_uploaded_file(uploaded_files))
            logger.debug(f"Extracted text from {len(uploaded_files)} uploaded files.")
        else:
            text_dict = {}
            img_dict = {}
            logger.debug("No files uploaded.")

        # Group fields by question ID.
        questions_data = defaultdict(dict)
        for field_name, value in self.cleaned_data.items():
            if field_name.startswith("question_"):
                qid = field_name.split("_")[1]
                questions_data[qid]["answer_text"] = value
            elif field_name.startswith("accepted_"):
                qid = field_name.split("_")[1]
                questions_data[qid]["accepted"] = value
            elif field_name.startswith("earmarked_"):
                qid = field_name.split("_")[1]
                questions_data[qid]["earmarked"] = value

        question_ids = questions_data.keys()
        logger.debug(f"Processing {len(question_ids)} questions.")

        questions = Question.objects.filter(id__in=question_ids)
        questions_map = {str(q.id): q for q in questions}

        for qid, data in questions_data.items():
            question = questions_map.get(qid)
            if not question:
                logger.error(f"Question with id {qid} does not exist.")
                continue

            answer, created = Answer.objects.get_or_create(
                assay=self.assay,
                question=question,
                defaults={"answer_text": data.get("answer_text", "")},
            )
            if not created and answer.answer_text != data.get("answer_text", ""):
                answer.answer_text = data.get("answer_text", "")
                answer.save()
                logger.debug(f"Updated answer_text for question id {qid}.")

            if answer.accepted != data.get("accepted", False):
                answer.accepted = data.get("accepted", False)
                answer.save()
                logger.debug(f"Updated accepted flag for question id {qid}.")

            if data.get("earmarked", False):
                earmarked_answers.append(answer)
                logger.info(f"Question id {qid} marked for GPT update.")

        # earmarked for renewed answer generation
        if earmarked_answers and (text_dict or img_dict):
            text_dict = {}
            img_dict = {}

            for answer in earmarked_answers:
                try:
                    messages = []
                    # Add all image messages
                    for filename, img_bytes in img_dict.items():
                        messages.append(ImageMessage(content=img_bytes, filename=filename))
                    # Add all text messages
                    if text_dict:
                        messages.append(SystemMessage(
                                    content=f"Below find the context to answer the question:\n CONTEXT:\n{text_dict}"
                                )),
                    # (Add additional messages as needed based on your requirements.)
                    draft_answer = chain.invoke(messages)
                    existing_docs = answer.answer_documents or []
                    new_docs = [Path(key).name for key in list(text_dict.keys())+list(img_dict.keys())]
                    combined_docs = existing_docs + new_docs
                    unique_docs_updated = list(dict.fromkeys(combined_docs))
                    answer.answer_documents = unique_docs_updated
                    answer.answer_text = draft_answer.content
                    answer.accepted = False
                    answer.save()
                    logger.info(
                        f"Successfully updated Answer id {answer.id} with GPT-generated text."
                    )
                except Exception as e:
                    logger.error(f"Error processing Answer id {answer.id}: {e}")
                    self.add_error(
                        "file_upload",
                        f"Error processing answer for question '{answer.question}': {e}",
                    )
