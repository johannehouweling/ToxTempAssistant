from django.http import HttpRequest
from django.http.response import JsonResponse
from django.template.response import TemplateResponse
from django.db import transaction
import json
from pathlib import Path

from django.urls import reverse
from toxtempass.models import Section, Subsection, Question
from django.shortcuts import get_object_or_404, render, redirect
from django.utils.safestring import mark_safe
from toxtempass.models import Investigation, Study, Assay
from toxtempass.forms import (
    AssayAnswerForm,
    StartingForm,
    InvestigationForm,
    StudyForm,
    AssayForm,
)

from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User


# Custom test function to check if the user is a superuser (admin)
def is_admin(user: User):
    """Check is user is admin. Return True if that's the case."""
    return user.is_superuser


def home(request: HttpRequest):
    return JsonResponse(dict(text="Hello, Flask!"))


def upload(request: HttpRequest):
    if request.method == "POST":
        print(request.files["file"])
        return JsonResponse(dict(message="Success"))
    return TemplateResponse(request, "upload.html", context=dict(style="height:200px"))


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
