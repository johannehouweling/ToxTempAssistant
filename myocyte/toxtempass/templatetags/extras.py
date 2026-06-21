import json

from django import template

register = template.Library()


@register.filter(name="getattr")
def getattr_custom(obj: object, attr_name: str) -> object:
    """Get an attribute dynamically from an object."""
    return getattr(obj, attr_name, None)


@register.filter()
def form_field(form: object, field_name: str) -> object:
    """Filter form by field name.

    Usage: {{ form|form_field:"field_name" }}
    """
    return form[field_name]


@register.filter()
def add_asstring(a: str, b: object) -> str:
    """Concatenate a string with another value.

    Converting the value to a string if necessary.
    Usage: {{ a|add_asstring:b }}
    """
    return a + str(b)


@register.filter()
def intdivperc(a: float, b: float) -> int:
    """Calculate the percentage of a divided by b."""
    if b != 0:
        return int(a / b * 100)
    else:
        return 0


@register.filter()
def mul(a: float, b: float) -> float:
    """Multiply two values (Django templates can't do arithmetic natively).

    Usage: {{ value|mul:100 }}
    """
    try:
        return float(a) * float(b)
    except (TypeError, ValueError):
        return 0


@register.filter()
def certainty_opacity(value: float | None) -> int:
    """Map a 0–1 certainty to a Bootstrap opacity step (50 / 75 / 100).

    Used to shade the indigo suggestion badge by confidence. Unknown/None
    certainty falls back to the faintest step.
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 50
    if v >= 0.67:
        return 100
    if v >= 0.34:
        return 75
    return 50


@register.filter()
def get_item(mapping: object, key: object) -> object:
    """Look up ``key`` in a dict from a template (handles int/str key mismatch).

    Usage: {{ pending_suggestions|get_item:question.id }}
    """
    if not isinstance(mapping, dict):
        return None
    if key in mapping:
        return mapping[key]
    return mapping.get(str(key), mapping.get(key))


@register.filter()
def to_json(value: object) -> str:
    """Serialize a value to a JSON string for embedding in an HTML attribute.

    Returns a plain (un-marked-safe) string so Django auto-escapes it for the
    attribute; the browser decodes it back on getAttribute() before JSON.parse().

    Usage: <div data-citations="{{ obj.citations|to_json }}">
    """
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return "[]"
