import logging
import os

from django.apps import AppConfig
from django.conf import settings

_LOG = logging.getLogger(__name__)

limit = 32


def _limit(val: str, limit: int = limit) -> str:
    """Limit length of displayed value."""
    if not val:
        return ""
    if not isinstance(val, str):
        val = str(val)
    return val if len(val) <= limit else val[:limit] + "..."


def _mask(val: str, keep: int = 4, limit: int = limit) -> str:
    """Mask secrets for display (keep first few chars)."""
    if not val:
        return ""
    if len(val) <= keep:
        return "*" * len(val)
    return _limit(val[:keep] + "*" * (len(val) - keep), limit=limit)


class ToxtempassConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "toxtempass"

    def ready(self) -> None:
        """Log a summary of key settings on startup."""
        import toxtempass.signals  # noqa: F401, I001

        summary = {
            "DJANGO_DEBUG": _limit(settings.DEBUG),
            "TESTING": _limit(getattr(settings, "TESTING", False)),
            "USE_POSTGRES": _limit(getattr(settings, "USE_POSTGRES", False)),
            "DB_ENGINE": _limit(settings.DATABASES["default"]["ENGINE"]),
            "DB_NAME": _limit(settings.DATABASES["default"].get("NAME")),
            "DB_USER": _limit(settings.DATABASES["default"].get("USER")),
            "DB_HOST": _limit(settings.DATABASES["default"].get("HOST")),
            "DB_PORT": _limit(settings.DATABASES["default"].get("PORT")),
            "ALLOWED_HOSTS": _limit(settings.ALLOWED_HOSTS),
            "CSRF_TRUSTED_ORIGINS": _limit(settings.CSRF_TRUSTED_ORIGINS),
            "SECRET_KEY": _mask(settings.SECRET_KEY),
            "OPENAI_API_KEY": _mask(os.getenv("OPENAI_API_KEY")),
            "OPENROUTER_API_KEY": _mask(os.getenv("OPENROUTER_API_KEY")),
        }

        title = "ENV VARIABLES FOR DJANGO SETUP"
        topbarlength = 60
        minbarlength = len(title) + 2
        filllength = topbarlength - minbarlength
        toptitlebar = (
            "#" * (int(filllength / 2) - 1)
            + " "
            + title
            + " "
            + "#" * (int(filllength / 2) - 1)
        )
        _LOG.info(toptitlebar)
        for k, v in summary.items():
            _LOG.info(f"{k:<22} {v}")
        _LOG.info("#" * len(toptitlebar))


   