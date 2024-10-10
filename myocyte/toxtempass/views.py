from django.http import HttpRequest
from toxtempass import config
from django.http.response import JsonResponse
from django.db import transaction
import json
from pathlib import Path
from django.urls import reverse
from langchain_core.messages import HumanMessage, SystemMessage
from toxtempass.filehandling import get_text_from_django_uploaded_file
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

from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from toxtempass.utilis import calculate_md5_multiplefiles


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
                doc_dict = get_text_from_django_uploaded_file(
                    files
                )  # dict of structure {Path(filename.pdf): {'text': 'lorem ipsum'}}
                try:
                    for answer in assay.answers.all():
                        question = answer.question.question_text
                        draft_answer = chain.invoke(
                            [
                                SystemMessage(content=config.base_prompt),
                                SystemMessage(
                                    content=f"""Below find the context to answer the question:\n CONTEXT:\n{doc_dict}"""  # text_dict can be optimized (e.g. only text)
                                ),
                                HumanMessage(content=question),
                            ]
                        )
                        answer.answer_text = draft_answer.content
                        answer.save()
                        print(draft_answer)
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


def gpt_allowed_for_assay(request: HttpRequest, pk: int) -> JsonResponse:
    """Answers if gpt is allowed."""
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
        form = AssayAnswerForm(request.POST, assay=assay)
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

    # Pass the version changes and the instance to the template
    return render(
        request,
        "version_history_modal.html",
        {"version_changes": version_changes, "instance": answer},
    )
