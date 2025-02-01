from django.http import FileResponse, HttpRequest
from toxtempass import config
from django.http.response import JsonResponse
from django.db import transaction
import json
import logging

from pathlib import Path
from django.urls import reverse
from langchain_core.messages import HumanMessage, SystemMessage
from toxtempass.filehandling import get_text_or_imagebytes_from_django_uploaded_file
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.utils.text import Truncator
from django.shortcuts import get_object_or_404, render, redirect
from django.utils.safestring import mark_safe
from toxtempass.models import (
    Investigation,
    Study,
    Assay,
    Answer,
    Section,
    Subsection,
    Question,
)
from toxtempass.forms import (
    AssayAnswerForm,
    StartingForm,
    InvestigationForm,
    StudyForm,
    AssayForm,
)
from toxtempass.llm import chain
from toxtempass.export import export_assay_to_file

from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from toxtempass.utilis import calculate_md5_multiplefiles

logger = logging.getLogger("views")


# Custom test function to check if the user is a superuser (admin)
def is_admin(user: User):
    """Check is user is admin. Return True if that's the case."""
    return user.is_superuser


@user_passes_test(is_admin)
def init_db(request: HttpRequest):
    """Populate database from ToxTemp.json."""
    with (Path().cwd() / "ToxTemp.json").open() as f:
        toxtemp = json.load(f)
    if (
        Section.objects.count() == 0
        and Subsection.objects.count() == 0
        and Question.objects.count() == 0
    ):
        with transaction.atomic():  # do all or none
            for sec_dict in toxtemp["sections"]:
                section = Section(title=sec_dict["title"])
                section.save()
                for question_dict in sec_dict["subsections"]:
                    subsection = Subsection(
                        section=section, title=question_dict["title"]
                    )
                    subsection.save()
                    question = Question(
                        subsection=subsection, question_text=question_dict["question"]
                    )
                    question.save()
                    if "subquestions" in question_dict.keys():
                        for subquest_dict in question_dict["subquestions"]:
                            subquestion = Question(
                                subsection=subsection,
                                parent_question=question,
                                question_text=subquest_dict["question"],
                            )
                            subquestion.save()
        return JsonResponse(dict(message="Success"))
    else:
        return JsonResponse(dict(message="Database not empty"))


def start_form_view(request):
    if request.method == "POST":
        form = StartingForm(request.POST)
        if form.is_valid():
            # Process form data here
            assay = form.cleaned_data["assay"]
            # Process the files to generate draft of answers
            files = request.FILES.getlist("files")
            if (
                files and not assay.answers.all()
            ):  # if the user provides files and no answers have been create yet, we can run GPT to seed the answers for whole assay
                # to run gpt we need to cycle over the answers, so we shall first create an empty answer set:
                form_empty_answers = AssayAnswerForm({}, assay=assay)
                if form_empty_answers.is_valid():
                    form_empty_answers.save()
                doc_dict = get_text_or_imagebytes_from_django_uploaded_file(
                    files
                )  # dict of structure {Path(filename.pdf): {'text': 'lorem ipsum'}}
                try:
                    answer_ids = []
                    for answer in assay.answers.all():
                        question = answer.question.question_text
                        draft_answer = chain.invoke(
                            [
                                SystemMessage(content=config.base_prompt),
                                SystemMessage(content=f"ASSAY NAME: {assay.title}\n"),
                                SystemMessage(
                                    content=f"ASSAY DESCRIPTION: {assay.description}\n"
                                ),
                                SystemMessage(
                                    content=f"""Below find the context to answer the question:\n CONTEXT:\n{doc_dict}"""  # text_dict can be optimized (e.g. only text)
                                ),
                                HumanMessage(content=question),
                            ]
                        )
                        answer.answer_text = draft_answer.content
                        answer.answer_documents = [key.name for key in doc_dict.keys()]
                        answer.save()
                        answer_ids.append(answer.id)
                    # store which doc has been used to answer which answers (in this case all of them cause it's the start gpt)
                except Exception as e:
                    print(e)
                    return JsonResponse(
                        {
                            "success": False,
                            "errors": {"__all__": [str(e)]},
                        }
                    )

            # return a success message (currently not displayed - only browser intern) and redirect
            return JsonResponse(
                dict(
                    success=True,
                    errors=form.errors,
                    redirect_url=reverse(  # define where to redirect to on success
                        "answer_assay_questions", kwargs=dict(assay_id=assay.id)
                    ),
                )
            )
        else:
            return JsonResponse(
                {
                    "success": False,
                    "errors": form.errors,
                }
            )
    else:
        form = StartingForm()

    return render(
        request,
        "start.html",
        {
            "form": form,
            # not really needed will send to page itself if no other action specified for from.
            # "action": mark_safe(reverse("start")),
        },
    )


def get_filtered_studies(request: HttpRequest, investigation_id: int):
    """Get the studies of a given investigation"""
    if investigation_id:
        studies = Study.objects.filter(investigation_id=investigation_id).values(
            "id", "title"
        )
        return JsonResponse(list(studies), safe=False)
    return JsonResponse([], safe=False)


def get_filtered_assays(request: HttpRequest, study_id: int):
    """Get the Assays of a given study"""
    if study_id:
        assays = Assay.objects.filter(study_id=study_id).values("id", "title")
        return JsonResponse(list(assays), safe=False)
    return JsonResponse([], safe=False)


def initial_gpt_allowed_for_assay(request: HttpRequest, pk: int) -> JsonResponse:
    """Answers if gpt is allowed in the first go (all answers empty)."""
    if request.method == "POST":
        assay = get_object_or_404(Assay, pk=pk)
        if not assay.answers.all():
            return JsonResponse({"gpt_allowed": True})
        else:
            return JsonResponse({"gpt_allowed": False})


# Create or update Investigation
def create_or_update_investigation(request, pk=None):
    if pk:
        investigation = get_object_or_404(
            Investigation, pk=pk
        )  # Retrieve the existing object for updating
    else:
        investigation = None  # Creating a new object

    if request.method == "POST":
        form = InvestigationForm(request.POST, instance=investigation)
        if form.is_valid():
            form.save()
            return JsonResponse(
                dict(
                    success=True,
                    errors=form.errors,
                    redirect_url=reverse("start"),
                )
            )
        else:
            return JsonResponse(
                {
                    "success": False,
                    "errors": form.errors,
                }
            )
    else:
        form = InvestigationForm(instance=investigation)

    return render(
        request,
        "create.html",
        dict(
            form=form,
            title="Create Investigation",
            back_url=mark_safe(reverse("start")),
        ),
    )


# Delete Investigation via GET
def delete_investigation(request, pk):
    if request.method == "GET":
        investigation = get_object_or_404(Investigation, pk=pk)
        investigation.delete()
        return redirect("start")
    return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)


# Create or update Study
def create_or_update_study(request, pk=None):
    if pk:
        study = get_object_or_404(
            Study, pk=pk
        )  # Retrieve the existing object for updating
    else:
        study = None  # Creating a new object

    if request.method == "POST":
        form = StudyForm(request.POST, instance=study)
        if form.is_valid():
            form.save()
            return JsonResponse(
                dict(
                    success=True,
                    errors=form.errors,
                    redirect_url=reverse("start"),
                )
            )
        else:
            return JsonResponse(
                {
                    "success": False,
                    "errors": form.errors,
                }
            )
    else:
        form = StudyForm(instance=study)

    return render(
        request,
        "create.html",
        dict(form=form, title="Create Study", back_url=mark_safe(reverse("start"))),
    )


# Delete Study via GET
def delete_study(request, pk):
    if request.method == "GET":
        study = get_object_or_404(Study, pk=pk)
        study.delete()
        return redirect("start")
    return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)


# Create or update Assay
def create_or_update_assay(request, pk=None):
    if pk:
        assay = get_object_or_404(
            Assay, pk=pk
        )  # Retrieve the existing object for updating
    else:
        assay = None  # Creating a new object

    if request.method == "POST":
        form = AssayForm(request.POST, instance=assay)
        if form.is_valid():
            form.save()
            return JsonResponse(
                dict(
                    success=True,
                    errors=form.errors,
                    redirect_url=reverse("start"),
                )
            )
        else:
            return JsonResponse(
                {
                    "success": False,
                    "errors": form.errors,
                }
            )
    else:
        form = AssayForm(instance=assay)

    return render(
        request,
        "create.html",
        dict(form=form, title="Create Assay", back_url=mark_safe(reverse("start"))),
    )


# Delete Assay via GET
def delete_assay(request, pk):
    if request.method == "GET":
        assay = get_object_or_404(Assay, pk=pk)
        assay.delete()
        return redirect("start")
    return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)


def answer_assay_questions(request, assay_id):
    assay = get_object_or_404(Assay, pk=assay_id)
    sections = Section.objects.prefetch_related("subsections__questions").all()

    if request.method == "POST":
        form = AssayAnswerForm(request.POST, request.FILES, assay=assay)
        if form.is_valid():
            form.save()
            return JsonResponse(
                dict(
                    success=True,
                    errors=form.errors,
                    redirect_url=reverse(
                        "answer_assay_questions", kwargs=dict(assay_id=assay.pk)
                    ),
                )
            )
        else:
            return JsonResponse(
                {
                    "success": False,
                    "errors": form.errors,
                }
            )
    else:
        form = AssayAnswerForm(assay=assay)
    return render(
        request,
        "answer.html",
        {
            "form": form,
            "assay": assay,
            "sections": sections,
            "back_url": reverse("start"),
            "export_json_url": reverse(
                "export_assay", kwargs=dict(assay_id=assay.id, export_type="json")
            ),
            "export_md_url": reverse(
                "export_assay", kwargs=dict(assay_id=assay.id, export_type="md")
            ),
            "export_pdf_url": reverse(
                "export_assay", kwargs=dict(assay_id=assay.id, export_type="pdf")
            ),
            "export_xml_url": reverse(
                "export_assay", kwargs=dict(assay_id=assay.id, export_type="xml")
            ),
            "export_html_url": reverse(
                "export_assay", kwargs=dict(assay_id=assay.id, export_type="html")
            ),
            "export_docx_url": reverse(
                "export_assay", kwargs=dict(assay_id=assay.id, export_type="docx")
            ),
        },
    )


# Versioning:


def get_version_history(request, assay_id, question_id):
    # Get the answer instance based on assay and question
    answer = get_object_or_404(Answer, assay=assay_id, question=question_id)

    # Get the version history of the answer
    history = answer.history.all()

    # List to store version and corresponding changes
    version_changes = []

    # Iterate through the history and compute differences
    for version in history:
        changes = None
        # Check if there is a previous record
        if version.prev_record:
            # Calculate the differences using diff_against
            changes = version.diff_against(version.prev_record).changes

        # Append the version and its changes to the list
        version_changes.append({"version": version, "changes": changes})
        # change time display // BETTER DONE with a templatetag but would have to look up how to load it
        version_changes[-1]["version"].history_date = naturaltime(
            version_changes[-1]["version"].history_date
        )
        if (
            changes
            and version_changes[-1]["changes"][0].field == "accepted"
            and version_changes[-1]["changes"][0].old == None
        ):
            version_changes.pop(-1)

    # Pass the version changes and the instance to the template
    return render(
        request,
        "answer_extras/version_history_modal_body.html",
        {"version_changes": version_changes, "instance": answer},
    )


# Exporting:


def export_assay(
    request: HttpRequest, assay_id: int, export_type: str
) -> FileResponse | JsonResponse:
    """Export View to ship Files to user per assay."""
    assay = Assay.objects.get(id=assay_id)
    return export_assay_to_file(request, assay, export_type)
