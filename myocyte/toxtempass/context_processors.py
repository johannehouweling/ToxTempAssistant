import logging

from django.http import HttpRequest
from django.urls import resolve

from toxtempass import Config, config


def toxtempass_config(request: HttpRequest) -> dict[str, Config]:
    """Include app config."""
    return {"config": config}


def current_url_name(request: HttpRequest) -> dict[str, str | None]:
    """Context processor to add the current URL name to the template context."""
    try:
        url_name = resolve(request.path_info).url_name
    except Exception as exc:
        logging.exception("Exception occurred while resolving URL name")
    return {"current_url_name": url_name}
