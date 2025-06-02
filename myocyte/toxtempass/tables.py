import django_tables2 as tables
from toxtempass.models import Assay
from django.utils.html import format_html
from toxtempass.models import LLMStatus


class AssayTable(tables.Table):
    investigation = tables.Column(
        accessor="study.investigation.title",
        verbose_name="Investigation",
        orderable=True,
        linkify=False,  # set to True or a URL pattern name if you want the cell to be clickable
    )
    study = tables.Column(
        accessor="study.title",
        verbose_name="Study",
        orderable=True,
        linkify=False,
    )
    assay = tables.Column(
        accessor="title",
        verbose_name="Assay",
        orderable=True,
        linkify=False,
    )
    progress = tables.Column(
        verbose_name="Progress",
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
        {% if record.status == LLMStatus.SCHEDULED %}
            <button class="btn btn-sm btn-outline-secondary" disabled>Queued</button>
        {% elif record.status == LLMStatus.BUSY %}
            <button class="btn btn-sm btn-outline-secondary" disabled>Busy</button>
        {% elif record.status == LLMStatus.ERROR %}
            <button class="btn btn-sm btn-outline-danger" disabled>Error</button>
        {% elif record.status == LLMStatus.DONE %}
            <a class="btn btn-sm btn-outline-primary" href="{% url 'answer_assay_questions' record.id %}">View</a>
        {% else %}
            <a class="btn btn-sm btn-outline-primary" href="{% url 'answer_assay_questions' record.id %}">View</a>
        {% endif %}
        """,
        extra_context={"LLMStatus": LLMStatus},
        verbose_name="Action",
        orderable=False,
    )

    def render_progress(self, value, record):
        total = record.get_n_answers
        accepted = record.get_n_accepted_answers
        if total:
            pct = int((accepted / total) * 100)
        else:
            pct = 0
        return format_html(
            '<div class="progress border"><div class="progress-bar" role="progressbar" style="width: {}%;" aria-valuenow="{}" aria-valuemin="0" aria-valuemax="100" data-bs-toggle="tooltip" title="{}%"></div></div>',
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
