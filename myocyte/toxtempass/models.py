from django.db import models


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


# Section, Subsection, and Question Models (fixed)
class Section(models.Model):
    title = models.CharField(max_length=255)

    def __str__(self):
        return self.title


class Subsection(models.Model):
    section = models.ForeignKey(
        Section, on_delete=models.CASCADE, related_name="subsections"
    )
    title = models.CharField(max_length=255)

    def __str__(self):
        return self.title


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
    answer_text = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Answer to {self.question} for assay {self.assay}"
