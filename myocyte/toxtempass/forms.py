from django import forms
import logging
from toxtempass.models import Investigation, Study, Assay, Question, Section, Answer
from toxtempass.widgets import (
    BootstrapSelectWithButtonsWidget,
)  # Import the custom widget
from toxtempass.filehandling import get_text_or_imagebytes_from_django_uploaded_file
from langchain_core.messages import HumanMessage, SystemMessage
from toxtempass.llm import ImageMessage
from collections import defaultdict
from toxtempass.llm import (
    chain,
    image_accept_files,
    text_accept_files,
    allowed_mime_types,
)
from toxtempass import config

# Form to submit answers to fixed questions for an assay

logger = logging.getLogger("forms")


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
        accepted_files = ",".join(image_accept_files + text_accept_files)
        # optional file uploaded for updating:
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
                f"Supported formats: {accepted_files}. Max size: {config.max_size_mb} "
                "MB per file."
            ),
        )

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
                    # Set initial value for 'accepted' field only if answer exists
                    if answer:
                        self.fields[accepted_field_name].initial = answer.accepted
                    else:
                        self.fields[accepted_field_name].initial = False
                    ## add earmark for update option
                    earmarked_field_name = f"earmarked_{question.id}"
                    self.fields[earmarked_field_name] = forms.BooleanField(
                        label="GPT Update",
                        required=False,
                    )
                    self.fields[earmarked_field_name].initial = False

    def clean_file_upload(self):
        uploaded_files = self.files.getlist("file_upload")
        allowed_types = allowed_mime_types
        max_size = config.max_size_mb * 1024 * 1024  # 20 MB

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

        # Extract text from uploaded files
        if uploaded_files:
            doc_dict = get_text_or_imagebytes_from_django_uploaded_file(uploaded_files)
            logger.debug(f"Extracted text from {len(uploaded_files)} uploaded files.")
        else:
            doc_dict = {}
            logger.debug("No files uploaded.")

        # Group the fields by question_id
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

        # Extract unique question_ids
        question_ids = questions_data.keys()
        logger.debug(f"Processing {len(question_ids)} questions.")

        # Fetch all relevant questions in a single query
        questions = Question.objects.filter(id__in=question_ids)
        questions_map = {str(q.id): q for q in questions}

        for qid, data in questions_data.items():
            question = questions_map.get(qid)
            if not question:
                logger.error(f"Question with id {qid} does not exist.")
                continue  # Skip processing if question does not exist

            # Get or create the answer object
            answer, created = Answer.objects.get_or_create(
                assay=self.assay,
                question=question,
                defaults={"answer_text": data.get("answer_text", "")},
            )
            if created:
                logger.info(f"Created new Answer for question id {qid}.")

            # Update answer_text if it has changed
            new_text = data.get("answer_text", "")
            if not created and answer.answer_text != new_text:
                answer.answer_text = new_text
                answer.save()
                logger.debug(f"Updated answer_text for question id {qid}.")

            # Update accepted field
            accepted = data.get("accepted", False)
            if answer.accepted != accepted:
                answer.accepted = accepted
                answer.save()
                logger.debug(
                    f"Updated 'accepted' flag for question id {qid} to {accepted}."
                )

            # Update earmarked_for_update field
            earmarked = data.get("earmarked", False)

            if earmarked:
                earmarked_answers.append(answer)
                logger.info(f"Question id {qid} marked for GPT update.")

        # Process earmarked answers
        if earmarked_answers and doc_dict:
            text_dict = {
                key: value
                for (key, value) in doc_dict.items()
                if "text" in value.keys()
            }
            img_dict = {
                key: value
                for (key, value) in doc_dict.items()
                if "bytes" in value.keys()
            }
            for answer in earmarked_answers:
                try:
                    # Prepare the messages for the GPT chain
                    messages = [
                        SystemMessage(content=config.base_prompt),
                        SystemMessage(content=f"ASSAY NAME: {self.assay.title}\n"),
                        SystemMessage(
                            content=f"ASSAY DESCRIPTION: {self.assay.description}\n"
                        ),
                        SystemMessage(
                            content="Below find the context to answer the question:"
                        ),
                    ]
                    # Add text context
                    for filepath, text_data in text_dict.items():
                        messages.append(
                            SystemMessage(
                                content=f"Document: {filepath}\nText:\n{text_data['text']}\n"
                            )
                        )
                    # Add image context
                    for filepath, image_data in img_dict.items():
                        # Assuming image_data['bytes'] is already Base64-encoded
                        messages.append(
                            ImageMessage(
                                content=image_data["bytes"], filename=filepath.name
                            )
                        )
                    # Add the user's question
                    messages.append(HumanMessage(content=answer.question.question_text))

                    logger.debug(f"Invoking GPT for Answer id {answer.id}.")

                    # Serialize messages to dictionaries
                    # serialized_messages = [message.to_dict() for message in messages]

                    # Invoke the chain using the custom function
                    draft_answer = chain.invoke(messages)

                    # Existing documents in answer_documents
                    existing_docs: list[str] = answer.answer_documents or []

                    # New documents from doc_dict.keys()
                    new_docs = [key.name for key in list(doc_dict.keys())]

                    # Combine existing and new documents
                    combined_docs = existing_docs + new_docs

                    # Remove duplicates while preserving order
                    unique_docs_updated = list(dict.fromkeys(combined_docs))

                    # Assign back to answer_documents
                    answer.answer_documents = unique_docs_updated
                    answer.answer_text = draft_answer.content
                    answer.accepted = False
                    answer.save()

                    logger.info(
                        f"Successfully updated Answer id {answer.id} with GPT-generated text."
                    )
                    logger.debug(
                        f"Updated 'answer_documents' for Answer id {answer.id}: {unique_docs_updated}"
                    )

                except Exception as e:
                    # Log the error and optionally handle it (e.g., add to form errors)
                    logger.error(f"Error processing Answer id {answer.id}: {e}")
                    self.add_error(
                        "file_upload",
                        f"Error processing answer for question '{answer.question}': {e}",
                    )
