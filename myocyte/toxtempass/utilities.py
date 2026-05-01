import hashlib
import logging
from pathlib import Path
from typing import Callable

from django.db import transaction
from django.db.models import Model

from toxtempass import config
from toxtempass.models import Assay, Investigation, Person, Study

logger = logging.getLogger(__name__)


def log_processing_event(
    assay: Assay, msg: str, clear_first: bool = False, is_error: bool = True
) -> None:
    """Append an internal event to ``assay.processing_log`` (debug/audit only).

    If clear_first is True, overwrite the field; otherwise, append. Total field
    length is capped at ``config.status_error_max_len`` by dropping the oldest
    entries; full tracebacks live in the persistent log file.

    Not surfaced to users — entries may contain stack traces, exception text,
    file paths, or correlation ids. For user-facing notifications, use
    :func:`add_user_alert` instead.
    """
    preamble = "Error occurred: " if is_error else "Info: "
    new_entry = f"{preamble}{msg}"
    if clear_first:
        combined = new_entry
    else:
        prev = getattr(assay, "processing_log", "") or ""
        combined = prev + ("\n" if prev else "") + new_entry

    if len(combined) > config.status_error_max_len:
        # Drop oldest lines first, but always preserve the most recent entry.
        lines = combined.splitlines()
        while len(lines) > 1 and len("\n".join(lines)) > config.status_error_max_len:
            lines.pop(0)
        combined = "\n".join(lines)
        if len(combined) > config.status_error_max_len:
            combined = combined[-config.status_error_max_len :]

    setattr(assay, "processing_log", combined)


def add_user_alert(
    assay: Assay, message: str, level: str = "warning"
) -> None:
    """Append a user-visible alert to ``assay.user_alerts``.

    Rendered as a dismissible Bootstrap banner on the assay page. ``level`` is
    a Bootstrap alert variant (``"info" | "warning" | "danger" | "success"``).

    Pre-vetted text only — never include raw exception messages, file paths,
    correlation ids, or other internal data here. For internal logging use
    :func:`log_processing_event`.
    """
    from django.utils import timezone

    alerts = list(getattr(assay, "user_alerts", None) or [])
    alerts.append({
        "message": message,
        "level": level,
        "ts": timezone.now().isoformat(),
    })
    setattr(assay, "user_alerts", alerts)


def calculate_md5(pdf_file_path: Path) -> str:
    """Calculate MD5 hash for a given PDF file."""
    md5_hash = hashlib.md5(usedforsecurity=False)

    # Open the PDF file in binary mode and read it in chunks
    with open(pdf_file_path, "rb") as pdf_file:
        # Read in chunks of 4096 bytes
        for chunk in iter(lambda: pdf_file.read(4096), b""):
            md5_hash.update(chunk)

    # Return the hexadecimal digest of the hash
    return md5_hash.hexdigest()


def calculate_md5_multiplefiles(files: list) -> dict:
    """Calculate MD5 has for multiple pdf files."""
    md5dict = {}
    for file in files:
        md5dict[Path(file)] = calculate_md5(file)
    return md5dict


def combine_dicts(dict1: dict, dict2: dict) -> dict:
    """Combine two dicts."""
    combined = {}

    # Get all keys from both dictionaries
    keys = set(dict1.keys()).union(dict2.keys())

    for key in keys:
        if key in dict1 and key in dict2:
            # If both values are dictionaries, recursively combine them
            if isinstance(dict1[key], dict) and isinstance(dict2[key], dict):
                combined[key] = combine_dicts(dict1[key], dict2[key])
            else:
                # If they are not dictionaries, you can decide how to handle conflicts
                combined[key] = dict1[key]  # or dict2[key] or a tuple of both, etc.
        elif key in dict1:
            # If the key is only in the first dictionary
            combined[key] = dict1[key]
        else:
            # If the key is only in the second dictionary
            combined[key] = dict2[key]

    return combined

# --- Beta utilities (token generation, verification, preference helpers) ---

def update_prefs_atomic(
    user: Person, mutate: Callable[[dict], bool]
) -> dict:
    """Atomically read-modify-write ``Person.preferences`` under a row lock.

    ``mutate(prefs)`` receives a dict (never None), mutates it in place, and
    returns ``True`` when prefs changed and a save is required, ``False`` to
    skip the save. Returns the latest prefs dict.

    Why: ``preferences`` is a JSONField holding multiple semantically distinct
    keys (beta state, tour progress, llm pref). The naive read-modify-write
    pattern allows concurrent requests to clobber each other's keys. Locking
    the row with ``SELECT FOR UPDATE`` serialises writers, eliminating the
    lost-update race.
    """
    with transaction.atomic():
        locked = Person.objects.select_for_update().get(pk=user.pk)
        prefs = locked.preferences or {}
        changed = mutate(prefs)
        if changed:
            locked.preferences = prefs
            locked.save(update_fields=["preferences"])
        # Reflect the post-lock state on the caller's instance so subsequent
        # reads see fresh data instead of the pre-lock snapshot.
        user.preferences = prefs
        return prefs


def generate_beta_token(person_id: int) -> str:
    """Generate a time-signed token for admitting a person to the beta program.

    The returned token is created with Django's signing machinery and should be
    safe to embed in approval links. It encodes a small payload containing the
    person's id. Verification should be done with verify_beta_token.
    """
    # Import locally to avoid making this module import Django at top-level
    from django.core.signing import dumps

    payload = {"person_id": person_id}
    return dumps(payload, salt="toxtempass-beta")


def verify_beta_token(token: str, max_age_days: int = 30) -> None|dict:
    """Verify a beta token and return the payload on success, otherwise None.

    max_age_days controls how long the token is valid (default 30 days).
    """
    from django.core.signing import loads, BadSignature, SignatureExpired

    max_age_seconds = int(max_age_days) * 24 * 60 * 60
    try:
        data = loads(token, salt="toxtempass-beta", max_age=max_age_seconds)
        return data
    except SignatureExpired:
        return None
    except BadSignature:
        return None


def set_beta_requested(person, comment: str | None = None) -> None:
    """Mark a Person as having requested access to the beta program.

    Safely handles person.preferences == None. Sets:
      - beta_signup = True
      - beta_requested_at = ISO timestamp
      - beta_admitted = False (if not present)
      - beta_comment = comment (if provided)
    """
    from django.utils import timezone

    def mutate(prefs: dict) -> bool:
        prefs["beta_signup"] = True
        prefs["beta_requested_at"] = timezone.now().isoformat()
        prefs.setdefault("beta_admitted", False)
        if comment is not None:
            prefs["beta_comment"] = comment
        return True

    update_prefs_atomic(person, mutate)


def set_beta_admitted(
    person: Person, admitted: bool, comment: str | None = None
) -> None:
    """Admit or revoke a Person's beta status.

    Sets:
      - beta_admitted = bool(admitted)
      - beta_admitted_at = ISO timestamp when admitted, or None when revoked
      - beta_comment = comment (if provided)
    """
    from django.utils import timezone

    def mutate(prefs: dict) -> bool:
        prefs["beta_admitted"] = bool(admitted)
        prefs["beta_admitted_at"] = (
            timezone.now().isoformat() if admitted else None
        )
        if comment is not None:
            prefs["beta_comment"] = comment
        return True

    update_prefs_atomic(person, mutate)


# ---------------------------------------------------------------------------
# Password reset rate-limiting helpers
# ---------------------------------------------------------------------------

# Minimum wait in seconds between consecutive reset requests.
# Index 0 → wait before 2nd attempt, index 1 → before 3rd, etc.
# Schedule: 1 min → 5 min → 1 hour → 1 day
_PW_RESET_WAIT_PERIODS: list[int] = [60, 300, 3600, 86400]
_PW_RESET_MAX_STORED = 10  # keep only the most recent N attempt timestamps


def get_password_reset_wait_seconds(person: "Person") -> float:
    """Return seconds the user must still wait before a new reset request.

    Returns 0.0 if the user is allowed to request immediately.
    The wait schedule (between consecutive attempts) is:
    1 min → 5 min → 1 hour → 1 day.
    """
    import datetime

    prefs = person.preferences or {}
    attempts: list[str] = prefs.get("pw_reset_attempts", [])
    if not attempts:
        return 0.0

    try:
        last_attempt = datetime.datetime.fromisoformat(attempts[-1])
    except (ValueError, TypeError):
        return 0.0

    if last_attempt.tzinfo is None:
        last_attempt = last_attempt.replace(tzinfo=datetime.timezone.utc)

    from django.utils import timezone as tz

    elapsed = (tz.now() - last_attempt).total_seconds()
    idx = min(len(attempts) - 1, len(_PW_RESET_WAIT_PERIODS) - 1)
    required_wait = _PW_RESET_WAIT_PERIODS[idx]
    return max(0.0, required_wait - elapsed)


def record_password_reset_attempt(person: "Person") -> None:
    """Append a timestamp for a new password reset attempt to the user's preferences."""
    from django.utils import timezone as tz

    def mutate(prefs: dict) -> bool:
        attempts = list(prefs.get("pw_reset_attempts", []))
        attempts.append(tz.now().isoformat())
        prefs["pw_reset_attempts"] = attempts[-_PW_RESET_MAX_STORED:]
        return True

    update_prefs_atomic(person, mutate)


def provenance_label_for_item(
    item: Model,
    current_user: Person | None,
) -> str:
    """Return a provenance-aware display label for a Study/Assay title.

    Rules:
      - If creator is present and different from investigation_owner, show
        "{title} (by creator.email on behalf of owner.email)".
      - Else if creator is present and different from current_user, show
        "{title} (by creator.email)".
      - Else if investigation_owner is present and different from current_user,
        show "{title} (by owner.email)".
      - Otherwise, return the plain title.
    """
    # default
    investigation_owner = None
    creator = None
    # Support Study, Assay and Investigation model instances
    if isinstance(item, Study):
        investigation_owner = item.investigation.owner if item.investigation else None
        creator = getattr(item, "created_by", None)
    elif isinstance(item, Assay):
        investigation_owner = (
            item.study.investigation.owner
            if item.study and item.study.investigation
            else None
        )
        creator = getattr(item, "created_by", None)
    elif isinstance(item, Investigation):
        investigation_owner = getattr(item, "owner", None)
        creator = getattr(item, "created_by", None)
    else:
        # If some other object (or a raw title) was passed, try best-effort
        creator = getattr(item, "created_by", None)
    creator_str = creator.email if creator else "Unknown"
    if creator == current_user:
        creator_str = "You"
    try:
        if creator and investigation_owner and creator.id != investigation_owner.id:
            return f"{item.title} (by {creator_str} on behalf of {investigation_owner.email})"
        if creator and current_user and creator.id != current_user.id:
            return f"{item.title} (by {creator_str})"
        if (
            investigation_owner
            and current_user
            and investigation_owner.id != current_user.id
        ):
            return f"{item.title} (by {investigation_owner.email})"
        # Fallbacks: if creator exists and is not current_user
        if creator and (not current_user or creator.id != current_user.id):
            return f"{item.title} (by {creator_str})"
        if investigation_owner and (
            not current_user or investigation_owner.id != current_user.id
        ):
            return f"{item.title} (by {investigation_owner.email})"
    except Exception:
        pass
    return item.title
