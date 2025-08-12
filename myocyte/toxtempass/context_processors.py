from django.http import HttpRequest

from toxtempass import Config, config


def toxtempass_config(request: HttpRequest) -> dict[str, Config]:
    """Include app config."""
    return {"config": config}
