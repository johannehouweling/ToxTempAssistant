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

        # Register ephemeral django_q schedules (in-memory, not persisted to DB)
        self._register_ephemeral_schedules()

    def _register_ephemeral_schedules(self) -> None:
        """Register ephemeral (in-memory) django_q schedules.

        These schedules are created in memory at startup and not persisted to
        the database. On each app restart, old schedules are discarded, preventing
        duplicate task runs.
        """
        try:
            from django_q.tasks import schedule
            from django.utils import timezone
            from datetime import timedelta

            # Schedule orphaned file cleanup: every week (168 hours)
            schedule(
                "toxtempass.utilities.cleanup_orphaned_files",
                schedule_type="H",  # Hourly recurring at specific times
                repeats=-1,  # Infinite repeats
                minutes=0,  # On the hour
                next_run=timezone.now() + timedelta(hours=1),
                kwargs={"phase": 1, "dry_run": False},
            )
            _LOG.info("Registered ephemeral schedule: cleanup_orphaned_files (Phase 1)")

            # Phase 2 follows a week after Phase 1
            schedule(
                "toxtempass.utilities.cleanup_orphaned_files",
                schedule_type="H",
                repeats=-1,
                minutes=0,
                next_run=timezone.now() + timedelta(days=7, hours=1),
                kwargs={"phase": 2, "dry_run": False},
            )
            _LOG.info("Registered ephemeral schedule: cleanup_orphaned_files (Phase 2)")

        except ImportError:
            _LOG.warning("django_q not available; ephemeral schedules not registered")
        except Exception as e:
            _LOG.warning(f"Failed to register ephemeral schedules: {e}")
