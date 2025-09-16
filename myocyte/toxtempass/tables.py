# ruff: noqa: E501
import django_tables2 as tables
from django.utils.html import format_html
from django.utils.safestring import SafeText

from toxtempass.models import Answer, Assay, LLMStatus


class AssayTable(tables.Table):
    new = tables.Column(
        verbose_name="New",
        orderable=False,
        empty_values=(),  # forces render_new to be called
        attrs={
            "th": {"class": "no-link-header d-none d-lg-table-cell"},
            "td": {"class": "align-middle my-0 py-0 text-center d-none d-lg-table-cell"},
        },
    )

    last_changed = tables.DateTimeColumn(
        verbose_name="Last Changed",
        orderable=False,
        linkify=False,
        format="Y-m-d H:i",
        attrs={
            "th": {"class": "no-link-header d-none d-lg-table-cell"},
            "td": {"class": "align-middle d-none d-lg-table-cell"},
        },
    )

    investigation = tables.Column(
        accessor="study__investigation__title",
        verbose_name="Investigation",
        orderable=True,
        linkify=False,
        attrs={
            "th": {"class": "no-link-header d-none d-lg-table-cell "},
            "td": {"class": "align-middle d-none d-lg-table-cell"},
        },
    )
    study = tables.Column(
        accessor="study__title",
        verbose_name="Study",
        orderable=True,
        linkify=False,
        attrs={
            "th": {"class": "no-link-header d-none d-lg-table-cell"},
            "td": {"class": "align-middle d-none d-lg-table-cell"},
        },
    )
    assay = tables.Column(
        accessor="title",
        verbose_name="Assay",
        orderable=True,
        linkify=False,
        attrs={"th": {"class": "no-link-header"}, "td": {"class": "align-middle"}},
    )
    progress = tables.Column(
        verbose_name="Answers Accepted",
        orderable=False,
        empty_values=(),
        attrs={"td": {"class": "align-middle"}},
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
                <button class="btn btn-sm btn-outline-secondary" disabled style="pointer-events: visible;">
                    <span class="d-inline-block" data-bs-toggle="tooltip" data-bs-container="body" data-bs-placement="top" title="Refresh the page to check for updates. Usually it doesn't take longer than 5-10 minutes.">
                        <i class="bi bi-hourglass"></i>
                    </span>
                </button>
            {% elif record.status == LLMStatus.BUSY.value %}
                <button class="btn btn-sm btn-outline-secondary" disabled style="pointer-events: visible;">
                    <span class="d-inline-block" data-bs-toggle="tooltip" data-bs-container="body" data-bs-placement="top" title="Refresh the page to check for updates. Usually it doesn't take longer than 5-10 minutes.">
                        <i class="bi bi-hourglass-split"></i>
                    </span>
                </button>
            {% elif record.status == LLMStatus.ERROR.value %}
                <a class="btn btn-sm btn-outline-danger" href="{% url 'answer_assay_questions' record.id %}">
                    <span class="d-inline-block" data-bs-toggle="tooltip" data-bs-container="body" data-bs-placement="top" title="LLM did not succeed. This can be temporary error with the LLM, or an issue with your documents, or too many documents at once.">
                        <i class="bi bi-bug"></i>
                    </span>
                </a>
            {% elif record.status == LLMStatus.DONE.value %}
                <a class="btn btn-sm btn-outline-primary" href="{% url 'answer_assay_questions' record.id %}">
                    <i class="bi bi-eye"></i>
                </a>
            {% else %}
                <a class="btn btn-sm btn-outline-primary" href="{% url 'answer_assay_questions' record.id %}">
                    <i class="bi bi-eye"></i>
                </a>
            {% endif %}
            <div class="btn-group">
                <button type="button" class="btn btn-sm btn-outline-secondary dropdown-toggle {% if record.status == LLMStatus.Error.value or record.status == LLMStatus.BUSY.value or record.status == LLMStatus.SCHEDULED.value %} disabled {% endif %}" data-bs-toggle="dropdown" aria-expanded="false">
                  <i class="bi bi-file-earmark-arrow-down"></i>
                </button>
                <ul class="dropdown-menu">
                  {% with id=record.id %}
                  <li><a class="dropdown-item" onclick=feedback_export("{{export_json_url}}",{{id}})>JSON</a></li>
                  <li><a class="dropdown-item" onclick=feedback_export("{{export_md_url}}",{{id}})>MD</a></li>
                  <li><a class="dropdown-item" onclick=feedback_export("{{export_pdf_url}}",{{id}})>PDF</a></li>
                  <li><a class="dropdown-item" onclick=feedback_export("{{export_xml_url}}",{{id}})>XML</a></li>
                  <li><a class="dropdown-item" onclick=feedback_export("{{export_docx_url}}",{{id}})>DOCX</a></li>
                  <li><a class="dropdown-item" onclick=feedback_export("{{export_html_url}}",{{id}})>HTML</a></li>
                  {% endwith %}
                </ul>
              </div>
            <a class="btn btn-sm btn-outline-danger" href="{% url 'delete_assay' record.id %}?from=overview" onclick="return confirm('Are you sure you want to delete this assay and any associated toxtemp answers? This cannot be undone.');">
                <i class="bi bi-x-lg"></i>
            </a>
        </div>
        """,
        extra_context={"LLMStatus": LLMStatus},
        verbose_name="Action(s)",
        orderable=False,
    )

    def render_new(self, record: Assay) -> SafeText:
        """Render a 'New' indicator if the assay isn't yet saved."""
        # show a red bullet if the assay isn’t yet saved, else blank
        if not record.is_saved:
            return format_html(
                '<i class="bi fs-3 text-primary bi-dot"></i><span class="visually-hidden">New</span>'
            )
        return ""

    def render_last_changed(self, value, record: Assay) -> SafeText:  # noqa: ANN001
        """Render the last changed date nicely, or 'Never' if None."""
        answers = Answer.objects.filter(assay=record)
        for answer in answers:
            # iterate through all answers and take the most recent history_date as
            # last changed
            date = answer.history.all().order_by("-history_date").first().history_date
            if date and (not value or date > value):
                value = date
        if value:
            return value.strftime("%d %b, %Y")
        else:
            return format_html('<span class="text-muted">Never</span>')

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
            "new",
            "assay",
            "study",
            "investigation",
            "last_changed",
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
