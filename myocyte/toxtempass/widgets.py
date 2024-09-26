from typing import Any
from django.forms.renderers import BaseRenderer
from django.forms.widgets import Select
from django.urls import reverse
from django.utils.safestring import SafeText, mark_safe


class BootstrapSelectWithButtonsWidget(Select):
    default_btn_label = "Add"
    default_btn_class = (
        "d-flex align-items-center btn btn-outline-secondary rounded-end"
    )

    def __init__(
        self,
        button_url_names: list[str],
        button_labels: list[str] | None = None,
        button_classes: list[str] | None = None,
        *args,
        **kwargs,
    ):
        self.num_btns = len(button_url_names)
        self.button_url_names = button_url_names
        self.button_labels = (
            button_labels if button_labels else self.num_btns * [self.default_btn_label]
        )
        self.button_classes = (
            button_classes
            if button_classes
            else self.num_btns * [self.default_btn_class]
        )
        super().__init__(*args, **kwargs)

    def render(
        self,
        name: str,
        value: Any,
        attrs: dict[str, str] | None = None,
        renderer: BaseRenderer = None,
    ) -> SafeText:
        # Get the HTML for the original select widget
        select_html = super().render(name, value, attrs, renderer)
        assert isinstance(
            attrs, dict
        )  # set internally with an id label so this is for mypy

        buttons_html = []
        for num, (button_url_name, button_label, button_class) in enumerate(
            zip(
                self.button_url_names,
                self.button_labels,
                self.button_classes,
                strict=False,
            )
        ):
            # Resolve the URL using the reverse function
            if button_url_name:
                button_url = reverse(button_url_name)
            else:
                button_url = ""

            # Construct the button HTML
            buttons_html.append(
                f'<a href="{button_url}" class="{button_class}" name="{name}_btn{num}"'
                f' id="{attrs["id"]}_btn{num}" type="button">{button_label}</a>'
            )

        # Construct the form-floating and input-group structure
        html = (
            '<div class="input-group">'
            '<div class="form-floating">'
            f"{select_html}"
            f'<label for="{attrs["id"]}">{name.title()}</label>'
            "</div>"
            f"{''.join(buttons_html)}"
            "</div>"
        )
        return mark_safe(html)  # noqa: S308
