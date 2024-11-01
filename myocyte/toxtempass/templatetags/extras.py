from typing import Any
from django import template

register = template.Library()


@register.filter(name="getattr")
def getattr_custom(obj, attr_name):
    """Get an attribute dynamically from an object."""
    return getattr(obj, attr_name, None)


@register.filter()
def form_field(form, field_name):
    """
    Custom template filter to dynamically retrieve a form field by its name.
    Usage: {{ form|form_field:"field_name" }}
    """
    return form[field_name]


@register.filter()
def add_asstring(a: str, b: Any) -> str:
    return a + str(b)


@register.filter()
def intdivperc(a: float, b: float) -> int:
    if b != 0:
        return int(a / b * 100)
    else:
        return 0
