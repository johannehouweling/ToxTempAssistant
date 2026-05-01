# ruff: noqa
import django_tables2 as tables
from django.utils.html import escape, format_html
from django.utils.safestring import SafeText, mark_safe

from django.urls import reverse

from toxtempass.models import Answer, Assay, AssayCost, LLMStatus, AssayView, Person
from django.utils.dateparse import parse_datetime
from django.contrib.humanize.templatetags.humanize import naturaltime


class AssayTable(tables.Table):
    new = tables.Column(
        verbose_name="",
        orderable=False,
        empty_values=(),  # causes render function to be called
        attrs={
            "th": {"class": "no-link-header d-none d-lg-table-cell"},
            "td": {"class": "align-middle my-0 py-0 text-center d-none d-lg-table-cell"},
        },
    )

    last_changed = tables.DateTimeColumn(
        verbose_name="Last Changed",
        orderable=False,
        format="%d %b, %Y",
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
            "th": {"class": "no-link-header d-none d-lg-table-cell"},
            "td": {"class": "align-middle d-none d-lg-table-cell text-break"},
        },
    )

    study = tables.Column(
        accessor="study__title",
        verbose_name="Study",
        orderable=True,
        linkify=False,
        attrs={
            "th": {"class": "no-link-header d-none d-lg-table-cell"},
            "td": {"class": "align-middle d-none d-lg-table-cell text-break"},
        },
    )

    assay = tables.Column(
        accessor="title",
        verbose_name="Assay",
        orderable=True,
        linkify=False,
        attrs={
            "th": {"class": "no-link-header"},
            "td": {"class": "align-middle text-break"},
        },
    )

    owner = tables.Column(
        accessor="owner__get_full_name",
        verbose_name="Owner",
        orderable=True,
        linkify=False,
        attrs={
            "th": {"class": "no-link-header d-none d-lg-table-cell"},
            "td": {"class": "align-middle d-none d-lg-table-cell"},
        },
    )

    cost = tables.Column(
        verbose_name="Cost (est.)",
        orderable=False,
        empty_values=(),
        attrs={
            "th": {"class": "no-link-header d-none d-lg-table-cell"},
            "td": {"class": "align-middle d-none d-lg-table-cell text-center"},
        },
    )

    progress = tables.Column(
        verbose_name="Answers Accepted",
        orderable=False,
        empty_values=(),
        attrs={"td": {"class": "align-middle"}},
    )

    action = tables.TemplateColumn(
        template_code="""
        <div class="btn-group" role="group">
            {% if record.status == LLMStatus.SCHEDULED.value %}
                <div class="btn-group" role="group" data-assay-id="{{ record.id }}" data-assay-status="{{ record.status }}" data-bs-toggle="tooltip" title="Processing scheduled. Refresh the page to see updates.">
                    <button class="btn btn-sm btn-outline-secondary" disabled>
                        <span class="d-flex">
                            <i class="bi bi-hourglass"></i>
                            <span class="ms-1 d-none d-lg-inline">Sched.</span>
                        </span>
                    </button>
                </div>
            {% elif record.status == LLMStatus.BUSY.value %}
                <div class="btn-group" role="group" data-assay-id="{{ record.id }}" data-assay-status="{{ record.status }}" data-bs-toggle="tooltip" title="Processing ongoing ({{record.number_processed_answers}}/{{record.get_n_answers}}). Refresh the page to see updates.">
                    <button class="btn btn-sm btn-outline-secondary" disabled>
                            <span class="spinner-grow spinner-grow-sm" aria-hidden="true"></span>
                            <span role="status" class="d-lg-inline d-none">Busy</span>
                    </button>
                </div>
            {% elif record.status == LLMStatus.ERROR.value %}
                <a class="btn btn-sm btn-outline-danger" data-assay-id="{{ record.id }}" data-assay-status="{{ record.status }}" href="{% url 'answer_assay_questions' record.id %}">
                    <span data-bs-toggle="tooltip" title="Processing failed">
                        <i class="bi bi-bug"></i>
                        <span class="ms-1 d-none d-lg-inline">Error</span>
                    </span>
                </a>
            {% else %}
                <a class="btn btn-sm btn-outline-primary" data-assay-id="{{ record.id }}" data-assay-status="{{ record.status }}" href="{% url 'answer_assay_questions' record.id %}">
                    <i class="bi bi-eye"></i>
                    <span class="ms-1 d-none d-lg-inline">View</span>
                </a>
            {% endif %}
            <div class="btn-group">
                <button type="button" class="btn btn-sm btn-outline-secondary dropdown-toggle {% if record.status == LLMStatus.ERROR.value or record.status == LLMStatus.BUSY.value or record.status == LLMStatus.SCHEDULED.value %}disabled{% endif %}" data-bs-toggle="dropdown">
                    <i class="bi bi-file-earmark-arrow-down"></i>
                    <span class="ms-1 d-none d-lg-inline">Export</span>
                </button>
                <ul class="dropdown-menu">
                    <li><a class="dropdown-item" href="{% url 'export_assay' assay_id=record.id export_type='json' %}">JSON</a></li>
                    <li><a class="dropdown-item" href="{% url 'export_assay' assay_id=record.id export_type='md' %}">MD</a></li>
                    <li><a class="dropdown-item" href="{% url 'export_assay' assay_id=record.id export_type='pdf' %}">PDF</a></li>
                    <li><a class="dropdown-item" href="{% url 'export_assay' assay_id=record.id export_type='xml' %}">XML</a></li>
                    <li><a class="dropdown-item" href="{% url 'export_assay' assay_id=record.id export_type='docx' %}">DOCX</a></li>
                    <li><a class="dropdown-item" href="{% url 'export_assay' assay_id=record.id export_type='html' %}">HTML</a></li>
                    <li><a class="dropdown-item" href="{% url 'export_assay' assay_id=record.id export_type='tex' %}">TEX</a></li>
                </ul>
            </div>
            <a class="btn btn-sm btn-outline-danger js-delete-link"
               href="#"
               role="button"
               data-delete-url="{% url 'delete_assay' record.id %}?from=overview"
               data-confirm-msg="Are you sure you want to delete this assay and associated data? This action cannot be undone.">
                <i class="bi bi-x-lg"></i>
                <span class="ms-1 d-none d-lg-inline">Delete</span>
            </a>
        </div>
        """,
        extra_context={"LLMStatus": LLMStatus},
        verbose_name="Actions",
        orderable=False,
        attrs={"th": {"class": "no-link-header"}, "td": {"class": "align-middle"}},
    )

    def render_investigation(self, record) -> SafeText:
        """If shared investigation, add share icon with tooltip."""
        if record.study.investigation.shared_in_workspaces.exists():
            return format_html(
                """
            <div class="position-relative d-inline-flex"> {}
                <span type="button" data-bs-toggle="offcanvas" href="#offcanvasUser"> 
                    <span class="position-absolute top-50 start-100 translate-middle-y p-2 " data-bs-toggle="tooltip" data-bs-placement="top" title="Shared in workspace: {}">
                        <span class="bi pill px-1 rounded bg-secondary-subtle bi-share"></span>
                    </span>
                </span>
            </div>""",
                record.study.investigation.title,
                ", ".join(
                    record.study.investigation.shared_in_workspaces
                    .filter(workspace__memberships__user_id=self.context["request"].user.id)
                    .values_list("workspace__name", flat=True)
                ),
            )
        return escape(record.study.investigation.title)

    def render_new(self, record) -> SafeText:
        """Render 'New' indicator if assay has not been viewed by current user."""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return ""
        viewed = AssayView.objects.filter(assay=record, user=request.user).exists()
        if not viewed:
            return mark_safe(
                '<i class="bi bi-dot text-primary fs-3"></i><span class="visually-hidden">New</span>'
            )
        return ""

    def render_last_changed(self, value, record) -> SafeText:
        """Render last changed date of assay from Answer history."""
        answers = Answer.objects.filter(assay=record)
        latest = None
        for answer in answers:
            hist = answer.history.order_by("-history_date").first()
            if hist and (latest is None or hist.history_date > latest):
                latest = hist.history_date
        if latest:
            return naturaltime(latest)
        else:
            return mark_safe('<span class="text-muted">Never</span>')

    def render_progress(self, value, record: Assay) -> SafeText:  # noqa: ANN001
        """Render the progress bar based on the number of answers."""
        total = record.get_n_answers
        accepted = record.get_n_accepted_answers
        draft_but_not_accepted = record.number_answers_found_but_not_accepted
        if total:
            pct_accepted = int((accepted / total) * 100)
            pct_draft_but_not_accepted = int((draft_but_not_accepted / total) * 100)
        else:
            pct_accepted = 0
            pct_draft_but_not_accepted = 0
        answers_accepted_string = "answer" if pct_accepted == 1 else "answers"
        draft_but_not_accepted_string = (
            "answer" if pct_draft_but_not_accepted == 1 else "answers"
        )
        return format_html(
            """
                <div class="progress border bg-white">
                <div class="progress-bar bg-primary"
                    role="progressbar"
                    style="width: {pct_a}%;"
                    aria-valuenow="{pct_a}"
                    aria-valuemin="0"
                    aria-valuemax="100"
                    data-bs-toggle="tooltip"
                    title="{acc} {acc_str} accepted">
                </div>

                <div class="progress-bar-striped bg-primary opacity-50"
                    role="progressbar"
                    style="width: {pct_d}%;"
                    aria-valuenow="{pct_d}"
                    aria-valuemin="0"
                    aria-valuemax="100"
                    data-bs-toggle="tooltip"
                    title="{draft} unaccepted draft {draft_str}">
                </div>
                </div>
            """,
            pct_a=pct_accepted,
            acc=accepted,
            acc_str=answers_accepted_string,
            pct_d=pct_draft_but_not_accepted,
            draft=draft_but_not_accepted,
            draft_str=draft_but_not_accepted_string,
        )

    def render_cost(self, value, record: Assay) -> SafeText:
        """Render admin-only estimated LLM cost with Bootstrap5 popover breakdown."""
        cost_rows = AssayCost.objects.filter(assay=record)
        if not cost_rows.exists():
            return mark_safe('<span class="text-muted">—</span>')

        total = sum(
            (r.total_cost or 0) for r in cost_rows
        )

        # Build popover HTML content with per-model breakdown
        breakdown_rows = []
        for r in cost_rows:
            row_total = r.total_cost
            cost_str = f"${row_total:.4f}" if row_total is not None else "no pricing data"
            in_str = f"{r.input_tokens:,}" if r.input_tokens else "0"
            out_str = f"{r.output_tokens:,}" if r.output_tokens else "0"
            breakdown_rows.append(
                f"<tr><td class='pe-2'><code>{escape(r.model_key)}</code></td>"
                f"<td class='pe-2'>{escape(r.model_id)}</td>"
                f"<td class='pe-2'>{in_str}&nbsp;in</td>"
                f"<td class='pe-2'>{out_str}&nbsp;out</td>"
                f"<td><b>{cost_str}</b></td></tr>"
            )
        popover_content = (
            '<table class="table table-sm mb-0">'
            "<thead><tr>"
            "<th>Key</th><th>Model</th><th>Input tokens</th>"
            "<th>Output tokens</th><th>Est. cost</th>"
            "</tr></thead><tbody>"
            + "".join(breakdown_rows)
            + "</tbody></table>"
        )

        total_str = f"${total:.4f}" if any(r.total_cost is not None for r in cost_rows) else "—"

        return format_html(
            '<span tabindex="0" role="button"'
            ' data-bs-toggle="popover"'
            ' data-bs-trigger="focus"'
            ' data-bs-placement="left"'
            ' data-bs-html="true"'
            ' data-bs-title="Cost breakdown"'
            ' data-bs-content="{content}"'
            ' class="badge bg-secondary text-decoration-underline cursor-pointer"'
            ' style="cursor:pointer">'
            "{total}"
            "</span>",
            content=popover_content,
            total=total_str,
        )

    def before_render(self, request):
        """Override get_table to conditionally exclude 'confidential' column."""
        if request.user.is_superuser:
            self.columns.show("owner")
            self.columns.show("cost")
        else:
            self.columns.hide("owner")
            self.columns.hide("cost")

    class Meta:
        model = Assay
        fields = (
            "new",
            "assay",
            "study",
            "investigation",
            "last_changed",
            "progress",
            "owner",
            "cost",
            "action",
        )
        # Use the Bootstrap5 template so it picks up your existing styling
        # template_name = "django_tables2/bootstrap5.html" THis is now a global setting
        attrs = {
            "class": "table table-striped table-hover",
            "wrapper_class": "table-responsive",
        }
        # If you want default ordering, add for example:
        # order_by = "study__investigation__title"


class BetaUserTable(tables.Table):
    name = tables.Column(accessor="get_full_name", verbose_name="Name", linkify=False)
    email = tables.Column(accessor="email", verbose_name="Email", linkify=False)
    requested_at = tables.Column(
        verbose_name="Requested at", orderable=False, empty_values=()
    )
    admitted = tables.Column(verbose_name="Admitted", orderable=False, empty_values=())
    num_assays = tables.Column(
        accessor="num_assays", verbose_name="# Assays", orderable=False
    )
    comment = tables.Column(
        accessor="preferences__beta_comment",
        verbose_name="Comment",
        orderable=False,
        empty_values=(),
    )
    action = tables.TemplateColumn(
        template_code="""
        <button class="btn btn-sm toggle-admit-btn {% if record.preferences and record.preferences.beta_admitted %}btn-danger{% else %}btn-success{% endif %}"
                data-person-id="{{ record.id }}"
                data-admit="{% if record.preferences and record.preferences.beta_admitted %}0{% else %}1{% endif %}">
            {% if record.preferences and record.preferences.beta_admitted %}Revoke{% else %}Admit{% endif %}
        </button>
        """,
        verbose_name="Action",
        orderable=False,
        attrs={"td": {"class": "align-middle"}, "th": {"class": "no-link-header"}},
    )

    def render_requested_at(self, value, record: Person) -> SafeText:  # noqa: ANN001
        prefs = record.preferences or {}
        ts = prefs.get("beta_requested_at")
        if not ts:
            return "-"
        # Try to parse ISO datetime stored in preferences; fall back to raw string.
        dt = parse_datetime(ts)
        if dt:
            try:
                return naturaltime(dt)
            except Exception:
                return str(ts)
        return str(ts)

    def render_admitted(self, value, record: Person) -> SafeText:  # noqa: ANN001
        prefs = record.preferences or {}
        return "Yes" if prefs.get("beta_admitted") else "No"

    class Meta:
        model = Person
        fields = (
            "name",
            "email",
            "requested_at",
            "num_assays",
            "comment",
            "admitted",
            "action",
        )
        template_name = "django_tables2/bootstrap5.html"
        attrs = {
            "class": "table table-striped table-hover",
            "wrapper_class": "table-responsive",
        }
