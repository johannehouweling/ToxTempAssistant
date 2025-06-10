from toxtempass import config, Config
from django.http import HttpRequest


def toxtempass_config(request: HttpRequest) -> dict[str, Config]:
    return {"config": config}
