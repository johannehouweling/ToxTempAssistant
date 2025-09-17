from collections.abc import Sequence
from pathlib import Path

from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template.loader import render_to_string
from django_q.tasks import async_task


def send_email_task(
    *,
    to: Sequence[str],
    subject: str,
    # Option A: plain text
    body: str | None = None,
    # Option B: templates
    template_html: str | None = None,
    template_text: str | None = None,
    context: dict | None = None,
    attachments: list | None = None,
) -> None:
    """Send either a plain-text email (if `body` is provided) or a templated email.

    (if `template_html` or `template_text` is provided). Raises on failure so
    django-q2 will retry according to Q_CLUSTER settings.
    """
    if not body and not template_html and not template_text:
        raise ValueError(
            "Provide `body` for plain text or a template_* for templated email."
        )

    # A) Plain text only
    if body:
        msg = EmailMessage(
            subject=subject,
            body=body,
            to=list(to),
        )
    else:
        # B) Template path(s)
        ctx = context or {}
        text_body = render_to_string(template_text, ctx) if template_text else ""
        html_body = render_to_string(template_html, ctx) if template_html else None

        # choose best base: have text? use EmailMultiAlternatives for alt HTML; else use HTML as base
        if text_body:
            msg = EmailMultiAlternatives(subject=subject, body=text_body, to=list(to))
            if html_body is not None:
                msg.attach_alternative(html_body, "text/html")
        else:
            # HTML only: still send as HTML
            msg = EmailMultiAlternatives(
                subject=subject, body=html_body or "", to=list(to)
            )
            msg.attach_alternative(html_body or "", "text/html")

    # Attachments (both modes)
    for att in attachments or ():
        if att.path is not None:
            msg.attach_file(str(att.path))
        elif att.filename and att.content is not None:
            msg.attach(
                att.filename, att.content, att.mimetype or "application/octet-stream"
            )

    msg.send()


def on_email_done(task: any) -> None:
    """Hooks to execute after email is sent, e.g., for logging."""
    # task.success, task.result, task.attempt_count, task.func, task.args/kwargs
    # Log/metrics here (e.g., Sentry, DB row, print)
    pass


def queue_email(
    *,
    to: Sequence[str],
    subject: str,
    body: str | None = None,
    template_html: str | None = None,
    template_text: str | None = None,
    context: dict | None = None,
    attachments: list | None = None,
    group: str = "emails",
) -> str:
    """Keyword-only wrapper. Returns django-q2 task id."""
    task_id = async_task(
        "toxtempass.tasks.send_email_task",
        to=to,
        subject=subject,
        body=body,
        template_html=template_html,
        template_text=template_text,
        context=context,
        attachments=attachments,
        hook=on_email_done,
        group=group,
    )
    return str(task_id)
