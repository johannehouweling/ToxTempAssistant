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
