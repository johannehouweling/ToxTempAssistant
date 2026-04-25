"""Tests: export_assay_to_file error handling.

Verifies that when Pandoc (subprocess.run) raises CalledProcessError or an
unexpected Exception:
1. The response has HTTP status 500.
2. assay.status_context is updated with the correlation id.
"""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from toxtempass import Config

PANDOC_EXPORT_TYPES = Config.PANDOC_EXPORT_TYPES


def _mock_assay() -> MagicMock:
    """Return a mock Assay with the minimal attributes used by export_assay_to_file."""
    assay = MagicMock()
    assay.status_context = ""
    assay.title = "error test assay"
    return assay


def _run_export_with_pandoc_error(assay, side_effect):
    """Run export_assay_to_file for the first Pandoc type with a given subprocess error."""
    from toxtempass.export import export_assay_to_file

    request = MagicMock()
    export_type = next(iter(PANDOC_EXPORT_TYPES))

    with tempfile.TemporaryDirectory() as tmp_dir:
        yaml_stub = Path(tmp_dir) / "meta.yaml"
        yaml_stub.write_text("title: test")

        with (
            patch("toxtempass.export.settings") as mock_settings,
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
                side_effect=side_effect,
            ),
        ):
            mock_settings.MEDIA_ROOT = tmp_dir
            response = export_assay_to_file(request, assay, export_type)

    return response


class ExportCalledProcessErrorTests(SimpleTestCase):
    """subprocess.CalledProcessError → HTTP 500 + correlation id in status_context."""

    def test_returns_500(self):
        assay = _mock_assay()
        error = subprocess.CalledProcessError(returncode=1, cmd=["pandoc"])
        response = _run_export_with_pandoc_error(assay, error)
        self.assertEqual(response.status_code, 500)

    def test_status_context_contains_corr_id(self):
        assay = _mock_assay()
        error = subprocess.CalledProcessError(returncode=1, cmd=["pandoc"])
        _run_export_with_pandoc_error(assay, error)
        self.assertRegex(
            assay.status_context,
            r"\[[0-9a-f]{8}\]",
            msg="status_context should contain a correlation id like [abcd1234]",
        )


class ExportUnexpectedExceptionTests(SimpleTestCase):
    """Generic Exception → HTTP 500 + correlation id in status_context."""

    def test_returns_500(self):
        assay = _mock_assay()
        error = RuntimeError("unexpected pandoc failure")
        response = _run_export_with_pandoc_error(assay, error)
        self.assertEqual(response.status_code, 500)

    def test_status_context_contains_corr_id(self):
        assay = _mock_assay()
        error = RuntimeError("unexpected pandoc failure")
        _run_export_with_pandoc_error(assay, error)
        self.assertRegex(
            assay.status_context,
            r"\[[0-9a-f]{8}\]",
            msg="status_context should contain a correlation id like [abcd1234]",
        )
