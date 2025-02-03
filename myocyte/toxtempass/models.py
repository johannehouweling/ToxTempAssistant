from django.db import models
from django.contrib.auth.models import AbstractUser
from simple_history.models import HistoricalRecords
from django.contrib.auth.models import BaseUserManager
from django.core.validators import validate_email


class PersonManager(BaseUserManager):
    def create_user(self, email=None, password=None, **kwargs):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **kwargs)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, *args, **kwargs):
        user = self.model(**kwargs)
        user.set_password(kwargs.get("password"))
        user.is_superuser = True
        user.is_staff = True
        user.save(using=self._db)


class Person(AbstractUser):
    # Remove the username field by setting it to None.
    username = None
    email = models.EmailField("email address", unique=True, validators=[validate_email])
    organization = models.CharField(default="", blank=True, null=True, max_length=255)
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
    objects = PersonManager()


# Investigation Model
class Investigation(models.Model):
    title = models.CharField(max_length=255, blank=False, null=False)
    description = models.TextField(blank=True, null=True)
    submission_date = models.DateTimeField(auto_now_add=True)
    public_release_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title


# Study Model
class Study(models.Model):
    investigation = models.ForeignKey(
        Investigation, on_delete=models.CASCADE, related_name="studies"
    )
    title = models.CharField(max_length=255, blank=False, null=False)
    description = models.TextField(blank=True)
    submission_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


# Assay Model
class Assay(models.Model):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="assays")
    title = models.CharField(max_length=255, blank=False, null=False)
    description = models.TextField(blank=True)
    submission_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    @property
    def get_n_questions(self):
        """Get number of questions associated with assay."""
        # Count all questions related to this assay
        # Navigate through the study -> sections -> subsections -> questions
        return Question.objects.filter(
            subsection__section__subsections__questions__answers__assay=self
        ).count()

    @property
    def get_n_answers(self):
        """Get number of answers associtated with assay."""
        # Count all answers related to this assay
        return self.answers.count()

    @property
    def get_n_accepted_answers(self):
        """Get number of accepted answers associtated with assay."""
        # Count all answers that are marked as accepted
        return self.answers.filter(accepted=True).count()


# Section, Subsection, and Question Models (fixed)
class Section(models.Model):
    title = models.CharField(max_length=255)

    def __str__(self):
        return self.title

    @property
    def all_answers_accepted(self) -> bool:
        """
        Check if all answers within this section are marked as accepted.
        """
        # Get all answers related to all questions in all subsections under this section
        answers = Answer.objects.filter(question__subsection__section=self)

        # Check if there are any answers and if all are accepted
        return answers.exists() and all(answer.accepted for answer in answers)


class Subsection(models.Model):
    section = models.ForeignKey(
        Section, on_delete=models.CASCADE, related_name="subsections"
    )
    title = models.CharField(max_length=255)

    def __str__(self):
        return self.title

    @property
    def all_answers_accepted(self) -> bool:
        """
        Check if all answers within this subsection are marked as accepted.
        """
        # Get all answers related to the questions in this subsection
        answers = Answer.objects.filter(question__subsection=self)

        # Check if there are any answers and if all are accepted
        return answers.exists() and all(answer.accepted for answer in answers)


class Question(models.Model):
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
    answer = models.TextField(blank=True)

    def __str__(self):
        return str(self.question_text)


# Answer Model (linked to Assay)
class Answer(models.Model):
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
    )  # chnage this to VectorField with for a real database.
    answer_text = models.TextField(null=True, blank=True)
    accepted = models.BooleanField(
        null=True, blank=True, help_text="Marked as final answer."
    )
    history = HistoricalRecords()

    def __str__(self):
        return f"Answer to: {self.question} for assay {self.assay}"
