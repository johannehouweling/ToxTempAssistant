from collections.abc import Iterator
import time
import difflib
from django.http import FileResponse, HttpRequest, HttpResponse, HttpResponseRedirect
from toxtempass import config
from django.http.response import JsonResponse
from django.db import transaction
import json
import logging
import re
from django.views import View
from django_q.tasks import async_task
from concurrent.futures import ThreadPoolExecutor, as_completed


from django.core.cache import cache
import uuid
from pathlib import Path
from django.urls import reverse
from langchain_core.messages import HumanMessage, SystemMessage
from toxtempass.filehandling import (
    get_text_or_imagebytes_from_django_uploaded_file,
    split_doc_dict_by_type,
)
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.shortcuts import get_object_or_404, render, redirect
from django.utils.safestring import mark_safe
from toxtempass.models import (
    Investigation,
    LLMStatus,
    Study,
    Assay,
    Answer,
    Section,
    Subsection,
    Question,
    Person,
    Feedback,
)
from django_tables2 import SingleTableView
from django.utils.decorators import method_decorator
from guardian.shortcuts import get_objects_for_user
from toxtempass.tables import AssayTable
from toxtempass.forms import (
    SignupFormOrcid,
    SignupForm,
    AssayAnswerForm,
    StartingForm,
    InvestigationForm,
    StudyForm,
    AssayForm,
    LoginForm,
)
from toxtempass.utilities import get_current_git_hash
from toxtempass.llm import chain
from toxtempass.export import export_assay_to_file

from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
import requests
from myocyte import settings


logger = logging.getLogger("views")


# Login stuff
orcid_id_baseurl = (
    "https://sandbox.orcid.org" if settings.DEBUG else "https://orcid.org"
)


# Custom test function to check if the user is a logged-in
def is_admin(user: User):
    """Check is user is admin. Return True if that's the case."""
    return user.is_superuser


# Custom test function to check if the user is a superuser (admin)
def is_logged_in(user: Person | None):
    """Check is user is admin. Return True if that's the case."""
    return isinstance(user, Person)


def logout_view(request: HttpRequest) -> HttpResponseRedirect:
    """Log out."""
    # Log out the user
    logout(request)
    # Redirect to the login page (you can replace '/login/' with your login URL)
    return redirect(reverse("login"))


class LoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect(reverse("start"))
        form = LoginForm()
        return render(request, "login.html", {"form": form})

    def post(self, request):
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            # if the username is an ORCID id, get the user by the ORCID id
            if "@" not in username:
                try:
                    # Check if the username matches the ORCID pattern: 4x4 digits separated by '-'
                    orcid_pattern = r"^\d{4}-\d{4}-\d{4}-\d{4}$"
                    if re.match(orcid_pattern, username):
                        try:
                            username = Person.objects.get(orcid_id=username).email
                        except Person.DoesNotExist:
                            form.add_error(None, "Invalid credentials.")
                            return JsonResponse(
                                dict(
                                    success=False,
                                    errors=form.errors,
                                )
                            )
                    else:
                        form.add_error(
                            None,
                            "ORCID iD must be in the format '0000-0000-0000-0000'.",
                        )
                        return JsonResponse(
                            dict(
                                success=False,
                                errors=form.errors,
                            )
                        )
                except Person.DoesNotExist:
                    form.add_error(None, "Invalid credentials.")
                    return JsonResponse(
                        dict(
                            success=False,
                            errors=form.errors,
                        )
                    )
            password = form.cleaned_data.get("password")
            user = authenticate(request, username=username, password=password)
            if user:
                login(
                    request, user, backend="django.contrib.auth.backends.ModelBackend"
                )
                return JsonResponse(
                    dict(
                        success=True,
                        errors=form.errors,
                        redirect_url=reverse("start"),
                    )
                )
            else:
                form.add_error(None, "Invalid credentials.")
                return JsonResponse(
                    dict(
                        success=False,
                        errors=form.errors,
                    )
                )
        else:
            return JsonResponse(
                {
                    "success": False,
                    "errors": form.errors,
                }
            )


def signup(request: HttpRequest) -> HttpResponse | JsonResponse:
    """
    Normal signup view. If the user is not logged in, they can sign up.
    """
    if request.user.is_authenticated:
        return redirect(reverse("start"))

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            # Create the user but ensure the ORCID id is set from the session.
            user = form.save(commit=False)
            user.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
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
        # Prefill the form with the ORCID id.
        form = SignupForm()

    return render(request, "signup.html", {"form": form})


# Redirects the user to ORCID’s OAuth authorization endpoint.
def orcid_login(request):
    """ "Redirects the user to ORCID’s OAuth authorization endpoint."""
    # Use your provided ORCID credentials:
    client_id = config._orcid_client_id
    # Build the redirect URI dynamically (ensure it matches the one registered with ORCID)
    redirect_uri = request.build_absolute_uri("/orcid/callback/")

    # The ORCID OAuth URL. According to the docs, for authentication the scope is `/authenticate`
    orcid_authorize_url = (
        f"{orcid_id_baseurl}/oauth/authorize?"  ### NEED TO CHANGE FOR PRODUCTION
        f"client_id={client_id}"
        "&response_type=code"
        "&scope=/authenticate"
        f"&redirect_uri={redirect_uri}"
    )
    return redirect(orcid_authorize_url)


# Handles the callback from ORCID and logs the user in.
def orcid_callback(request):
    """Digest the callback from ORCID and either log the user in or link their ORCID to their account."""
    code = request.GET.get("code")
    if not code:
        return HttpResponse("No code provided.", status=400)

    # Construct the token URL and prepare the token request data.
    token_url = f"{orcid_id_baseurl}/oauth/token"
    client_id = config._orcid_client_id
    client_secret = config._orcid_client_secret
    redirect_uri = request.build_absolute_uri("/orcid/callback/")

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }

    response = requests.post(token_url, data=data)
    if response.status_code != 200:
        return HttpResponse("Failed to authenticate with ORCID.", status=400)

    token_data = response.json()
    orcid_id = token_data.get("orcid")
    if not orcid_id:
        return HttpResponse("No ORCID id found in response.", status=400)

    # If the user is already authenticated, link the ORCID id to the logged-in account.
    if request.user.is_authenticated:
        try:
            # Assume your Person model is linked to the User model.
            # This example retrieves the Person instance via the user.
            person = Person.objects.get(email=request.user.email)
        except Person.DoesNotExist:
            return HttpResponse(
                "Authenticated user does not have a corresponding profile.", status=400
            )

        # Optional: Check if another account already has this ORCID linked.
        if Person.objects.filter(orcid_id=orcid_id).exclude(pk=person.pk).exists():
            return HttpResponse(
                "This ORCID id is already linked to another account. Please go orcid.com and logout to be prompted with anohter authentication prompt.",
                status=400,
            )

        # Save the ORCID id and token data to the user’s profile.
        person.orcid_id = orcid_id
        person.orcid_token_data = token_data  # Ensure your model field supports storing this data (e.g., JSONField)
        person.save()

        # Optionally, you can add a message to confirm successful linking.
        return redirect("start")  # Or wherever you wish to redirect the user.

    # If the user is not authenticated, handle the login/signup flow.
    try:
        # Attempt to log in if an account with this ORCID exists.
        user_profile = Person.objects.get(orcid_id=orcid_id)
        login(
            request, user_profile, backend="django.contrib.auth.backends.ModelBackend"
        )  # Assuming Person has a related user object.
        return redirect("start")
    except Person.DoesNotExist:
        # Save the ORCID id and token data in the session for use in the signup process.
        request.session["orcid_id"] = orcid_id
        request.session["orcid_token_data"] = token_data
        return redirect("orcid_signup")


def orcid_signup(request: HttpRequest) -> HttpResponse | JsonResponse:
    """
    Handles the signup process after the user has authenticated with ORCID.
    """
    orcid_id = request.session.get("orcid_id")
    if not orcid_id:
        return JsonResponse(
            dict(
                success=False,
                errors={"__all__": ["No ORCID id found in session."]},
                redirect_url=reverse("login"),
            )
        )

    if request.method == "POST":
        form = SignupFormOrcid(request.POST)
        if form.is_valid():
            # Create the user but ensure the ORCID id is set from the session.
            user = form.save(commit=False)
            user.orcid_id = orcid_id
            user.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            # Optionally, clear the ORCID data from the session.
            request.session.pop("orcid_id", None)
            request.session.pop("orcid_token_data", None)
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
        # Prefill the form with the ORCID id.
        names = request.session.get("orcid_token_data", {}).get("name").split(" ")
        if len(names) == 2:
            first_name, last_name = names
        elif len(names) < 2:
            first_name, last_name = names[0], ""
        elif len(names) > 2:
            first_name, last_name = names[0], " ".join(names[1:])
        form = SignupFormOrcid(
            initial={
                "orcid_id": orcid_id,
                "first_name": first_name,
                "last_name": last_name,
            }
        )

    return render(request, "signup.html", {"form": form})


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


def process_llm_async(assay_id: int, text_dict: dict[str, dict[str, str]]):
    """Prepare to send the text documents to the LLM to get answer draft using DjangoQ."""
    try:
        assay = Assay.objects.get(id=assay_id)
        answers = list(assay.answers.all())

        # chnage assay status from Scheduled to BUSY
        assay.status = LLMStatus.BUSY
        assay.save()

        # Build shared prompt context
        context_string = "\n\n".join(
            f"--- {Path(fp).name} ---\n{meta['text']}"
            for fp, meta in text_dict.items()
            if "text" in meta
        )

        def generate_answer(answer: Answer):
            question = answer.question.question_text
            messages = [
                SystemMessage(content=config.base_prompt),
                SystemMessage(content=f"ASSAY NAME: {assay.title}"),
                SystemMessage(content=f"ASSAY DESCRIPTION: {assay.description}"),
                SystemMessage(
                    content=f"Below find the context to answer the question:\n{context_string}"
                ),
                HumanMessage(content=question),
            ]
            response = chain.invoke(messages)
            return answer.id, response.content

        with ThreadPoolExecutor(max_workers=config.max_workers_threading) as executor:
            futures = {
                executor.submit(generate_answer, answer): answer for answer in answers
            }

            for idx, future in enumerate(as_completed(futures)):
                try:
                    answer_id, draft = future.result()
                    answer = Answer.objects.get(id=answer_id)
                    answer.answer_text = draft
                    answer.answer_documents = [Path(k).name for k in text_dict.keys()]
                    answer.save()

                except Exception as inner_e:
                    assay.status = LLMStatus.ERROR
                    assay.save()
                    break
        assay.status = LLMStatus.DONE
        assay.save()

    except Exception as e:
        assay.status = LLMStatus.ERROR
        assay.save()
        pass


@method_decorator(user_passes_test(is_logged_in, login_url="/login/"), name="dispatch")
class AssayListView(SingleTableView):
    model = Assay
    table_class = AssayTable
    template_name = "toxtempass/overview.html"
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        accessible_investigations = get_objects_for_user(
            user,
            "toxtempass.view_investigation",
            klass=Investigation,
            use_groups=False,
            any_perm=False,
        )
        return Assay.objects.filter(
            study__investigation__in=accessible_investigations
        ).order_by("-submission_date")


@user_passes_test(is_logged_in, login_url="/login/")
def new_form_view(request: HttpRequest) -> HttpResponse | JsonResponse:
    # ————————————————————————————————
    # GET: render the StartingForm, possibly using ?investigation=?, ?study=?, ?assay=?
    # ————————————————————————————————
    if request.method == "GET":
        # 2) Check for any query‐parameters to prefill the form
        inv_id = request.GET.get("investigation")
        st_id = request.GET.get("study")
        assay_id = request.GET.get("assay")

        initial: dict[str, str] = {}
        if inv_id:
            initial["investigation"] = inv_id
        if st_id:
            initial["study"] = st_id
        if assay_id:
            initial["assay"] = assay_id

        # 3) Instantiate StartingForm with initial=… so those <select> fields stay pre-selected
        form = StartingForm(initial=initial, user=request.user)

        return render(
            request,
            "start.html",
            {"form": form},
        )

    # ————————————————————————————————
    # POST: process the StartingForm and kick off the async task
    # ————————————————————————————————
    if request.method == "POST":
        form = StartingForm(request.POST, user=request.user)

        if form.is_valid():
            assay = form.cleaned_data["assay"]

            # Security check: does the user still have view-permission on this Assay?
            if not assay.is_accessible_by(request.user, perm_prefix="view"):
                from django.core.exceptions import PermissionDenied

                raise PermissionDenied(
                    "You do not have permission to access this assay."
                )

            files = request.FILES.getlist("files")

            # If files were uploaded and there are no existing answers, seed empty answers.
            if files and not assay.answers.all():
                form_empty_answers = AssayAnswerForm({}, assay=assay, user=request.user)
                if form_empty_answers.is_valid():
                    form_empty_answers.save()

                # Split text/images:
                text_dict, _ = split_doc_dict_by_type(
                    get_text_or_imagebytes_from_django_uploaded_file(files)
                )
                try:
                    # Set assay status to busy and hand it off to the async worker
                    assay.status = LLMStatus.BUSY
                    assay.save()

                    # Fire off the asynchronous worker
                    async_task(process_llm_async, assay.id, text_dict)

                except Exception as e:
                    return JsonResponse(
                        {
                            "success": False,
                            "errors": {"__all__": [str(e)]},
                        }
                    )

            # On success, return JSON with a redirect to 'answer_assay_questions'
            return JsonResponse(
                {
                    "success": True,
                    "errors": form.errors,
                    "redirect_url": reverse("start"),
                }
            )

        else:
            # Form invalid → return errors back to the AJAX handler
            return JsonResponse({"success": False, "errors": form.errors})


@user_passes_test(is_logged_in, login_url="/login/")
def get_filtered_studies(request: HttpRequest, investigation_id: int):
    if investigation_id:
        studies = Study.objects.filter(investigation_id=investigation_id).values(
            "id", "title"
        )
        return JsonResponse(list(studies), safe=False)
    return JsonResponse([], safe=False)


@user_passes_test(is_logged_in, login_url="/login/")
def get_filtered_assays(request: HttpRequest, study_id: int):
    if study_id:
        assays = Assay.objects.filter(study_id=study_id).values("id", "title")
        return JsonResponse(list(assays), safe=False)
    return JsonResponse([], safe=False)


@user_passes_test(is_logged_in, login_url="/login/")
def initial_gpt_allowed_for_assay(request: HttpRequest, pk: int) -> JsonResponse:
    if request.method == "POST":
        assay = get_object_or_404(Assay, pk=pk)
        if not assay.is_accessible_by(request.user, perm_prefix="view"):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied("You do not have permission to access this assay.")
        if not assay.answers.all():
            return JsonResponse({"gpt_allowed": True})
        else:
            return JsonResponse({"gpt_allowed": False})


@user_passes_test(is_logged_in, login_url="/login/")
def create_or_update_investigation(request, pk=None):
    if pk:
        investigation = get_object_or_404(Investigation, pk=pk)
        if not investigation.is_accessible_by(request.user, perm_prefix="change"):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied(
                "You do not have permission to modify this investigation."
            )
    else:
        investigation = None
    if request.method == "POST":
        form = InvestigationForm(request.POST, instance=investigation)
        if form.is_valid():
            inv = form.save(commit=False)
            inv.owner = request.user
            inv.save()
            return JsonResponse(
                {
                    "success": True,
                    "errors": form.errors,
                    "redirect_url": reverse("add_new"),
                }
            )
        else:
            return JsonResponse({"success": False, "errors": form.errors})
    else:
        form = InvestigationForm(instance=investigation)
    return render(
        request,
        "create.html",
        {
            "form": form,
            "title": "Create Investigation",
            "back_url": mark_safe(reverse("add_new")),
        },
    )


@user_passes_test(is_logged_in, login_url="/login/")
def delete_investigation(request, pk):
    if request.method == "GET":
        investigation = get_object_or_404(Investigation, pk=pk)
        if not investigation.is_accessible_by(request.user, perm_prefix="delete"):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied(
                "You do not have permission to delete this investigation."
            )
        investigation.delete()
        return redirect("add_new")
    return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)


@user_passes_test(is_logged_in, login_url="/login/")
def create_or_update_study(request, pk=None):
    # If pk is provided, we’re editing an existing Study.
    if pk:
        study = get_object_or_404(Study, pk=pk)
        if not study.is_accessible_by(request.user, perm_prefix="change"):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied("You do not have permission to modify this study.")
    else:
        study = None

    if request.method == "POST":
        form = StudyForm(request.POST, instance=study, user=request.user)
        if form.is_valid():
            saved_study = form.save()
            inv_id = saved_study.investigation_id
            st_id = saved_study.id

            # Redirect back to /start/?investigation=<inv_id>&study=<st_id>
            redirect_url = reverse("add_new")
            redirect_url += f"?investigation={inv_id}&study={st_id}"

            return JsonResponse(
                {
                    "success": True,
                    "errors": form.errors,
                    "redirect_url": redirect_url,
                }
            )
        else:
            return JsonResponse({"success": False, "errors": form.errors})

    else:
        # GET: possibly prefill “investigation” if present in querystring
        inv_id = request.GET.get("investigation")
        initial = {}
        if inv_id:
            initial["investigation"] = inv_id

        form = StudyForm(instance=study, initial=initial, user=request.user)

        back_url = reverse("add_new")
        if inv_id:
            back_url += f"?investigation={inv_id}"

        return render(
            request,
            "create.html",
            {
                "form": form,
                "title": pk and "Modify Study" or "Create Study",
                "back_url": mark_safe(back_url),
            },
        )


@user_passes_test(is_logged_in, login_url="/login/")
def delete_study(request, pk):
    if request.method == "GET":
        study = get_object_or_404(Study, pk=pk)
        if not study.is_accessible_by(request.user, perm_prefix="delete"):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied("You do not have permission to delete this study.")
        study.delete()
        return redirect("add_new")
    return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)


@user_passes_test(is_logged_in, login_url="/login/")
def create_or_update_assay(request, pk=None):
    # If pk is provided, we’re editing an existing Assay.
    if pk:
        assay = get_object_or_404(Assay, pk=pk)
        if not assay.is_accessible_by(request.user, perm_prefix="change"):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied("You do not have permission to modify this assay.")
    else:
        assay = None

    if request.method == "POST":
        form = AssayForm(request.POST, instance=assay, user=request.user)
        if form.is_valid():
            saved_assay = form.save()
            st_id = saved_assay.study_id
            inv_id = saved_assay.study.investigation_id
            assay_id = saved_assay.id

            # Redirect back to /start/?investigation=<inv_id>&study=<st_id>&assay=<assay_id>
            redirect_url = reverse("add_new")
            redirect_url += f"?investigation={inv_id}&study={st_id}&assay={assay_id}"

            return JsonResponse(
                {
                    "success": True,
                    "errors": form.errors,
                    "redirect_url": redirect_url,
                }
            )
        else:
            return JsonResponse({"success": False, "errors": form.errors})

    else:
        # GET: possibly prefill “study” (and indirectly Investigation) from querystring
        inv_id = request.GET.get("investigation")
        st_id = request.GET.get("study")
        initial = {}
        if st_id:
            initial["study"] = st_id
        # (AssayForm only needs the “study” field; the Investigation is inferred.)

        form = AssayForm(instance=assay, initial=initial, user=request.user)

        back_url = reverse("add_new")
        params = []
        if inv_id:
            params.append(f"investigation={inv_id}")
        if st_id:
            params.append(f"study={st_id}")
        if params:
            back_url += "?" + "&".join(params)

        return render(
            request,
            "create.html",
            {
                "form": form,
                "title": pk and "Modify Assay" or "Create Assay",
                "back_url": mark_safe(back_url),
            },
        )


@user_passes_test(is_logged_in, login_url="/login/")
def delete_assay(request, pk):
    if request.method == "GET":
        assay = get_object_or_404(Assay, pk=pk)
        if not assay.is_accessible_by(request.user, perm_prefix="delete"):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied("You do not have permission to delete this assay.")
        assay.delete()
        return redirect("add_new")
    return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)


@user_passes_test(is_logged_in, login_url="/login/")
def answer_assay_questions(request, assay_id):
    assay = get_object_or_404(Assay, pk=assay_id)
    if not assay.is_accessible_by(request.user, perm_prefix="view"):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied("You do not have permission to access this assay.")
    sections = Section.objects.prefetch_related("subsections__questions").all()
    if request.method == "POST":
        form = AssayAnswerForm(
            request.POST, request.FILES, assay=assay, user=request.user
        )
        if form.is_valid():
            form.save()
            return JsonResponse(
                {
                    "success": True,
                    "errors": form.errors,
                    "redirect_url": reverse(
                        "answer_assay_questions", kwargs=dict(assay_id=assay.pk)
                    ),
                }
            )
        else:
            return JsonResponse({"success": False, "errors": form.errors})
    else:
        form = AssayAnswerForm(assay=assay, user=request.user)
    return render(
        request,
        "answer.html",
        {
            "form": form,
            "assay": assay,
            "sections": sections,
            "config": config,
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


@user_passes_test(is_logged_in, login_url="/login/")
def get_version_history(request, assay_id, question_id):
    answer = get_object_or_404(Answer, assay=assay_id, question=question_id)
    if not answer.is_accessible_by(request.user, perm_prefix="view"):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied(
            "You do not have permission to access this answer's version history."
        )
    history = answer.history.all()
    version_changes = []

    class DotDict(dict):
        def __getattr__(self, key):
            try:
                return self[key]
            except KeyError:
                raise AttributeError(f"'DotDict' object has no attribute '{key}'")

        def __setattr__(self, key, value):
            self[key] = value

    def _split_into_words(text: str) -> list:
        return re.findall(r"\S+|\n", text)

    def _get_diff_html(diff: Iterator) -> str:
        html_diff = ""
        for word in diff:
            if word.startswith("-"):
                html_diff += f'<span style="color: red; text-decoration: line-through;">{word[2:]}</span> '
            elif word.startswith("+"):
                html_diff += f'<span style="color: green;">{word[2:]}</span> '
            else:
                html_diff += f"{word[2:]} "
        return html_diff

    for version in history:
        if version.prev_record:
            changes = version.diff_against(version.prev_record).changes
        else:
            changes = version.diff_against(version).changes
        version_changes.append({"version": version, "changes": changes})
        version_changes[-1]["version"].history_date = naturaltime(
            version_changes[-1]["version"].history_date
        )
        last_changes_answer_text = [
            change
            for change in version_changes[-1]["changes"]
            if change.field == "answer_text"
        ]
        if last_changes_answer_text:
            version_changes[-1]["answer_text_changes_html"] = _get_diff_html(
                difflib.ndiff(
                    _split_into_words(last_changes_answer_text[0].old),
                    _split_into_words(last_changes_answer_text[0].new),
                )
            )
        if changes and version_changes[-1]["changes"][0].field == "accepted":
            version_changes.pop(-1)
    return render(
        request,
        "answer_extras/version_history_modal_body.html",
        {
            "version_changes": version_changes,
            "instance": answer,
        },
    )


@user_passes_test(is_logged_in, login_url="/login/")
def export_assay(
    request: HttpRequest, assay_id: int, export_type: str
) -> FileResponse | JsonResponse:
    assay = get_object_or_404(Assay, id=assay_id)
    if not assay.is_accessible_by(request.user, perm_prefix="view"):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied("You do not have permission to export this assay.")
    if assay.has_feedback:
        return export_assay_to_file(request, assay, export_type)
    else:
        return JsonResponse(
            {
                "success": False,
                "errors": {"__all__": ["No feedback has been provided yet."]},
            }
        )


@user_passes_test(is_logged_in, login_url="/login/")
def assay_hasfeedback(request: HttpRequest, assay_id: int) -> JsonResponse:
    assay = get_object_or_404(Assay, id=assay_id)
    return JsonResponse({"success": True, "has_feedback": assay.has_feedback})


@user_passes_test(is_logged_in, login_url="/login/")
def assay_feedback(request: HttpRequest, assay_id: int) -> JsonResponse:
    assay = get_object_or_404(Assay, id=assay_id)
    if request.method == "POST":
        feedback_text = request.POST.get("feedback")
        usefulness_rating = request.POST.get("usefulness_rating")
        if feedback_text and usefulness_rating:
            feedback = Feedback.objects.create(
                feedback_text=feedback_text,
                usefulness_rating=usefulness_rating,
                assay=assay,
                user=request.user,
            )
            assay.feedback = feedback
            assay.save()
            return JsonResponse(
                {
                    "success": True,
                    "errors": {},
                }
            )
        else:
            errors = {}
            if not feedback_text:
                errors["feedbackText"] = ["Feedback cannot be empty."]
            if not usefulness_rating:
                errors["usefulnessRating"] = ["Usefulness rating cannot be empty."]
            return JsonResponse({"success": False, "errors": errors})
