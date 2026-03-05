from typing import Dict

from .views import get_workspace_list
from django.utils.functional import SimpleLazyObject
from toxtempass import config


def toxtempass_config(request) -> dict:
    """Expose the app-level config object to templates as 'config'."""
    return {"config": config}


def current_url_name(request) -> dict:
    """Expose the current resolved URL name as 'current_url_name'."""
    name = ""
    try:
        name = request.resolver_match.url_name or ""
    except Exception:
        name = ""
    return {"current_url_name": name}


def workspaces(request) -> Dict[str, object]:
    """Add workspace lists to every template so the offcanvas can render on any page.

    This calls the existing get_workspace_list view helper which returns a dict with
    owned_workspaces, member_workspaces and accessible_investigations. Using a
    context processor avoids having to call this from every view that renders the
    offcanvas.
    """
    # Provide the three expected context keys but keep evaluation lazy so
    # DB access only happens when the template actually uses them.
    def _owned_workspaces():
        try:
            user = getattr(request, "user", None)
            if not user or not getattr(user, "is_authenticated", False):
                return []
            return get_workspace_list(request).get("owned_workspaces", [])
        except Exception:
            return []

    def _member_workspaces():
        try:
            user = getattr(request, "user", None)
            if not user or not getattr(user, "is_authenticated", False):
                return []
            return get_workspace_list(request).get("member_workspaces", [])
        except Exception:
            return []

    def _accessible_investigations():
        try:
            user = getattr(request, "user", None)
            if not user or not getattr(user, "is_authenticated", False):
                return []
            return get_workspace_list(request).get("accessible_investigations", [])
        except Exception:
            return []

    return {
        "owned_workspaces": SimpleLazyObject(_owned_workspaces),
        "member_workspaces": SimpleLazyObject(_member_workspaces),
        "accessible_investigations": SimpleLazyObject(_accessible_investigations),
    }
