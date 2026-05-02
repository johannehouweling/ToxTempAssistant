import logging
from io import BytesIO

from django import forms
from django.contrib import admin, messages
from django.http import FileResponse, HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from toxtempass.azure_registry import (
    all_model_choices,
    badge_color,
    badge_icon,
    badge_short,
    endpoint_choices,
    get_registry,
)
from toxtempass.filehandling import download_assay_files_as_zip
from toxtempass.models import (
    Answer,
    Assay,
    AssayCost,
    Feedback,
    Investigation,
    LLMConfig,
    Person,
    Question,
    QuestionSet,
    Section,
    Study,
    Subsection,
    FileAsset
)

logger = logging.getLogger(__name__)


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "email", "orcid_id")
    search_fields = ("first_name", "last_name", "email", "orcid_id")


@admin.register(Investigation)
class InvestigationAdmin(admin.ModelAdmin):
    list_display = ("title", "submission_date")
    search_fields = ("title",)


@admin.register(Study)
class StudyAdmin(admin.ModelAdmin):
    list_display = ("title", "investigation", "submission_date")
    search_fields = ("title", "investigation__name")


@admin.register(Assay)
class AssayAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "study",
        "submission_date",
        "feedback__feedback_text",
        "number_answers_not_found",
    )
    search_fields = ("title", "study__name")
    actions = ["download_assay_files"]

    def download_assay_files(self, request, queryset):
        """Custom admin action to download files associated with selected assays."""
        if not request.user.is_staff or not request.user.is_superuser:
            self.message_user(request, "You do not have permission to download files.", level="error")
            return

        if queryset.count() != 1:
            self.message_user(request, "Please select exactly one assay.", level="error")
            return

        assay = queryset.first()
        try:
            zip_bytes, filename = download_assay_files_as_zip(assay, request.user, request)

            if not zip_bytes:
                self.message_user(request, "No files found for this assay.", level="warning")
                return

            # Wrap zip_bytes in BytesIO for FileResponse
            response = FileResponse(BytesIO(zip_bytes), content_type="application/zip")
            response["Content-Disposition"] = f'attachment; filename="{filename}"'

            logger.info(
                "User %s downloaded files for assay %s",
                request.user.email,
                assay.id,
            )

            return response

        except Exception as exc:
            logger.exception("Failed to download files for assay %s: %s", assay.id, exc)
            self.message_user(
                request,
                f"Failed to download files: {str(exc)}",
                level="error",
            )

    download_assay_files.short_description = "Download assay files as ZIP"


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("title",)
    search_fields = ("title",)


@admin.register(Subsection)
class SubsectionAdmin(admin.ModelAdmin):
    list_display = ("title", "section")
    search_fields = ("title", "section__title")


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "question_text", "subsection", "answer")
    search_fields = ("question_text", "subsection__title")


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ("assay", "question", "preview_text", "accepted")
    search_fields = ("assay__name", "question", "accepted")

@admin.register(FileAsset)
class FileAssetAdmin(admin.ModelAdmin):
    list_display = ("id", "original_filename", "uploaded_by")

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("assay", "user", "feedback_text", "usefulness_rating")
    search_fields = ("assay__name", "user")


@admin.register(QuestionSet)
class QuestionSetAdmin(admin.ModelAdmin):
    list_display = ("id", "label", "display_name", "created_at", "is_visible")
    search_fields = (
        "label",
        "display_name",
    )
    ordering = ("display_name", "created_at")
    list_filter = ("is_visible",)


# ── LLM Configuration (singleton) ─────────────────────────────────────────────

def _render_deployments_table(
    *,
    registry,
    results: dict,
    current_default: str,
    current_allowed: set,
    cfg_pk,
):
    """Render the unified deployments picker (button + table + legend + banner).

    Used by both ``DeploymentTableWidget.render`` (interactive) and the admin's
    ``deployments_panel`` readonly fallback.
    """
    from datetime import datetime

    from django.contrib.humanize.templatetags.humanize import naturaltime

    run_url = (
        reverse("admin:toxtempass_llmconfig_run_health_check", args=[cfg_pk])
        if cfg_pk else None
    )

    last_ts_raw = next(
        (r.get("checked_at", "") for r in results.values() if r.get("checked_at")),
        "",
    )
    if last_ts_raw:
        try:
            dt = datetime.fromisoformat(last_ts_raw)
        except (ValueError, TypeError):
            dt = None
        human = naturaltime(dt) if dt else last_ts_raw
        ts_text = format_html(
            '<span style="color:#666;font-size:90%;margin-left:14px" title="{}">'
            "Last checked {}</span>",
            last_ts_raw, human,
        )
    else:
        ts_text = mark_safe(
            '<span style="color:#888;font-style:italic;'
            'font-size:90%;margin-left:14px">Never checked</span>'
        )
    btn_bar = format_html(
        '<div style="display:flex;align-items:center;margin:18px 0 14px 0">'
        '<a class="button" href="{}" '
        'style="background:#417690;color:#fff;padding:8px 16px;'
        "text-decoration:none;border-radius:3px;font-weight:500\">"
        "⟳ Run health check now</a>{}</div>",
        run_url, ts_text,
    ) if run_url else ""

    retired_but_allowed: list[str] = []
    rows = []
    for ep in registry:
        for m in ep.models:
            key = f"{ep.index}:{m.tag}"
            r = results.get(key) or {}

            if not r:
                status_html = mark_safe('<span style="color:#888">— not tested —</span>')
            elif r.get("ok"):
                status_html = format_html(
                    '<span style="color:#198754">✓ {} ms</span>',
                    r.get("latency_ms", "?"),
                )
            else:
                err = (r.get("error") or "").replace('"', "'")
                status_html = format_html(
                    '<span style="color:#dc3545" title="{}">✗ failed</span>', err,
                )

            privacy_html = format_html(
                '<span style="color:{}">{} {}</span>',
                badge_color(m.badge), badge_icon(m.badge), badge_short(m.badge),
            )

            retirement_html = mark_safe("")
            # Env-default badge — shows which model bootstraps on a fresh install.
            env_default_html = (
                mark_safe(
                    '<br><span style="color:#0f62fe;font-size:90%" '
                    'title="Selected by default:true in AZURE_E*_TAGS_*">'
                    "★ env-default</span>"
                )
                if m.is_env_default
                else mark_safe("")
            )
            ret_status = m.retirement_status
            days = m.days_until_retirement
            if ret_status == "retired":
                retirement_html = format_html(
                    '<br><span style="color:#dc3545;font-weight:600">'
                    "☠️ Retired {}</span>",
                    m.retirement_date.isoformat() if m.retirement_date else "",
                )
                if key in current_allowed:
                    retired_but_allowed.append(key)
            elif ret_status == "retiring_soon":
                retirement_html = format_html(
                    '<br><span style="color:#a75d00">'
                    "⏳ Retires in {} day{} ({})</span>",
                    days, "" if days == 1 else "s",
                    m.retirement_date.isoformat() if m.retirement_date else "",
                )
            elif m.retirement_date:
                retirement_html = format_html(
                    '<br><span style="color:#888;font-size:90%">Retires {}</span>',
                    m.retirement_date.isoformat(),
                )

            row_style = (
                "border-top:1px solid #eee;opacity:0.55"
                if ret_status == "retired"
                else "border-top:1px solid #eee"
            )
            is_retired = ret_status == "retired"
            default_checked = "checked" if key == current_default else ""
            allowed_checked = "checked" if key in current_allowed else ""
            disabled_attr = "disabled" if is_retired else ""
            hidden_keeper = (
                format_html(
                    '<input type="hidden" name="allowed_models" value="{}">',
                    key,
                )
                if is_retired and key in current_allowed
                else mark_safe("")
            )

            # Cost per 1M tokens display
            cip = m.cost_input_per_1m_tokens
            cop = m.cost_output_per_1m_tokens
            if cip is not None and cop is not None:
                cost_html = format_html(
                    '<span style="color:#198754;font-family:monospace">'
                    'in&nbsp;€{}/1M&nbsp;·&nbsp;out&nbsp;€{}/1M</span>',
                    cip, cop,
                )
            elif cip is not None:
                cost_html = format_html(
                    '<span style="color:#198754;font-family:monospace">'
                    'in&nbsp;€{}/1M</span>'
                    '<span style="color:#a75d00" title="Missing cost-output-1Mtoken tag"> ⚠️</span>',
                    cip,
                )
            elif cop is not None:
                cost_html = format_html(
                    '<span style="color:#198754;font-family:monospace">'
                    'out&nbsp;€{}/1M</span>'
                    '<span style="color:#a75d00" title="Missing cost-input-1Mtoken tag"> ⚠️</span>',
                    cop,
                )
            else:
                cost_html = mark_safe(
                    '<span style="color:#a75d00" title="No cost-input-1Mtoken / '
                    'cost-output-1Mtoken tags set on this model">'
                    "⚠️ no pricing</span>"
                )

            rows.append(format_html(
                '<tr style="{0}">'
                '<td style="padding:9px 12px;text-align:center">'
                '<input type="radio" name="default_model" value="{1}" {2} {3}></td>'
                '<td style="padding:9px 12px;text-align:center">'
                '<input type="checkbox" name="allowed_models" value="{1}" {4} {3}>'
                "{5}</td>"
                '<td style="padding:9px 12px;font-family:monospace">E{6}:{7}</td>'
                '<td style="padding:9px 12px">{8}</td>'
                '<td style="padding:9px 12px;color:#666">{9}{10}{11}{15}</td>'
                '<td style="padding:9px 12px">{12}</td>'
                '<td style="padding:9px 12px;font-family:monospace;color:#666">{13}</td>'
                '<td style="padding:9px 12px">{14}</td>'
                '<td style="padding:9px 12px">{16}</td>'
                "</tr>",
                row_style,
                key, default_checked, disabled_attr, allowed_checked,
                hidden_keeper,
                ep.index, m.tag,
                m.model_id,
                m.tags.get("provider", "").title(),
                f" · v{m.tags['version']}" if m.tags.get("version") else "",
                retirement_html,
                privacy_html,
                m.api,
                status_html,
                env_default_html,
                cost_html,
            ))

    table = format_html(
        '<table style="border-collapse:collapse;width:100%;'
        'background:#fff;border:1px solid #ddd;margin-bottom:14px">'
        '<thead><tr style="background:#f8f8f8;text-align:left">'
        '<th style="padding:10px 12px">Default</th>'
        '<th style="padding:10px 12px">Choose</th>'
        '<th style="padding:10px 12px">Endpoint</th>'
        '<th style="padding:10px 12px">Model</th>'
        '<th style="padding:10px 12px">Details</th>'
        '<th style="padding:10px 12px">Data handling</th>'
        '<th style="padding:10px 12px">API</th>'
        '<th style="padding:10px 12px">Status</th>'
        '<th style="padding:10px 12px">Pricing (EUR)</th>'
        "</tr></thead><tbody>{}</tbody></table>",
        mark_safe("".join(rows)),
    )

    legend = mark_safe(
        '<p style="color:#666;font-size:90%;margin:10px 0 4px 0">'
        "<b>Data handling:</b> "
        "🇪🇺 EU-resident (processing stays in EU) · "
        "🌐 Global (Microsoft as processor) · "
        "⚠️ Global (third-party MaaS) · "
        "❓ Unknown."
        "</p>"
    )

    banner = mark_safe("")
    if retired_but_allowed:
        banner = format_html(
            '<div style="background:#fff4f3;border:1px solid #f5b3b0;'
            "color:#a40000;padding:10px 14px;border-radius:4px;"
            'margin:0 0 14px 0">'
            "⚠️ <b>{} retired model(s)</b> still in the user-allowed list: "
            "<code>{}</code>. They are excluded from the user picker, but "
            "consider unticking them to keep the admin view clean."
            "</div>",
            len(retired_but_allowed), ", ".join(retired_but_allowed),
        )

    return mark_safe(
        '<div style="display:block;width:100%;flex-basis:100%">'
        + banner + btn_bar + table + legend +
        "</div>"
    )


class DeploymentTableWidget(forms.Widget):
    """Renders the deployments picker as a proper form widget.

    Because this is the ``default_model`` field's widget, its ``<input>`` elements
    live inside the change-form's ``<form>`` tag and submit correctly. The widget
    also renders ``allowed_models`` checkboxes (with matching ``name="allowed_models"``)
    so a single table drives both fields.
    """

    def __init__(self, *args, llm_config=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._llm_config = llm_config

    def render(self, name, value, attrs=None, renderer=None):
        current_default = value or ""
        cfg = self._llm_config
        current_allowed = set(cfg.allowed_models) if cfg and cfg.allowed_models else set()
        results = (cfg.last_health_check if cfg else {}) or {}
        registry = get_registry()
        if not registry:
            return mark_safe("<p><em>No Azure endpoints configured.</em></p>")

        return _render_deployments_table(
            registry=registry,
            results=results,
            current_default=current_default,
            current_allowed=current_allowed,
            cfg_pk=cfg.pk if cfg else None,
        )

    def value_from_datadict(self, data, files, name):
        # Radio submits one value.
        if hasattr(data, "getlist"):
            vals = data.getlist(name)
            return vals[0] if vals else ""
        return data.get(name, "")


class LLMConfigForm(forms.ModelForm):
    """Admin form: ``default_model`` and ``allowed_models`` are driven by the unified
    deployment-picker panel (see ``LLMConfigAdmin.deployments_panel``).

    The form fields carry silent widgets that render nothing; the panel's radio and
    checkbox inputs (with matching ``name=`` attributes) feed the form on submit.
    """

    class Meta:
        model = LLMConfig
        fields = ("default_model", "allowed_models")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        model_ch = all_model_choices()

        self.fields["default_model"] = forms.ChoiceField(
            choices=model_ch or [("", "-- no Azure models discovered --")],
            required=bool(model_ch),
            widget=DeploymentTableWidget(llm_config=self.instance),
            label="",
        )
        if model_ch:
            self.fields["allowed_models"] = forms.MultipleChoiceField(
                choices=model_ch,
                required=False,
                widget=forms.MultipleHiddenInput(),  # real inputs live in the table
                label="",
            )


@admin.register(LLMConfig)
class LLMConfigAdmin(admin.ModelAdmin):
    form = LLMConfigForm
    list_display = (
        "current_default",
        "discovered_endpoints_count",
        "pricing_summary",
        "health_summary",
        "updated_at",
    )
    fieldsets = (
        ("Deployments", {
            "fields": ("default_model", "allowed_models"),
            "description": mark_safe(
                '<div style="margin:6px 0 22px 0;max-width:900px;line-height:1.5">'
                "Each row is one Azure deployment. "
                "Pick one <b>Default</b> (sent for every request unless users have choice), "
                "tick the ones regular users may <b>Choose</b>. "
                "Click <b>Run health check</b> to refresh the Status column."
                "</div>"
            ),
        }),
    )

    # ── URL + button for the health check ─────────────────────────────────────

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:object_id>/run-health-check/",
                self.admin_site.admin_view(self.run_health_check_view),
                name="toxtempass_llmconfig_run_health_check",
            ),
        ]
        return custom + urls

    def run_health_check_view(self, request, object_id):
        """Trigger a live smoke test and persist results to LLMConfig."""
        from toxtempass.llm import run_health_check

        cfg = LLMConfig.load()
        try:
            results = run_health_check()
            cfg.last_health_check = results
            cfg.save()
            ok = sum(1 for r in results.values() if r.get("ok"))
            total = len(results)
            level = messages.SUCCESS if ok == total else messages.WARNING
            messages.add_message(
                request, level, f"Health check complete: {ok}/{total} deployments OK."
            )
        except Exception as exc:
            messages.error(request, f"Health check failed: {exc}")

        return HttpResponseRedirect(
            reverse("admin:toxtempass_llmconfig_change", args=[cfg.pk])
        )

    def change_view(self, request, object_id, form_url="", extra_context=None):
        """Inject the 'Run health check' button URL into the change template."""
        extra_context = extra_context or {}
        extra_context["run_health_check_url"] = reverse(
            "admin:toxtempass_llmconfig_run_health_check", args=[object_id]
        )
        return super().change_view(request, object_id, form_url, extra_context)

    # ── Columns & panels ──────────────────────────────────────────────────────

    def current_default(self, obj):
        return obj.default_model or "(auto)"
    current_default.short_description = "Default model"

    def discovered_endpoints_count(self, obj):
        registry = get_registry()
        total_models = sum(len(ep.models) for ep in registry)
        return f"{len(registry)} endpoint(s), {total_models} model(s)"
    discovered_endpoints_count.short_description = "Discovered"

    def pricing_summary(self, obj):
        """Show how many models have pricing tags configured."""
        registry = get_registry()
        all_models = [m for ep in registry for m in ep.models]
        if not all_models:
            return "—"
        with_pricing = sum(
            1 for m in all_models
            if m.cost_input_per_1m_tokens is not None and m.cost_output_per_1m_tokens is not None
        )
        total = len(all_models)
        if with_pricing == total:
            return format_html(
                '<span style="color:#198754"'
                ' title="All models have pricing configured">'
                "&#10003; {}/{} priced</span>",
                with_pricing, total,
            )
        elif with_pricing == 0:
            return format_html(
                '<span style="color:#a75d00"'
                ' title="Add cost-input-1Mtoken and cost-output-1Mtoken tags to '
                'AZURE_E*_TAGS_* to enable cost tracking">'
                "&#9888; 0/{} priced</span>",
                total,
            )
        return format_html(
            '<span style="color:#fd7e14"'
            ' title="{} of {} models are missing pricing tags">'
            "&#9888; {}/{} priced</span>",
            total - with_pricing, total, with_pricing, total,
        )
    pricing_summary.short_description = "Pricing"

    def health_summary(self, obj):
        """Compact ✓/✗ counter for the list view."""
        results = obj.last_health_check or {}
        if not results:
            return "—"
        ok = sum(1 for r in results.values() if r.get("ok"))
        total = len(results)
        colour = "#198754" if ok == total else ("#dc3545" if ok == 0 else "#fd7e14")
        return format_html(
            '<span style="color:{}">{}/{} OK</span>', colour, ok, total,
        )
    health_summary.short_description = "Last health check"

    def deployments_panel(self, obj):
        """Read-only view of the panel (used before the instance exists).

        The real interactive panel is rendered by ``DeploymentTableWidget`` on the
        ``default_model`` field — this method is only a fallback for the rare case
        where Django renders the panel outside of that widget.
        """
        registry = get_registry()
        if not registry:
            return mark_safe("<p><em>No Azure endpoints configured.</em></p>")
        return _render_deployments_table(
            registry=registry,
            results=obj.last_health_check or {},
            current_default=obj.default_model or "",
            current_allowed=set(obj.allowed_models or []),
            cfg_pk=obj.pk,
        )
    # ── Singleton enforcement ─────────────────────────────────────────────────

    def has_add_permission(self, request):
        # Only allow one instance
        return not LLMConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        # Explicitly copy the panel-provided inputs onto the instance —
        # the silent widgets don't render their own <input>s, so we bypass
        # any potential form cleaning edge-case by reading POST directly.
        post = request.POST
        default = post.get("default_model", "").strip()
        if default:
            obj.default_model = default
        obj.allowed_models = [v for v in post.getlist("allowed_models") if v]
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AssayCost)
class AssayCostAdmin(admin.ModelAdmin):
    """Read-only admin view for per-assay LLM cost records."""

    list_display = (
        "assay",
        "model_key",
        "model_id",
        "input_tokens",
        "output_tokens",
        "cost_input_display",
        "cost_output_display",
        "total_cost_display",
        "updated_at",
    )
    list_filter = ("model_key",)
    search_fields = ("assay__title", "model_key", "model_id")
    ordering = ("-updated_at",)
    readonly_fields = (
        "assay",
        "model_key",
        "model_id",
        "input_tokens",
        "output_tokens",
        "cost_input_per_1m",
        "cost_output_per_1m",
        "cost_input",
        "cost_output",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def cost_input_display(self, obj):
        if obj.cost_input is None:
            return mark_safe('<span style="color:#888">—</span>')
        return f"€{obj.cost_input:.6f}"
    cost_input_display.short_description = "Input cost (EUR)"

    def cost_output_display(self, obj):
        if obj.cost_output is None:
            return mark_safe('<span style="color:#888">—</span>')
        return f"€{obj.cost_output:.6f}"
    cost_output_display.short_description = "Output cost (EUR)"

    def total_cost_display(self, obj):
        total = obj.total_cost
        if total is None:
            return mark_safe('<span style="color:#888">—</span>')
        return format_html('<b>€{}</b>', f"{total:.6f}")
    total_cost_display.short_description = "Total cost (EUR)"
