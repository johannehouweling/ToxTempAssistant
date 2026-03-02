from __future__ import annotations

import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import validate_email
from django.db import models
from django.db.models import Q
from django.utils import timezone
from guardian.shortcuts import assign_perm
from simple_history.models import HistoricalRecords

from toxtempass import config


class LLMStatus(models.TextChoices):
    NONE = "none", "None"
    SCHEDULED = "scheduled", "Scheduled"
    BUSY = "busy", "Busy"
    DONE = "done", "Done"
    ERROR = "error", "Error"


# we are desinging user access that inherits from the parent object.
# That way if Investigation is shared, all the children objects will be shared as well.
class AccessibleModel(models.Model):
    """Abstract base model for objects that may have hierarchical permissions."""

    class Meta:
        abstract = True

    def get_parent(self) -> None:
        """Return the immediate parent object in the hierarchy, if any.

        Override this method in child models that have a parent.
        """
        return None

    def is_accessible_by(self, user: "Person", perm_prefix: str = "view") -> bool:
        """Check if a user has permission to access this object.

        The check is recursive: if the user does not have direct permission on
        this instance, check its parent (if any).

        :param user: The user to check permissions for.
        :param perm_prefix: The permission prefix (e.g., 'view', 'change', 'delete').
        :return: True if the permission is granted on this instance or any parent.
        """
        # Construct the permission codename, e.g., 'view_investigation'
        codename = f"{perm_prefix}_{self._meta.model_name}"
        full_permission = f"{self._meta.app_label}.{codename}"

        # Direct permission check using Django's permission system (or django-guardian)
        if user.has_perm(full_permission, self):
            return True

        # Otherwise, try checking the parent's permissions, if a parent exists
        parent = self.get_parent()
        if parent is not None:
            return parent.is_accessible_by(user, perm_prefix=perm_prefix)

        # No permission found in the chain
        return False


class PersonManager(BaseUserManager):
    def create_user(self, email: str = None, password: str = None, **kwargs) -> "Person":
        """Create user."""
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **kwargs)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, *args, **kwargs) -> "Person":
        """Create superuser."""
        user = self.model(**kwargs)
        user.set_password(kwargs.get("password"))
        user.is_superuser = True
        user.is_staff = True
        user.save(using=self._db)
        return user


class Person(AbstractUser):
    objects = PersonManager()

    # Remove the username field by setting it to None.
    username = None
    email = models.EmailField("email address", unique=True, validators=[validate_email])
    organization = models.CharField(default="", blank=True, max_length=255)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # Add List of fields which you want to be required
    orcid_id = models.CharField(
        max_length=19,
        blank=True,
        unique=True,
        null=True,
        # editable=False,
        help_text=(
            "When the user authenticates with ORCID, "
            "this field will be populated with the ORCID iD."
        ),
    )
    has_accepted_tos = models.BooleanField(
        default=False,
        null=False,
        blank=False,
        verbose_name="I have read, understood and accept the terms of service.",
        help_text=(
            "<button type='button' class='btn btn-sm btn-outline-secondary'"
            " data-bs-toggle='modal' data-bs-target='#termsModal'>"
            "Terms of service</button>"
        ),
    )
    preferences = models.JSONField(
        null=True,
        blank=True,
        help_text="Miscelanous stuff about the user can be stored here",
    )

    @property
    def num_assays(self) -> int:
        """Return the number of assays owned by this user."""
        return sum(
            study.assays.count()
            for investigation in self.investigations.all()
            for study in investigation.studies.all()
        )


# Investigation Model
class Investigation(AccessibleModel):
    owner = models.ForeignKey(
        Person, on_delete=models.PROTECT, related_name="investigations"
    )
    title = models.CharField(max_length=255, blank=False, null=False)
    description = models.TextField(blank=True, default="")
    submission_date = models.DateTimeField(auto_now_add=True)
    public_release_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        """Investigation as string."""
        return self.title

    def save(self, *args, **kwargs) -> None:
        """Save the object and assign object-level permissions to the owner."""
        super().save(*args, **kwargs)
        # Ensure the owner always gets object-level permissions on their own
        # Investigation.
        assign_perm("view_investigation", self.owner, self)
        assign_perm("change_investigation", self.owner, self)
        assign_perm("delete_investigation", self.owner, self)

    def share(self, user: Person) -> None:
        """Grant full access to the specified user for this Investigation."""
        assign_perm("view_investigation", user, self)
        assign_perm("change_investigation", user, self)
        assign_perm("delete_investigation", user, self)

    def get_parent(self) -> None:
        """Return the parent object in the hierarchy, if any."""
        return None


# Study Model
class Study(AccessibleModel):
    investigation = models.ForeignKey(
        Investigation, on_delete=models.CASCADE, related_name="studies"
    )
    title = models.CharField(max_length=255, blank=False, null=False)
    description = models.TextField(blank=True)
    submission_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        """Study as string."""
        return self.title

    def get_parent(self) -> Investigation:
        """Get parent."""
        return self.investigation


# To allow different Versions of ToxTempQuestions
class QuestionSet(models.Model):
    """A named version of the entire question hierarchy."""

    label = models.CharField(max_length=10, unique=True, null=True)  # v1  # noqa: DJ001
    display_name = models.CharField(
        max_length=50,
        default="v2019",
        help_text="A user-friendly name for this question set version, e.g.,"
        " 'ToxTemp Questions v1.0'.",
    )  # noqa: DJ001
    hide_from_display = models.BooleanField(
        default=True,
        help_text="If true, this question set will not be displayed in the UI.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name="questionsets",  # so you can do some_person.questionsets.all()
        null=True,
        blank=False,
        help_text="The user who created this question set version.",
    )
    is_visible = models.BooleanField(
        default=True,
        help_text="Control whether this QuestionSet version is shown to users.",
    )

    class Meta:
        verbose_name = "ToxTemp Question Set Version"
        verbose_name_plural = "ToxTemp Question Set Versions"

    def __str__(self) -> str:
        """Questionset as string."""
        if self.display_name:
            return f"{self.display_name} ({self.created_at.strftime('%b %Y')})"
        elif self.label:
            return f"{self.label} ({self.created_at.strftime('%b %Y')})"
        else:
            return f"Unnamed Question Set ({self.created_at.strftime('%b %Y')})"

    def __expr__(self) -> str:
        """Return a string representation of the QuestionSet for debugging."""
        return f"QuestionSet(label={self.label}, display_name={self.display_name})"

    def is_accessible_by(self, user: Person, perm_prefix: str = "view") -> bool:
        """Can user access this."""
        # Always return True since questions are public.
        return True

    def display(self) -> str:
        """Return a safe HTML representation of the question set."""
        return self.display_name or self.label


# Assay Model
class Assay(AccessibleModel):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="assays")
    title = models.CharField(max_length=255, blank=False, null=False)
    description = models.TextField(blank=False, default="")
    submission_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=10,
        choices=LLMStatus.choices,
        default=LLMStatus.NONE,
    )
    demo_lock = models.BooleanField(
        default=False,
        help_text="Prevent edits so this assay can be used as a read-only demo.",
    )
    demo_template = models.BooleanField(
        default=False,
        help_text="Marks this assay as the master template used to seed demo copies.",
    )
    demo_source = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="demo_copies",
        help_text="Template assay this demo copy originated from.",
    )
    status_context = models.TextField(blank=True, default="")
    question_set = models.ForeignKey(
        QuestionSet,
        on_delete=models.PROTECT,
        related_name="assays",
        blank=True,
        null=True,
        help_text="Which version of the questionnaire this assay is using",
    )

    def __str__(self) -> str:
        """Assay as string."""
        # if unique title within study, just show title otherwise title + submission date
        if Assay.objects.filter(title=self.title).count() == 1:
            return self.title
        return f"{self.title} ({self.submission_date.strftime('%d %b, %Y - %H:%M')})"

    @property
    def get_n_questions(self) -> float:
        """Get number of questions associated with assay."""
        # Count all questions related to this assay
        # Navigate through the study -> sections -> subsections -> questions
        return Question.objects.filter(
            subsection__section__subsections__questions__answers__assay=self
        ).count()

    @property
    def get_n_answers(self) -> float:
        """Get number of answers associtated with assay."""
        # Count all answers related to this assay
        return self.answers.count()

    @property
    def get_n_accepted_answers(self) -> float:
        """Get number of accepted answers associtated with assay."""
        # Count all answers that are marked as accepted
        return self.answers.filter(accepted=True).count()

    def get_parent(self) -> Study:
        """Get Study."""
        return self.study

    def is_accessible_by(self, user: "Person", perm_prefix: str = "view") -> bool:
        """Check if this assay is accessible by the user.

        Checks:
        1. Direct permission on this assay
        2. Workspace membership: user is in a workspace that has this assay shared
        3. Parent permissions (Study -> Investigation)
        """
        codename = f"{perm_prefix}_{self._meta.model_name}"
        full_permission = f"{self._meta.app_label}.{codename}"

        if user.has_perm(full_permission, self):
            return True

        user_workspaces = WorkspaceMember.objects.filter(user=user).values_list("workspace_id", flat=True)
        # If the parent Investigation is shared to any workspace the user is a member of,
        # the assay should be accessible as well.
        from toxtempass.models import WorkspaceInvestigation

        if WorkspaceInvestigation.objects.filter(
            investigation=self.study.investigation, workspace_id__in=user_workspaces
        ).exists():
            return True

        parent = self.get_parent()
        if parent is not None:
            return parent.is_accessible_by(user, perm_prefix=perm_prefix)

        return False

    @property
    def has_feedback(self) -> bool:
        """Check if this assay has feedback."""
        # Check if there are any feedbacks related to this assay
        return hasattr(self, "feedback")

    @property
    def number_answers_not_found(self) -> int:
        """Check if there are any answers not found for this assay."""
        not_found_string = config.not_found_string
        # Get all questions related to this assay
        return Answer.objects.filter(
            assay=self, answer_text__icontains=not_found_string
        ).count()

    @property
    def number_processed_answers(self) -> int:
        """Check if there are any answers processed for this assay."""
        not_found_string = config.not_found_string
        # Get all questions related to this assay
        return (
            Answer.objects.filter(
                assay=self,
            )
            .filter(~Q(Q(answer_text="") | Q(answer_text__isnull=True)))
            .count()
        )

    @property
    def number_answers_found_but_not_accepted(self) -> int:
        """Check if there are any answers found but not yet accepted for this assay."""
        not_found_string = config.not_found_string
        # Get all questions related to this assay
        return (
            Answer.objects.filter(
                assay=self,
                accepted=False,
            )
            .filter(
                ~Q(
                    Q(answer_text__icontains=not_found_string)
                    | Q(answer_text="")
                    | Q(answer_text__isnull=True)
                )
            )
            .count()
        )

    @property
    def is_saved(self) -> bool:
        """Check if saved.

        Returns True if this assay has at least one
        Answer row (i.e. it's been seeded/saved).
        """
        return self.answers.exists()

    @property
    def owner(self) -> Person:
        """Return the owner of this assay (i.e., the owner of the parent investigation)."""
        return self.study.investigation.owner


# New model to track individual user's assay views
class AssayView(models.Model):
    user = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="assay_views")
    assay = models.ForeignKey(Assay, on_delete=models.CASCADE, related_name="views")
    last_viewed = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("user", "assay")

    def __str__(self):
        return f"AssayView(user={self.user.email}, assay={self.assay.title}, last_viewed={self.last_viewed})"


# Section, Subsection, and Question Models (fixed)
class Section(AccessibleModel):
    question_set = models.ForeignKey(
        QuestionSet,
        on_delete=models.CASCADE,
        related_name="sections",
    )
    title = models.CharField(max_length=255)

    def __str__(self):
        """Section as string."""
        return self.title + f"({self.question_set.display()})"

    @property
    def all_answers_accepted(self) -> bool:
        """Check if all answers within this section are marked as accepted."""
        # Get all answers related to all questions in all subsections under this section
        answers = Answer.objects.filter(question__subsection__section=self)

        # Check if there are any answers and if all are accepted
        return answers.exists() and all(answer.accepted for answer in answers)

    def is_accessible_by(self, user: Person, perm_prefix: str = "view") -> bool:
        """Check if this section is accessible by the user."""
        # Always return True since questions are public.
        return True


class Subsection(AccessibleModel):
    section = models.ForeignKey(
        Section, on_delete=models.CASCADE, related_name="subsections"
    )
    title = models.CharField(max_length=255)

    def __str__(self):
        """Return a string representation of the subsection."""
        return self.title + f" ({self.section.question_set.display()})"

    @property
    def all_answers_accepted(self) -> bool:
        """Check if all answers within this subsection are marked as accepted."""
        # Get all answers related to the questions in this subsection
        answers = Answer.objects.filter(question__subsection=self)

        # Check if there are any answers and if all are accepted
        return answers.exists() and all(answer.accepted for answer in answers)

    def is_accessible_by(self, user: Person, perm_prefix: str = "view") -> bool:
        """Check if this subsection is accessible by the user."""
        # Always return True since questions are public.
        return True


class Question(AccessibleModel):
    subsection = models.ForeignKey(
        Subsection, on_delete=models.CASCADE, related_name="questions"
    )
    parent_question = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="subquestions",
        null=True,
        blank=True,
    )
    question_text = models.TextField()
    subsections_for_context = models.ManyToManyField(
        Subsection,
        related_name="context_questions",
        blank=True,
        help_text="List of subsections that provide context for this question.",
    )
    only_subsections_for_context = models.BooleanField(
        default=False,
        help_text=(
            "If true, only answers from the subsections listed in"
            " subsections_for_context will be used to answer this question."
        ),
    )
    answering_round = models.PositiveSmallIntegerField(
        default=1,
        help_text="Which round (1, 2, 3, ...) this question should be answered in.",
    )
    additional_llm_instruction = models.TextField(
        blank=True,
        default="",
        help_text="Extra prompt instructions for the LLM when answering this question.",
    )
    only_additional_llm_instruction = models.BooleanField(
        blank=False,
        null=False,
        default=False,
        help_text="Extra flag to determine if additional llm instruction shall replace all others.",
    )

    answer = models.TextField(blank=True)

    def __str__(self):
        """Return a string representation of the question."""
        return str(self.question_text)

    def is_accessible_by(self, user: Person, perm_prefix: str = "view") -> bool:
        """Check if this question is accessible by the user."""
        # Always return True since questions are public.
        return True


class FileAsset(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        DELETED = "deleted", "Deleted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    bucket = models.CharField(max_length=255, blank=True)
    object_key = models.CharField(max_length=1024, unique=True)

    original_filename = models.CharField(max_length=512)
    content_type = models.CharField(max_length=255, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)

    sha256 = models.CharField(max_length=64, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.AVAILABLE
    )

    uploaded_by = models.ForeignKey(
        Person,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="uploaded_files",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.original_filename


# Answer Model (linked to Assay)
class Answer(AccessibleModel):
    assay = models.ForeignKey(Assay, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="answers",
        blank=False,
        null=False,
    )
    answer_documents = models.JSONField(
        null=True,
        blank=True,
        help_text="Store list of Filenames used to answer this question.",
    )  # change this to VectorField with for a real database.
    files = models.ManyToManyField(
        FileAsset,
        through="AnswerFile",
        related_name="answers",
        blank=True,
        null=True,
        help_text="Actual stored files (only present if user consented to storage).",
    )
    answer_text = models.TextField(blank=True, default="")
    accepted = models.BooleanField(
        null=True, blank=True, help_text="Marked as final answer."
    )
    history = HistoricalRecords()

    def __str__(self):
        """Return a string representation of the answer."""
        return f"Answer to: {self.question} for assay {self.assay}"

    def get_parent(self) -> Assay:
        """Return the parent Assay object."""
        return self.assay

    @property
    def preview_text(self, max_length: int = 75) -> str:
        """Return a preview of the answer text, truncated to max_length."""
        if len(self.answer_text) <= max_length:
            return self.answer_text
        return self.answer_text[:max_length].rsplit(" ", 1)[0] + "..."


class AnswerFile(models.Model):
    answer = models.ForeignKey(Answer, on_delete=models.CASCADE)
    file = models.ForeignKey(FileAsset, on_delete=models.CASCADE)

    # optional per-link metadata, useful later
    label = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["answer", "file"], name="uq_answer_file"),
        ]


class FileDownloadLog(models.Model):
    """Audit log for file downloads (staff/superuser only)."""

    file = models.ForeignKey(
        FileAsset,
        on_delete=models.CASCADE,
        related_name="download_logs",
    )
    user = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name="file_download_logs",
    )
    ip_address = models.GenericIPAddressField(
        null=True, blank=True, help_text="IP address of the download request"
    )
    downloaded_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-downloaded_at"]
        verbose_name = "File Download Log"
        verbose_name_plural = "File Download Logs"

    def __str__(self):
        return f"{self.user.email} downloaded {self.file.original_filename} on {self.downloaded_at.strftime('%Y-%m-%d %H:%M:%S')}"


# Feedback Model
class Feedback(AccessibleModel):
    user = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="feedbacks")
    feedback_text = models.TextField()
    usefulness_rating = models.FloatField(null=True, blank=True)
    submission_date = models.DateTimeField(auto_now_add=True)
    assay = models.OneToOneField(Assay, on_delete=models.CASCADE, related_name="feedback")

    def __str__(self):
        """Represent as String."""
        return f"Feedback from {self.user} on {self.submission_date}"

    def get_parent(self) -> Assay:
        """Return the parent Assay object."""
        return self.assay


class WorkspaceRole(models.TextChoices):
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
    MEMBER = "member", "Member"


class Workspace(AccessibleModel):
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="owned_workspaces"
    )
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def get_parent(self):
        return None
    
    def save(self, *args, **kwargs):
        """Override save to ensure owner is always a member with OWNER role."""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            WorkspaceMember.objects.create(workspace=self, user=self.owner, role=WorkspaceRole.OWNER)


class WorkspaceMember(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="workspace_memberships"
    )
    role = models.CharField(
        max_length=20, choices=WorkspaceRole.choices, default=WorkspaceRole.MEMBER
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("workspace", "user")


class WorkspaceInvestigation(models.Model):
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="shared_investigations"
    )
    investigation = models.ForeignKey(
        Investigation, on_delete=models.CASCADE, related_name="shared_in_workspaces"
    )
    added_by = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("workspace", "investigation")



