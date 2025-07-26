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
        label: str | None = None,
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
        self.label_override = label
        super().__init__(*args, **kwargs)

    def render(
        self,
        name: str,
        value: Any,
        attrs: dict[str, str] | None = None,
        renderer: BaseRenderer = None,
    ) -> SafeText:
        attrs = attrs or {}
        select_html = super().render(name, value, attrs, renderer)

        # pick the label text: either override, or from attrs, or fallback to name.title()
        label_text = (
            self.label_override
            or attrs.get("label")
            or name.replace("_", " ").capitalize()
        )

        buttons_html = []
        for num, (url_name, btn_label, btn_cls) in enumerate(
            zip(
                self.button_url_names,
                self.button_labels,
                self.button_classes,
                strict=False,
            )
        ):
            button_url = reverse(url_name) if url_name else ""
            buttons_html.append(
                f'<a href="{button_url}" class="{btn_cls}" '
                f'name="{name}_btn{num}" id="{attrs.get("id")}_btn{num}" '
                f'type="button">{btn_label}</a>'
            )

        html = (
            '<div class="input-group">'
            '<div class="form-floating">'
            f"{select_html}"
            f'<label for="{attrs.get("id")}">{label_text}</label>'
            "</div>"
            f"{''.join(buttons_html)}"
            "</div>"
        )
        return mark_safe(html)
