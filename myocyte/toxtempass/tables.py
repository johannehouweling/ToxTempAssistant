# ruff: noqa: E501
import django_tables2 as tables
from django.utils.html import format_html
from django.utils.safestring import SafeText

from toxtempass.models import Assay, LLMStatus


class AssayTable(tables.Table):
    investigation = tables.Column(
        accessor="study__investigation__title",
        verbose_name="Investigation",
        orderable=True,
        linkify=False,
        attrs={"th": {"class": "no-link-header"}},
    )
    study = tables.Column(
        accessor="study__title",
        verbose_name="Study",
        orderable=True,
        linkify=False,
        attrs={"th": {"class": "no-link-header"}},
    )
    assay = tables.Column(
        accessor="title",
        verbose_name="Assay",
        orderable=True,
        linkify=False,
        attrs={"th": {"class": "no-link-header"}},
    )
    progress = tables.Column(
        verbose_name="Answers Accepted",
        orderable=False,
        empty_values=(),
    )
    # not_found_answers = tables.Column(
    #     accessor="number_answers_not_found",
    #     verbose_name="Answers Not Found",
    #     orderable=False,
    # )

    # NEW: Add a "View" button column that links to answer_assay_questions for this assay
    action = tables.TemplateColumn(
        template_code="""
        <div class="btn-group" role="group">
            {% if record.status == LLMStatus.SCHEDULED.value %}
                <span class="d-inline-block" data-bs-toggle="tooltip" data-bs-container="body" data-bs-placement="top" title="Refresh the page to check for updates. Usually it doesn't take longer than 5-10 minutes.">
                    <button class="btn btn-sm btn-outline-secondary" disabled style="pointer-events: none;">Scheduled</button>
                </span>
            {% elif record.status == LLMStatus.BUSY.value %}
                <span class="d-inline-block" data-bs-toggle="tooltip" data-bs-container="body" data-bs-placement="top" title="Refresh the page to check for updates. Usually it doesn't take longer than 5-10 minutes.">
                    <button class="btn btn-sm btn-outline-secondary" disabled style="pointer-events: none;">Busy</button>
                </span>
            {% elif record.status == LLMStatus.ERROR.value %}
                <span class="d-inline-block" data-bs-toggle="tooltip" data-bs-container="body" data-bs-placement="top" title="LLM did not succeed. This can be temporary error with the LLM, or an issue with your documents, or too many documents at once.">
                    <button class="btn btn-sm btn-outline-danger" disabled style="pointer-events: none;">Error</button>
                </span>
            {% elif record.status == LLMStatus.DONE.value %}
                <a class="btn btn-sm btn-outline-primary" href="{% url 'answer_assay_questions' record.id %}">View</a>
            {% else %}
                <a class="btn btn-sm btn-outline-primary" href="{% url 'answer_assay_questions' record.id %}">View</a>
            {% endif %}
            <a class="btn btn-sm btn-outline-danger" href="{% url 'delete_assay' record.id %}" onclick="return confirm('Are you sure you want to delete this assay and any associated toxtemp answers? This cannot be undone.');">Delete</a>
        </div>
        """,
        extra_context={"LLMStatus": LLMStatus},
        verbose_name="Action(s)",
        orderable=False,
    )

    def render_progress(self, value, record: Assay) -> SafeText:  # noqa: ANN001
        """Render the progress bar based on the number of answers."""
        total = record.get_n_answers
        accepted = record.get_n_accepted_answers
        if total:
            pct = int((accepted / total) * 100)
        else:
            pct = 0
        return format_html(
            (
                '<div class="progress border"><div class="progress-bar" '
                'role="progressbar" style="width: {}%;" aria-valuenow="{}"'
                'aria-valuemin="0" aria-valuemax="100" data-bs-toggle="tooltip"'
                ' title="{}%"></div></div>'
            ),
            pct,
            pct,
            pct,
        )

    class Meta:
        model = Assay
        # We only need to list the columns we defined above; django-tables2 uses them in this order.
        fields = (
            "investigation",
            "study",
            "assay",
            "progress",
            "action",
        )
        # Use the Bootstrap5 template so it picks up your existing styling
        template_name = "django_tables2/bootstrap5.html"
        attrs = {
            "class": "table table-striped table-hover",
            "wrapper_class": "table-responsive",
        }
        # If you want default ordering, add for example:
        # order_by = "study__investigation__title"
