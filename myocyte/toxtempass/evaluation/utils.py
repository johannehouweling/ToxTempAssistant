from django.core.exceptions import ObjectDoesNotExist

from toxtempass.models import QuestionSet


def select_question_set(label: str | None = None) -> QuestionSet:
    """Pick the question set by label or fallback to latest visible."""
    if label:
        try:
            return QuestionSet.objects.get(label=label)
        except ObjectDoesNotExist as exc:
            raise ValueError(f"QuestionSet with label '{label}' not found") from exc

    qs = QuestionSet.objects.filter(is_visible=True).order_by("-created_at").first()
    if not qs:
        raise ValueError("No visible QuestionSet found; cannot run evaluation.")
    return qs