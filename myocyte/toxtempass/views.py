import difflib
import json
import logging
import re
import time
from collections import defaultdict
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.db import transaction
from django.db.models import QuerySet
from django.http import (
    FileResponse,
    HttpRequest,
    HttpResponse,
    HttpResponseRedirect,
)
from django.http.response import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.views import View
from django_q.tasks import async_task
from django_tables2 import SingleTableView
from guardian.shortcuts import get_objects_for_user
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai import RateLimitError
from tqdm.auto import tqdm

from myocyte import settings
from toxtempass import config
from toxtempass import utilities as beta_util
from toxtempass.demo import seed_demo_assay_for_user
from toxtempass.export import export_assay_to_file
from toxtempass.filehandling import (
    collect_source_documents,
    get_text_or_imagebytes_from_django_uploaded_file,
    split_doc_dict_by_type,
    stringyfy_text_dict,
    summarize_image_entries,
)
from toxtempass.forms import (
    AssayAnswerForm,
    AssayForm,
    InvestigationForm,
    LoginForm,
    SignupForm,
    SignupFormOrcid,
    StartingForm,
    StudyForm,
)
from toxtempass.llm import get_llm
from toxtempass.models import (
    Answer,
    Assay,
    Feedback,
    Investigation,
    LLMStatus,
    Person,
    Question,
    QuestionSet,
    Section,
    Study,
    Subsection,
)
from toxtempass.tables import AssayTable
from toxtempass.tasks import queue_email

logger = logging.getLogger("views")


# Login stuff
orcid_id_baseurl = "https://sandbox.orcid.org" if settings.DEBUG else "https://orcid.org"


# Custom test function to check if the user is a logged-in
def is_admin(user: User) -> bool:
    """Check is user is admin. Return True if that's the case."""
    return user.is_superuser


# Custom test function to check if the user is a superuser (admin)
def is_logged_in(user: Person | None) -> bool:
    """Check if user is logged in as a Person instance."""
    return isinstance(user, Person)


def is_beta_admitted(user: Person | None) -> bool:
    """Check if user is admitted to beta.

    If the user is not logged in, or not admitted, return False.
    Admins (superusers) always bypass this check.
    """
    if not isinstance(user, Person):
        return False
    # Allow superusers to bypass beta admission
    if user.is_superuser:
        return True
    prefs = getattr(user, "preferences", {}) or {}
    return prefs.get("beta_admitted", False)


def logout_view(request: HttpRequest) -> HttpResponseRedirect:
    """Log out the current user and redirect to the login page."""
    logout(request)
    return redirect(reverse("login"))


class LoginView(View):
    """View to handle user login via GET and POST methods."""

    def get(self, request: HttpRequest) -> HttpResponse:
        """Render the login page with the login form if user is not authenticated."""
        if request.user.is_authenticated:
            return redirect(reverse("overview"))
        form = LoginForm()
        return render(request, "login.html", {"form": form})

    def post(self, request: HttpRequest) -> JsonResponse:
        """Process login form submission and authenticate user."""
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            # Check if username looks like an ORCID id and get the email associated
            if "@" not in username:
                orcid_pattern = r"^\d{4}-\d{4}-\d{4}-\d{4}$"
                if re.match(orcid_pattern, username):
                    try:
                        username = Person.objects.get(orcid_id=username).email
                    except Person.DoesNotExist:
                        form.add_error(None, "Invalid credentials.")
                        return JsonResponse({"success": False, "errors": form.errors})
                else:
                    form.add_error(
                        None, "ORCID iD must be in the format '0000-0000-0000-0000'."
                    )
                    return JsonResponse({"success": False, "errors": form.errors})
            password = form.cleaned_data.get("password")
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                return JsonResponse(
                    {
                        "success": True,
                        "errors": form.errors,
                        "redirect_url": reverse("overview"),
                    }
                )
            else:
                form.add_error(None, "Invalid credentials.")
                return JsonResponse({"success": False, "errors": form.errors})
        else:
            return JsonResponse({"success": False, "errors": form.errors})


def signup(request: HttpRequest) -> HttpResponse | JsonResponse:
    """Show normal signup view.

    If the user is not logged in, they can sign up.
    """
    if request.user.is_authenticated:
        return redirect(reverse("overview"))

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            # Create the user but ensure the ORCID id is set from the session.
            user = form.save(commit=False)
            user.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            try:
                seed_demo_assay_for_user(user)
            except Exception:
                logger.exception("Failed to seed demo assay for user %s", user.id)
            # Mark the user as having requested beta and enqueue notification to mntnr.
            try:
                async_task("toxtempass.tasks.send_beta_signup_notification", user.id)
                beta_util.set_beta_requested(user)
            except Exception:
                logger.exception(
                    "Failed to record/queue beta signup notification for user %s",
                    getattr(user, "id", None),
                )
            return JsonResponse(
                dict(
                    success=True,
                    errors=form.errors,
                    redirect_url=reverse("overview"),
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


def approve_beta(request: HttpRequest, token: str) -> HttpResponse:
    """One-click approval endpoint reached from the emailed link.

    Verifies the signed token and, on success, admits the associated Person to
    the beta program. Sends an approval email to the person and returns a
    confirmation page. On failure returns an appropriate HTTP error.
    """
    from toxtempass import utilities as beta_util  # local import to avoid cycles

    payload = beta_util.verify_beta_token(token)
    if not payload or "person_id" not in payload:
        return HttpResponse("Invalid or expired approval token.", status=400)

    person_id = payload["person_id"]
    try:
        person = Person.objects.get(pk=person_id)
    except Person.DoesNotExist:
        return HttpResponse("Person not found for provided token.", status=404)

    try:
        beta_util.set_beta_admitted(person, True, comment="Approved via email link")
    except Exception:
        logger.exception("Failed to set beta admitted flag for person %s", person_id)
        return HttpResponse("Failed to admit user; contact maintainer.", status=500)

    # Send approval email to the user (best-effort; do not fail the request if email fails).
    # Use django-q async_task directly to ensure the job is scheduled consistently.
    try:
        recipient = getattr(person, "email", None)
        if recipient:
            task_id = async_task(
                "toxtempass.tasks.send_email_task",
                to=[recipient],
                subject="[ToxTempAssistant] Beta access approved",
                template_text="toxtempass/email/beta_approved_email.txt",
                template_html="toxtempass/email/beta_approved_email.html",
                context={
                    "person": person,
                    "login_url": request.build_absolute_uri(reverse("login")),
                },
                group="emails",
            )
            logger.info("Queued approval email task %s for person %s", task_id, person_id)
    except Exception:
        logger.exception("Failed to queue approval email for person %s", person_id)

    return render(
        request,
        "toxtempass/email/beta_approved.html",
        {
            "person": person,
            "toggle_beta_users_url": request.build_absolute_uri(
                reverse("admin_beta_user_list")
            ),
        },
    )


def beta_wait(request: HttpRequest) -> HttpResponse:
    """Page shown to users who have requested beta access but are not yet admitted."""
    return render(request, "toxtempass/beta_wait.html")


# --- Admin beta management -----------------------------------------------
@method_decorator(user_passes_test(is_admin, login_url="/login/"), name="dispatch")
class AdminBetaUserListView(SingleTableView):
    """Admin-only SingleTableView listing persons who requested beta access.

    Uses a table class defined in toxtempass.tables.BetaUserTable.
    """

    model = Person
    template_name = "toxtempass/admin/beta_user_list.html"

    def get_table_class(self) -> type:
        """Return the table class used for displaying beta users."""
        # local import to avoid circular imports at module import time
        from toxtempass.tables import BetaUserTable

        return BetaUserTable

    def get_table_data(self) -> list[Person]:
        """Return an iterable of Person objects who requested beta access."""
        qs = Person.objects.all()
        # Filter in Python level to be resilient against JSONField DB differences
        return [p for p in qs if (p.preferences or {}).get("beta_signup")]

    def get_context_data(self, **kwargs) -> dict:
        """Add extra context variables for the template."""
        ctx = super().get_context_data(**kwargs)
        return ctx


@user_passes_test(is_admin, login_url="/login/")
def toggle_beta_admitted(request: HttpRequest) -> HttpResponse:
    """Toggle admit/revoke beta status for a Person.

    Expects POST with:
      - person_id: int
      - admit: "1" or "0" (or "true"/"false")

    Returns JSON: {"success": True, "admitted": bool} or {"success": False, "error": "..."}
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST required"}, status=405)

    person_id = request.POST.get("person_id")
    admit_raw = request.POST.get("admit", "0")
    if not person_id:
        return JsonResponse({"success": False, "error": "person_id required"}, status=400)

    try:
        person = Person.objects.get(pk=int(person_id))
    except (Person.DoesNotExist, ValueError):
        return JsonResponse({"success": False, "error": "Person not found"}, status=404)

    admit = admit_raw.lower() in ("1", "true", "yes", "on")
    try:
        beta_util.set_beta_admitted(
            person, admitted=admit, comment=f"Set by admin {request.user.get_full_name()}"
        )
    except Exception as exc:
        logger.exception("Error toggling beta admitted for person %s: %s", person_id, exc)
        return JsonResponse(
            {"success": False, "error": "Failed to update person"}, status=500
        )

    return JsonResponse({"success": True, "admitted": admit, "person_id": person.id})


# Redirects the user to ORCID’s OAuth authorization endpoint.
def orcid_login(request: HttpRequest) -> HttpResponse:
    """Redirect the user to ORCIDs OAuth authorization endpoint."""
    # Use your provided ORCID credentials:
    client_id = config._orcid_client_id
    # Build the redirect URI dynamically (ensure it matches the one registered with ORCID)
    redirect_uri = request.build_absolute_uri("/orcid/callback/")

    # The ORCID OAuth URL.
    # According to the docs, for authentication the scope is `/authenticate`
    orcid_authorize_url = (
        f"{orcid_id_baseurl}/oauth/authorize?"  ### NEED TO CHANGE FOR PRODUCTION
        f"client_id={client_id}"
        "&response_type=code"
        "&scope=/authenticate"
        f"&redirect_uri={redirect_uri}"
    )
    return redirect(orcid_authorize_url)


# Handles the callback from ORCID and logs the user in.
def orcid_callback(request: HttpRequest) -> HttpResponse | JsonResponse:
    """Digest the callback from ORCID.

    Either log the user in or link their ORCID to their account.
    """
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

    response = requests.post(token_url, data=data, timeout=15)
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
                (
                    "This ORCID id is already linked to another account."
                    " Please go orcid.com and logout to be prompted with"
                    " anohter authentication prompt."
                ),
                status=400,
            )

        # Save the ORCID id and token data to the user’s profile.
        person.orcid_id = orcid_id
        # Ensure your model field supports storing this data (e.g., JSONField)
        person.orcid_token_data = token_data
        person.save()

        # Optionally, you can add a message to confirm successful linking.
        return redirect("overview")  # Or wherever you wish to redirect the user.

    # If the user is not authenticated, handle the login/signup flow.
    try:
        # Attempt to log in if an account with this ORCID exists.
        user_profile = Person.objects.get(orcid_id=orcid_id)
        login(
            request, user_profile, backend="django.contrib.auth.backends.ModelBackend"
        )  # Assuming Person has a related user object.
        return redirect("overview")
    except Person.DoesNotExist:
        # Save the ORCID id and token data in the session for use in the signup process.
        request.session["orcid_id"] = orcid_id
        request.session["orcid_token_data"] = token_data
        return redirect("orcid_signup")


def orcid_signup(request: HttpRequest) -> HttpResponse | JsonResponse:
    """Handle the signup process after the user has authenticated with ORCID."""
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
            # Record beta request and enqueue notification to maintainer.
            try:
                from toxtempass import utilities as beta_util  # type: ignore

                async_task("toxtempass.tasks.send_beta_signup_notification", user.id)
                beta_util.set_beta_requested(user)
            except Exception:
                logger.exception(
                    "Failed to record/queue beta signup notification for ORCID user %s",
                    getattr(user, "id", None),
                )
            # Optionally, clear the ORCID data from the session.
            request.session.pop("orcid_id", None)
            request.session.pop("orcid_token_data", None)
            return JsonResponse(
                dict(
                    success=True,
                    errors=form.errors,
                    redirect_url=reverse("overview"),
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


def create_questionset_from_json(label: str, created_by: Person) -> QuestionSet:
    """Create a QuestionSet from a ToxTemp_<label>.json file."""
    if not label:
        raise ValueError("Version label is required.")

    existing_qs = QuestionSet.objects.filter(label=label).first()
    if existing_qs:
        has_content = Section.objects.filter(question_set=existing_qs).exists() or Question.objects.filter(
            subsection__section__question_set=existing_qs
        ).exists()
        if has_content:
            raise ValueError(f"Version '{label}' already exists")
        # reuse the existing (empty) QuestionSet
        qs = existing_qs
        if qs.created_by is None:
            qs.created_by = created_by
            qs.save(update_fields=["created_by"])
    else:
        qs = QuestionSet.objects.create(label=label, created_by=created_by)

    path = settings.BASE_DIR / f"ToxTemp_{label}.json"
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        raise FileNotFoundError(f"Could not find {path.name}")

    pending_ctx = []  # will hold (Question, [context_title, ...])

    with transaction.atomic():
        # Phase 1: create everything and collect context titles
        for sec in data.get("sections", []):
            section = Section.objects.create(
                question_set=qs,
                title=sec.get("title", "").strip(),
            )

            for subsec in sec.get("subsections", []):
                subsection = Subsection.objects.create(
                    section=section,
                    title=subsec.get("title", "").strip(),
                )

                # MAIN question
                q = Question.objects.create(
                    subsection=subsection,
                    question_text=subsec.get("question", "").strip(),
                    answer=subsec.get("answer", "").strip(),
                    answering_round=subsec.get("answering_round", 1),
                    additional_llm_instruction=subsec.get(
                        "additional_llm_instruction", ""
                    ).strip(),
                    only_additional_llm_instruction=subsec.get(
                        "only_additional_llm_instruction", False
                    ),
                    only_subsections_for_context=subsec.get(
                        "only_subsections_for_context", False
                    ),
                )

                # collect context‑titles for later resolution
                raw_ctx = subsec.get("subsections_for_context_title", [])
                ctx_list = [raw_ctx] if isinstance(raw_ctx, str) else list(raw_ctx)
                if ctx_list:
                    pending_ctx.append((q, ctx_list))

                # SUBquestions
                for sq in subsec.get("subquestions", []):
                    subq = Question.objects.create(
                        subsection=subsection,
                        parent_question=q,
                        question_text=sq.get("question", "").strip(),
                        answer=sq.get("answer", "").strip(),
                        answering_round=sq.get("answering_round", q.answering_round),
                        additional_llm_instruction=sq.get(
                            "additional_llm_instruction", ""
                        ).strip(),
                        only_subsections_for_context=sq.get(
                            "only_subsections_for_context", False
                        ),
                    )

                    raw_ctx_sq = sq.get("subsections_for_context_title", [])
                    ctx_sq = (
                        [raw_ctx_sq] if isinstance(raw_ctx_sq, str) else list(raw_ctx_sq)
                    )
                    if ctx_sq:
                        pending_ctx.append((subq, ctx_sq))

        # Phase 2: resolve all contexts
        for question_obj, titles in pending_ctx:
            # find matching subsections in this set
            subs = Subsection.objects.filter(title__in=titles, section__question_set=qs)
            question_obj.subsections_for_context.set(subs)

    return qs


@user_passes_test(is_admin)
def init_db(request: HttpRequest, label: str) -> JsonResponse:
    """Create a brand-new QuestionSet each time you upload."""
    try:
        qs = create_questionset_from_json(label=label, created_by=request.user)
    except ValueError as exc:
        return JsonResponse({"message": str(exc)}, status=400)
    except FileNotFoundError as exc:
        return JsonResponse({"message": str(exc)}, status=404)
    except json.JSONDecodeError as exc:
        return JsonResponse({"message": f"JSON parse error: {exc}"}, status=400)

    return JsonResponse(
        {
            "message": f"QuestionSet '{qs.label}' successfully created.",
            "version": qs.label,
        }
    )


def add_status_context(
    assay: Assay, msg: str, clear_first: bool = False, is_error: bool = True
) -> None:
    """Add an error message to the assay's status_context field.

    If clear_first is True, overwrite the field; otherwise, append.
    """
    preamble = "Error occured: " if is_error else "Info: "
    new_entry = f"{preamble}: {msg}"
    if clear_first:
        setattr(assay, "status_context", new_entry)
    else:
        prev_context = getattr(assay, "status_context", "") or ""
        setattr(
            assay,
            "status_context",
            prev_context + ("\n" if prev_context else "") + new_entry,
        )


def user_has_seen_tour_page(page: str, user: Person) -> bool:
    """Register onboarding in user preferences per page.

    Returns:
        bool: False, if onboarding has not been seen already (first time)
        bool: True, if onboarding has been shown already

    """
    # Check if user has seen the add_new tour before
    prefs = getattr(user, "preferences", {}) or {}

    # Ensure the 'has_seen_tour' entry is a dict so we can safely call .get on it.
    seen = prefs.get("has_seen_tour")
    if not isinstance(seen, dict):
        seen = {}
        prefs["has_seen_tour"] = seen

    # Determine whether this page has been seen and mark it as seen if not.
    has_seen_tour = bool(seen.get(page, False))
    if not has_seen_tour:
        seen[page] = True

    # if we have visited all tours we no longer have to autostart
    user.preferences = prefs
    user.save()
    return has_seen_tour


llm = get_llm()


def generate_answer(
    ans: Answer,
    full_pdf_context: str,
    assay: Assay,
    chatopenai: ChatOpenAI,
) -> tuple[int, str, str]:
    """Generate an answer for a single Answer instance.
    
    Returns:
        Tuple of (answer_id, answer_text, context_used)
    """
    ## some variables for logging and deadline handling
    # compute a soft deadline based on Django‑Q timeout (90% of it)
    q_timeout = settings.Q_CLUSTER.get("timeout", None)
    if q_timeout:
        deadline = time.time() + q_timeout * 0.9
    else:
        deadline = None

    all_answers = list(
        assay.answers.select_related("question__subsection__section__question_set")
    )
    max_ans_id = max(a.id for a in all_answers) if all_answers else None
    min_ans_id = min(a.id for a in all_answers) if all_answers else None
    delta_ans = max_ans_id - min_ans_id if max_ans_id and min_ans_id else 0

    q = ans.question

    # pick system messages
    if q.only_additional_llm_instruction and q.additional_llm_instruction:
        sys_msgs = [SystemMessage(content=q.additional_llm_instruction)]
    else:
        # base + question‐specific appended
        sys_msgs = [
            SystemMessage(content=config.base_prompt),
            SystemMessage(content=f"ASSAY NAME: {assay.title}"),
            SystemMessage(content=f"ASSAY DESCRIPTION: {assay.description}"),
        ]
        if q.additional_llm_instruction:
            sys_msgs.append(SystemMessage(content=q.additional_llm_instruction))

    # build context string (the context the LLM can use to answer the question)
    if q.only_subsections_for_context and q.subsections_for_context.exists():
        # gather answers to *all* questions in those subsections
        ctx_answers = Answer.objects.filter(
            assay=assay,
            question__subsection__in=q.subsections_for_context.all(),
            answer_text__isnull=False,
        )
        context_blocks = [
            f"--- Q: {ca.question.question_text}\nA: {ca.answer_text}"
            for ca in ctx_answers
        ]
        context_str = "\n\n".join(context_blocks)
    else:
        # use full PDF + *optional* subsection‑scoped answers
        context_str = full_pdf_context
        if q.subsections_for_context.exists():
            ctx_answers = Answer.objects.filter(
                assay=assay,
                question__subsection__in=q.subsections_for_context.all(),
                answer_text__isnull=False,
            )
            extra = "\n\n".join(
                f"--- Q: {ca.question.question_text}\nA: {ca.answer_text}"
                for ca in ctx_answers
            )
            context_str += "\n\n" + extra

    # build messages
    messages = []
    messages.extend(sys_msgs)
    if context_str:
        messages.append(
            SystemMessage(content="Context for this question:\n" + context_str)
        )
    messages.append(HumanMessage(content=q.question_text))

    # retry loop with dynamic waits and soft deadline
    while True:
        if deadline is not None and time.time() > deadline:
            logger.error(
                f"Timed out retrying answer {ans.id} [{max_ans_id - ans.id}"
                " of {delta_ans}] after {q_timeout}s total"
            )
            raise TimeoutError(
                f"Answer {ans.id} [{max_ans_id - ans.id} of {delta_ans}] timed out"
            )

        try:
            resp = chatopenai.invoke(messages)
            return ans.id, (resp.content or ""), context_str

        except RateLimitError as e:
            # parse “try again in Xs” if present
            wait = 5.0
            try:
                msg = e.response.json().get("error", {}).get("message", "")
                m = re.search(r"try again in ([\d\.]+)s", msg)
                if m:
                    wait = float(m.group(1)) + 0.5
            except Exception:
                pass

            logger.warning(
                f"RateLimit hit for answer {ans.id} [{max_ans_id - ans.id} "
                f"of {delta_ans}], retrying in {wait:.1f}s"
            )
            time.sleep(wait)

        except Exception as exc:
            logger.exception(
                f"LLM error for answer {ans.id} [{max_ans_id - ans.id} "
                "of {delta_ans}]: {exc}"
            )
            return ans.id, "", context_str


def process_llm_async(
    assay_id: int,
    doc_dict: dict[str, dict[str, str]] | None = None,
    extract_images: bool = False,
    answer_ids: list[int] | None = None,
    chatopenai: ChatOpenAI | None = None,
    verbose: bool = False,
) -> None:
    """Process llm answer async.

    1) Seed answers in round 1,
    2) save them, then round 2, etc.
    Each question can override or replace instructions,
    and can scope context to specific subsections or use the PDFs.
    """
    try:
        try:
            assay = Assay.objects.get(pk=assay_id)
        except Assay.DoesNotExist:
            logger.info(f"Assay with id {assay_id} does not exist. Exiting task early.")
            return

        if assay.demo_lock:
            logger.info("Assay %s is demo locked; skipping processing.", assay_id)
            return

        assay.status = LLMStatus.BUSY
        assay.save()

        chatopenai = chatopenai or get_llm()

        payload = dict(doc_dict or {})
        if extract_images and payload:
            summarize_image_entries(payload)
        else:
            for key in list(payload.keys()):
                if "encodedbytes" in payload[key]:
                    payload.pop(key)

        source_documents = collect_source_documents(payload)
        text_dict, _ = split_doc_dict_by_type(payload, decode=False)
        full_pdf_context = stringyfy_text_dict(text_dict)

        all_answers = list(
            assay.answers.select_related("question__subsection__section__question_set")
        )
        requested_ids = set(answer_ids or [])
        if requested_ids:
            all_answers = [a for a in all_answers if a.id in requested_ids]
            if not all_answers:
                logger.info(
                    "No matching answers to regenerate for assay %s; marking DONE.",
                    assay_id,
                )
                assay.status = LLMStatus.DONE
                assay.save()
                return
        rounds = sorted({a.question.answering_round for a in all_answers})
        answers_by_round = defaultdict(list)
        for ans in all_answers:
            answers_by_round[ans.question.answering_round].append(ans)

        for rnd in rounds:
            round_answers = answers_by_round[rnd]
            if requested_ids:
                round_answers = [a for a in round_answers if a.id in requested_ids]
                if not round_answers:
                    continue

            logger.info(
                f"Starting answering_round={rnd} with {len(round_answers)} questions"
            )

            # fire off the round in parallel
            with ThreadPoolExecutor(max_workers=config.max_workers_threading) as pool:
                futures = {
                    pool.submit(generate_answer, a, full_pdf_context, assay, chatopenai): a
                    for a in round_answers
                }

                with tqdm(total=len(futures), disable=not verbose, desc="Answers") as pbar:
                    for future in as_completed(futures):
                        try:
                            aid, text, context = future.result()  # optionally: future.result(timeout=...)
                        except TimeoutError as te:
                            logger.error(str(te))
                            continue
                        except Exception as exc:
                            logger.exception(f"Fatal error for answer {futures[future].id}: {exc}")
                            continue
                        finally:
                            pbar.update(1)

                        try:
                            # check assay existence before saving
                            try:
                                assay.refresh_from_db()
                            except Assay.DoesNotExist:
                                logger.info(
                                    f"Assay with id {assay_id} deleted during processing; stopping."
                                )
                                return

                            Answer.objects.filter(pk=aid).update(
                                answer_text=text,
                                context_used=context,
                                answer_documents=source_documents,
                            )
                        except Exception as e:
                            add_status_context(assay, str(e))
                            assay.status = LLMStatus.ERROR
                            assay.save()
                            continue

        assay.status = LLMStatus.DONE
        assay.save()

    except Exception as e:
        logger.exception(f"Fatal error in process_llm_async: {e}")
        # Check if assay exists before updating status and context
        try:
            assay.status = LLMStatus.ERROR
            add_status_context(assay, str(e))
            assay.save()
        except (UnboundLocalError, Assay.DoesNotExist):
            logger.info(
                f"Assay with id {assay_id} does not exist; skipping error status update."
            )


@method_decorator(user_passes_test(is_logged_in, login_url="/login/"), name="dispatch")
class AssayListView(SingleTableView):
    model = Assay
    table_class = AssayTable
    template_name = "toxtempass/overview.html"
    paginate_by = 7

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Gate users who have requested beta access but are not yet admitted.

        Redirect them to the beta waiting page.
        """
        prefs = getattr(request.user, "preferences", {}) or {}
        if prefs.get("beta_signup") and not prefs.get("beta_admitted"):
            return redirect(reverse("beta_wait"))
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self) -> QuerySet[Assay]:
        """Return a queryset of Assays accessible by the user.

        Filtered to only those with a question_set.
        """
        user = self.request.user
        accessible_investigations = get_objects_for_user(
            user,
            "toxtempass.view_investigation",
            klass=Investigation,
            use_groups=False,
            any_perm=False,
        )
        base_qs = Assay.objects.filter(
            study__investigation__in=accessible_investigations,
            question_set__isnull=False,
        )
        real_qs = base_qs.filter(demo_lock=False)
        if real_qs.exists():
            return real_qs.order_by("-submission_date")
        return base_qs.order_by("-submission_date")

    def get_context_data(self, **kwargs) -> dict:
        """Inject context."""
        context = super().get_context_data(**kwargs)
        context["show_tour"] = not user_has_seen_tour_page("overview", self.request.user)
        # Tour management is now handled by JavaScript localStorage
        # No backend flags needed
        return context


@user_passes_test(is_logged_in, login_url="/login/")
@user_passes_test(is_beta_admitted, login_url="/beta/wait/")
def new_form_view(request: HttpRequest) -> HttpResponse | JsonResponse:
    """View to handle the starting form for new ToxTemp."""
    # -------------------------------
    # GET: render the StartingForm, possibly using ?investigation=?, ?study=?, ?assay=?
    # -------------------------------
    if request.method == "GET":
        # 2) Check for any query-parameters to prefill the form
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

        # 3) Instantiate StartingForm with initial=… so those
        # <select> fields stay pre-selected
        form = StartingForm(initial=initial, user=request.user)

        # Check if user has seen the add_new tour before
        show_tour = not user_has_seen_tour_page("add_new", request.user)

        return render(
            request,
            "new.html",
            {"form": form, "action": reverse("add_new"), "show_tour": show_tour},
        )

    # --------------------------------
    # POST: process the StartingForm and kick off the async task
    # --------------------------------
    if request.method == "POST":
        form = StartingForm(request.POST, user=request.user)

        if form.is_valid():
            assay = form.cleaned_data["assay"]
            extract_images = form.cleaned_data.get("extract_images", False)
            overwrite = form.cleaned_data.get("overwrite", False)
            qs = form.cleaned_data["question_set"]
            assay.question_set = qs
            assay.save()
            # Security check: does the user still have view-permission on this Assay?
            if not assay.is_accessible_by(request.user, perm_prefix="view"):
                from django.core.exceptions import PermissionDenied

                raise PermissionDenied("You do not have permission to access this assay.")

            if assay.demo_lock:
                return JsonResponse(
                    {
                        "success": False,
                        "errors": {
                            "__all__": [
                                "Demo assays cannot be regenerated.",
                            ]
                        },
                    },
                    status=400,
                )

            files = request.FILES.getlist("files")
            answers_exist = assay.answers.exists()
            # If files were uploaded and there are no existing answers,
            # seed empty answers.
            if files and not answers_exist:
                form_empty_answers = AssayAnswerForm({}, assay=assay, user=request.user)
                if form_empty_answers.is_valid():
                    form_empty_answers.save()
            # If files were uploaded and either overwrite is True or no existing
            if files and (overwrite or not answers_exist):
                doc_dict = get_text_or_imagebytes_from_django_uploaded_file(
                    files, extract_images=False
                )
                try:
                    # Set assay status to busy and hand it off to the async worker
                    assay.status = LLMStatus.SCHEDULED
                    assay.save()
                    # Fire off the asynchronous worker
                    async_task(
                        process_llm_async,
                        assay.id,
                        doc_dict,
                        extract_images,
                    )

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
                    "redirect_url": reverse("overview"),
                }
            )

        else:
            # Form invalid → return errors back to the AJAX handler
            return JsonResponse({"success": False, "errors": form.errors})


@user_passes_test(is_logged_in, login_url="/login/")
def get_filtered_studies(request: HttpRequest, investigation_id: int) -> JsonResponse:
    """Get filtered Studies based on the Investigation ID."""
    if investigation_id:
        studies = Study.objects.filter(investigation_id=investigation_id).values(
            "id", "title"
        )
        return JsonResponse(list(studies), safe=False)
    return JsonResponse([], safe=False)


@user_passes_test(is_logged_in, login_url="/login/")
def get_filtered_assays(request: HttpRequest, study_id: int) -> JsonResponse:
    """Get filtered Assays based on the Study ID."""
    if study_id:
        assays = Assay.objects.filter(study_id=study_id)
        assays_list = [
            {
                "id": assay.id,
                "title": str(assay),
            }
            for assay in assays
        ]
        return JsonResponse(assays_list, safe=False)
    return JsonResponse([], safe=False)


@user_passes_test(is_logged_in, login_url="/login/")
def initial_gpt_allowed_for_assay(request: HttpRequest, pk: int) -> JsonResponse:
    """Check if GPT is allowed for the given Assay."""
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
def create_or_update_investigation(
    request: HttpRequest, pk: int | None = None
) -> JsonResponse | HttpResponse:
    """Create or update an Investigation."""
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
            "back_url": mark_safe(reverse("add_new")),  # noqa: S308
        },
    )


@user_passes_test(is_logged_in, login_url="/login/")
def delete_investigation(
    request: HttpRequest, pk: int
) -> JsonResponse | HttpResponseRedirect:
    """Delete an investigation if the user has permission."""
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
def create_or_update_study(
    request: HttpRequest, pk: int | None = None
) -> JsonResponse | HttpResponse:
    """Create or update a Study."""
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
                "back_url": mark_safe(back_url),  # noqa: S308
            },
        )


@user_passes_test(is_logged_in, login_url="/login/")
def delete_study(request: HttpRequest, pk: int) -> JsonResponse | HttpResponseRedirect:
    """Delete a study if the user has permission."""
    if request.method == "GET":
        study = get_object_or_404(Study, pk=pk)
        if not study.is_accessible_by(request.user, perm_prefix="delete"):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied("You do not have permission to delete this study.")
        study.delete()
        return redirect("add_new")
    return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)


@user_passes_test(is_logged_in, login_url="/login/")
def create_or_update_assay(
    request: HttpRequest, pk: int | None = None
) -> JsonResponse | HttpResponse:
    """Create or update an Assay."""
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

            # Redirect back to
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
                "back_url": mark_safe(back_url),  # noqa: S308
                "show_tour": not user_has_seen_tour_page("create_assay", request.user),
            },
        )


@user_passes_test(is_logged_in, login_url="/login/")
def delete_assay(request: HttpRequest, pk: int) -> JsonResponse | HttpResponseRedirect:
    """Delete an assay if the user has permission."""
    if request.method == "GET":
        # allows to distuigish between deleting from overview tables
        source_page = request.GET.get("from")
        assay = get_object_or_404(Assay, pk=pk)
        if not assay.is_accessible_by(request.user, perm_prefix="delete"):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied("You do not have permission to delete this assay.")
        if assay.demo_lock:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Demo assays cannot be deleted.",
                },
                status=400,
            )
        assay.delete()
        if source_page == "overview":
            return redirect("overview")
        return redirect("add_new")
    return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)


@user_passes_test(is_logged_in, login_url="/login/")
def answer_assay_questions(
    request: HttpRequest, assay_id: int
) -> JsonResponse | HttpResponse:
    """Render the form to answer questions for a specific assay."""
    from toxtempass.models import AssayView

    assay = get_object_or_404(Assay, pk=assay_id)
    if not assay.is_accessible_by(request.user, perm_prefix="view"):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied("You do not have permission to access this assay.")
    if assay.demo_lock and request.method == "POST":
        return JsonResponse(
            {
                "success": False,
                "errors": {
                    "__all__": [
                        "This assay is locked for demo purposes and cannot be edited.",
                    ]
                },
            },
            status=400,
        )
    # Record that the user has viewed this assay, update or create the AssayView record
    AssayView.objects.update_or_create(
        user=request.user,
        assay=assay,
        defaults={"last_viewed": timezone.now()},
    )
    # only the sections belonging to this assay's QuestionSet
    sections = Section.objects.filter(question_set=assay.question_set).prefetch_related(
        "subsections__questions"
    )
    if request.method == "POST":
        form = AssayAnswerForm(
            request.POST, request.FILES, assay=assay, user=request.user
        )
        if form.is_valid():
            queued = form.save()
            if form.errors:
                return JsonResponse({"success": False, "errors": form.errors})
            redirect_target = (
                reverse("overview")
                if getattr(form, "async_enqueued", False)
                else reverse("answer_assay_questions", kwargs=dict(assay_id=assay.pk))
            )
            return JsonResponse(
                {
                    "success": True,
                    "errors": form.errors,
                    "redirect_url": redirect_target,
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
            "show_tour": not user_has_seen_tour_page(
                "answer_assay_questions", request.user
            ),
            # config is injected via the template context processor
            "back_url": reverse("overview"),
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
def get_version_history(
    request: HttpRequest, assay_id: int, question_id: int
) -> HttpResponse:
    """Fetch the version history of an answer to a question in an assay."""
    answer = get_object_or_404(Answer, assay=assay_id, question=question_id)
    if not answer.is_accessible_by(request.user, perm_prefix="view"):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied(
            "You do not have permission to access this answer's version history."
        )
    history = answer.history.all().order_by("-history_date")
    version_changes = []

    class DotDict(dict):
        def __getattr__(self, key: str):
            try:
                return self[key]
            except KeyError:
                raise AttributeError(f"'DotDict' object has no attribute '{key}'")

        def __setattr__(self, key: str, value: object) -> None:
            self[key] = value

    def _split_into_words(text: str) -> list:
        return re.findall(r"\S+|\n", text)

    def _get_diff_html(diff: Iterator) -> str:
        html_diff = ""
        for word in diff:
            if word.startswith("-"):
                html_diff += (
                    '<span style="color: red; text-decoration: line-through;">'
                    f"{word[2:]}</span> "
                )
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

    # ─── strip out any “versions” with no changes ───
    version_changes = [entry for entry in version_changes if entry["changes"]]

    # If no versions with changes found, add a synthetic "original" version entry to show initial data.
    if not version_changes:
        # Build a minimal synthetic version entry
        answer_text = answer.answer_text or ""

        # Create a DotDict-like object for synthetic version metadata
        class SyntheticVersion(DotDict):
            pass

        synthetic_version = SyntheticVersion()
        synthetic_version.history_date = (
            history.first().history_date if history else "Original"
        )
        synthetic_version.history_user = history.first().history_user if history else None
        synthetic_version.history_id = history.first().history_id if history else None

        # Build changes list for answer_text and answer_documents field
        changes = []
        # change dict format matches what is expected
        # Use attributes to mimic along with "field", "old", and "new"
        changes.append(DotDict(field="answer_text", old="", new=answer_text))
        changes.append(
            DotDict(
                field="answer_documents",
                old="",
                new=", ".join(answer.answer_documents or []),
            )
        )

        # Build HTML for answer_text no diffs because original
        answer_text_html = answer_text.replace("\n", "<br>")

        version_changes.append(
            {
                "version": synthetic_version,
                "changes": changes,
                "answer_text_changes_html": answer_text_html,
            }
        )

    question_set_display_name = str(answer.question.subsection.section.question_set)
    return render(
        request,
        "answer_extras/version_history_modal_body.html",
        {
            "version_changes": version_changes,
            "instance": answer,
            "question_set_display_name": question_set_display_name,
        },
    )


@user_passes_test(is_logged_in, login_url="/login/")
def export_assay(
    request: HttpRequest, assay_id: int, export_type: str
) -> FileResponse | JsonResponse:
    """Export an assay to a file in the specified format."""
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
    """Check if an assay has feedback. Returns a JSON response."""
    assay = get_object_or_404(Assay, id=assay_id)
    return JsonResponse({"success": True, "has_feedback": assay.has_feedback})


@user_passes_test(is_logged_in, login_url="/login/")
def assay_feedback(request: HttpRequest, assay_id: int) -> JsonResponse:
    """Handle feedback submission for an assay."""
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
