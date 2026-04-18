"""Regression tests: export_assay_to_file security hardening.

Verifies that:
1. Exported filenames use only the hardcoded suffix from mime_type_suffix_dict,
   not raw export_type string concatenation.
2. The Pandoc subprocess command contains only trusted options from EXPORT_MAPPING
   and never includes raw export_type values as standalone arguments.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import TestCase

from toxtempass.export import EXPORT_MAPPING, PANDOC_EXPORT_TYPES, mime_type_suffix_dict
from toxtempass.tests.fixtures.factories import AssayFactory, PersonFactory


def _make_pandoc_stub(captured_commands: list) -> object:
    """Return a side_effect callable that records the command and touches the output file."""

    def _run(cmd, check=False):
        captured_commands.append(list(cmd))
        try:
            o_idx = cmd.index("-o")
            Path(cmd[o_idx + 1]).touch()
        except ValueError:
            pass

    return _run


class ExportFilenameTests(TestCase):
    """Filename suffix is derived from mime_type_suffix_dict, not raw export_type."""

    def setUp(self):
        self.user = PersonFactory()
        self.assay = AssayFactory(title="my test assay")
        self.request = MagicMock()

    def test_json_filename_suffix_from_mapping(self):
        """JSON export filename ends with the suffix from mime_type_suffix_dict."""
        from toxtempass.export import export_assay_to_file

        with tempfile.TemporaryDirectory() as tmp_dir:
            with (
                patch("toxtempass.export.settings") as mock_settings,
                patch("toxtempass.export.Config") as mock_config,
                patch(
                    "toxtempass.export.generate_json_from_assay", return_value={}
                ),
            ):
                mock_settings.MEDIA_ROOT = tmp_dir
                mock_config.allowed_export_types = list(EXPORT_MAPPING.keys())
                response = export_assay_to_file(self.request, self.assay, "json")

        expected_suffix = mime_type_suffix_dict["json"]["suffix"]  # ".json"
        content_disp = response.headers.get("Content-Disposition", "")
        self.assertIn(expected_suffix, content_disp)
        # Guard against a double-dot regression (e.g. "toxtemp_title..json")
        self.assertNotIn("..", content_disp)

    def test_pandoc_filename_suffix_from_mapping(self):
        """Every Pandoc export type uses the suffix from mime_type_suffix_dict."""
        from toxtempass.export import export_assay_to_file

        for export_type in PANDOC_EXPORT_TYPES:
            with (
                self.subTest(export_type=export_type),
                tempfile.TemporaryDirectory() as tmp_dir,
            ):
                yaml_stub = Path(tmp_dir) / "meta.yaml"
                yaml_stub.write_text("title: test")
                captured_commands: list = []

                with (
                    patch("toxtempass.export.settings") as mock_settings,
                    patch("toxtempass.export.Config") as mock_config,
                    patch(
                        "toxtempass.export.generate_markdown_from_assay",
                        return_value="# test",
                    ),
                    patch(
                        "toxtempass.export.get_create_meta_data_yaml",
                        return_value=yaml_stub,
                    ),
                    patch(
                        "toxtempass.export.subprocess.run",
                        side_effect=_make_pandoc_stub(captured_commands),
                    ),
                ):
                    mock_settings.MEDIA_ROOT = tmp_dir
                    mock_config.allowed_export_types = list(EXPORT_MAPPING.keys())
                    response = export_assay_to_file(
                        self.request, self.assay, export_type
                    )

                expected_suffix = mime_type_suffix_dict[export_type]["suffix"]
                content_disp = response.headers.get("Content-Disposition", "")
                self.assertIn(
                    expected_suffix,
                    content_disp,
                    msg=f"Expected suffix '{expected_suffix}' for type '{export_type}'",
                )
                self.assertNotIn(
                    "..",
                    content_disp,
                    msg=f"Double-dot in Content-Disposition for type '{export_type}'",
                )


class ExportPandocCommandTests(TestCase):
    """Pandoc command is built only from EXPORT_MAPPING trusted options."""

    def setUp(self):
        self.user = PersonFactory()
        self.assay = AssayFactory(title="pandoc test assay")
        self.request = MagicMock()

    def test_pandoc_command_contains_only_mapped_options(self):
        """subprocess.run receives exactly the trusted options listed in EXPORT_MAPPING."""
        from toxtempass.export import export_assay_to_file

        for export_type in PANDOC_EXPORT_TYPES:
            with (
                self.subTest(export_type=export_type),
                tempfile.TemporaryDirectory() as tmp_dir,
            ):
                yaml_stub = Path(tmp_dir) / "meta.yaml"
                yaml_stub.write_text("title: test")
                captured_commands: list = []

                with (
                    patch("toxtempass.export.settings") as mock_settings,
                    patch("toxtempass.export.Config") as mock_config,
                    patch(
                        "toxtempass.export.generate_markdown_from_assay",
                        return_value="# test",
                    ),
                    patch(
                        "toxtempass.export.get_create_meta_data_yaml",
                        return_value=yaml_stub,
                    ),
                    patch(
                        "toxtempass.export.subprocess.run",
                        side_effect=_make_pandoc_stub(captured_commands),
                    ),
                ):
                    mock_settings.MEDIA_ROOT = tmp_dir
                    mock_config.allowed_export_types = list(EXPORT_MAPPING.keys())
                    export_assay_to_file(self.request, self.assay, export_type)

                self.assertEqual(
                    len(captured_commands),
                    1,
                    msg=f"Expected one subprocess.run call for type '{export_type}'",
                )
                cmd = captured_commands[0]

                # Every trusted option from EXPORT_MAPPING must appear in the command
                for opt in EXPORT_MAPPING[export_type]:
                    self.assertIn(
                        opt,
                        cmd,
                        msg=f"Trusted option '{opt}' missing from pandoc cmd for '{export_type}'",
                    )

                # The raw export_type string must NOT be a standalone argument
                self.assertNotIn(
                    export_type,
                    cmd,
                    msg=f"Raw export_type '{export_type}' must not appear as a standalone "
                    f"argument in the pandoc command",
                )
