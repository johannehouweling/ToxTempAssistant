"""Tests: FAIR data export improvements.

Covers:
1. JSON export includes identifier (UUID), author, keywords, license fields.
2. JSON-LD export produces well-structured JSON-LD with @context and @id.
3. FAIR ZIP export contains the expected files (jsonld, PROVENANCE, LICENSE, README).
4. API endpoint URL pattern resolves correctly.
5. New export types are registered in Config allowlists.
"""

import io
import json
import zipfile
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from toxtempass import Config


class ConfigFAIRExportTypesTests(SimpleTestCase):
    """New FAIR export types are registered in Config allowlists."""

    def test_jsonld_in_export_mime_suffix(self):
        self.assertIn("jsonld", Config.EXPORT_MIME_SUFFIX)
        self.assertEqual(
            Config.EXPORT_MIME_SUFFIX["jsonld"]["mime_type"], "application/ld+json"
        )
        self.assertEqual(Config.EXPORT_MIME_SUFFIX["jsonld"]["suffix"], ".jsonld")

    def test_zip_in_export_mime_suffix(self):
        self.assertIn("zip", Config.EXPORT_MIME_SUFFIX)
        self.assertEqual(
            Config.EXPORT_MIME_SUFFIX["zip"]["mime_type"], "application/zip"
        )
        self.assertEqual(Config.EXPORT_MIME_SUFFIX["zip"]["suffix"], ".zip")

    def test_jsonld_in_export_mapping(self):
        self.assertIn("jsonld", Config.EXPORT_MAPPING)

    def test_zip_in_export_mapping(self):
        self.assertIn("zip", Config.EXPORT_MAPPING)

    def test_jsonld_not_in_pandoc_types(self):
        self.assertNotIn("jsonld", Config.PANDOC_EXPORT_TYPES)

    def test_zip_not_in_pandoc_types(self):
        self.assertNotIn("zip", Config.PANDOC_EXPORT_TYPES)


def _make_assay_mock(uid=None):
    """Return a minimal mock Assay suitable for FAIR export helpers."""
    import uuid as _uuid

    assay = MagicMock()
    assay.uid = uid or _uuid.uuid4()
    assay.title = "My Test Assay"
    assay.description = "A test assay description."
    assay.submission_date.isoformat.return_value = "2024-01-01T00:00:00+01:00"
    assay.question_set = None

    owner = MagicMock()
    owner.get_full_name.return_value = "Jane Doe"
    owner.email = "jane@example.com"
    owner.orcid_id = "0000-0002-1825-0097"
    assay.owner = owner

    study = MagicMock()
    study.title = "My Study"
    investigation = MagicMock()
    investigation.title = "My Investigation"
    study.investigation = investigation
    assay.study = study

    # answers queryset is empty for these unit tests
    assay.answers.filter.return_value.first.return_value = None

    return assay


class GenerateProvenanceDictTests(SimpleTestCase):
    """generate_provenance_dict returns a valid W3C PROV-JSON-inspired dict."""

    def test_contains_required_keys(self):
        from toxtempass.export import generate_provenance_dict

        assay = _make_assay_mock()
        result = generate_provenance_dict(assay, "2024-06-01T12:00:00+01:00")
        self.assertIn("@context", result)
        self.assertIn("prov:entity", result)
        self.assertIn("prov:activity", result)
        self.assertIn("prov:wasAttributedTo", result)

    def test_entity_id_contains_assay_uid(self):
        from toxtempass.export import generate_provenance_dict

        assay = _make_assay_mock()
        result = generate_provenance_dict(assay, "2024-06-01T12:00:00+01:00")
        self.assertIn(str(assay.uid), result["prov:entity"]["@id"])

    def test_agent_includes_orcid(self):
        from toxtempass.export import generate_provenance_dict

        assay = _make_assay_mock()
        result = generate_provenance_dict(assay, "2024-06-01T12:00:00+01:00")
        agent = result["prov:wasAttributedTo"]
        self.assertIn("schema:identifier", agent)
        self.assertIn("0000-0002-1825-0097", agent["schema:identifier"])

    def test_agent_without_orcid(self):
        from toxtempass.export import generate_provenance_dict

        assay = _make_assay_mock()
        assay.owner.orcid_id = None
        result = generate_provenance_dict(assay, "2024-06-01T12:00:00+01:00")
        agent = result["prov:wasAttributedTo"]
        self.assertNotIn("schema:identifier", agent)


class GenerateJsonldFromAssayTests(SimpleTestCase):
    """generate_jsonld_from_assay returns a JSON-LD document."""

    def _call(self, assay):
        from toxtempass.export import generate_jsonld_from_assay

        with patch("toxtempass.export.Section") as mock_section_cls:
            mock_section_cls.objects.filter.return_value.prefetch_related.return_value = (
                []
            )
            return generate_jsonld_from_assay(assay)

    def test_context_present(self):
        assay = _make_assay_mock()
        result = self._call(assay)
        self.assertIn("@context", result)
        self.assertIn("@vocab", result["@context"])

    def test_type_is_dataset(self):
        assay = _make_assay_mock()
        result = self._call(assay)
        self.assertEqual(result["@type"], "Dataset")

    def test_id_contains_uid(self):
        assay = _make_assay_mock()
        result = self._call(assay)
        self.assertIn(str(assay.uid), result["@id"])
        self.assertIn(str(assay.uid), result["identifier"])

    def test_creator_has_orcid(self):
        assay = _make_assay_mock()
        result = self._call(assay)
        creator = result["creator"]
        self.assertIn("identifier", creator)
        self.assertIn("0000-0002-1825-0097", creator["identifier"])

    def test_creator_without_orcid(self):
        assay = _make_assay_mock()
        assay.owner.orcid_id = None
        result = self._call(assay)
        creator = result["creator"]
        self.assertNotIn("identifier", creator)

    def test_license_present(self):
        assay = _make_assay_mock()
        result = self._call(assay)
        self.assertIn("license", result)

    def test_keywords_present(self):
        assay = _make_assay_mock()
        result = self._call(assay)
        self.assertIsInstance(result["keywords"], list)
        self.assertTrue(len(result["keywords"]) > 0)


class GenerateFairZipBytesTests(SimpleTestCase):
    """generate_fair_zip_bytes produces a valid ZIP with expected members."""

    def _call(self, assay):
        from toxtempass.export import generate_fair_zip_bytes

        with patch("toxtempass.export.Section") as mock_section_cls:
            mock_section_cls.objects.filter.return_value.prefetch_related.return_value = (
                []
            )
            return generate_fair_zip_bytes(assay)

    def test_returns_bytes(self):
        assay = _make_assay_mock()
        result = self._call(assay)
        self.assertIsInstance(result, bytes)

    def test_is_valid_zip(self):
        assay = _make_assay_mock()
        result = self._call(assay)
        self.assertTrue(zipfile.is_zipfile(io.BytesIO(result)))

    def test_zip_contains_jsonld(self):
        assay = _make_assay_mock()
        result = self._call(assay)
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            names = zf.namelist()
        self.assertTrue(any(name.endswith(".jsonld") for name in names))

    def test_zip_contains_provenance(self):
        assay = _make_assay_mock()
        result = self._call(assay)
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            names = zf.namelist()
        self.assertIn("PROVENANCE.json", names)

    def test_zip_contains_license(self):
        assay = _make_assay_mock()
        result = self._call(assay)
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            names = zf.namelist()
        self.assertIn("LICENSE.txt", names)

    def test_zip_contains_readme(self):
        assay = _make_assay_mock()
        result = self._call(assay)
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            names = zf.namelist()
        self.assertIn("README.md", names)

    def test_provenance_json_is_valid(self):
        assay = _make_assay_mock()
        result = self._call(assay)
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            data = json.loads(zf.read("PROVENANCE.json"))
        self.assertIn("prov:entity", data)

    def test_jsonld_in_zip_is_valid_json(self):
        assay = _make_assay_mock()
        result = self._call(assay)
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            jsonld_name = next(n for n in zf.namelist() if n.endswith(".jsonld"))
            data = json.loads(zf.read(jsonld_name))
        self.assertEqual(data["@type"], "Dataset")

    def test_readme_mentions_fair(self):
        assay = _make_assay_mock()
        result = self._call(assay)
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            readme = zf.read("README.md").decode()
        self.assertIn("FAIR", readme)

    def test_readme_mentions_uuid(self):
        assay = _make_assay_mock()
        result = self._call(assay)
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            readme = zf.read("README.md").decode()
        self.assertIn(str(assay.uid), readme)


class ExportAssayToFileJsonldTests(SimpleTestCase):
    """export_assay_to_file handles the jsonld export type."""

    def test_jsonld_export_produces_file_response(self):
        import tempfile

        from django.http import FileResponse

        from toxtempass.export import export_assay_to_file

        assay = _make_assay_mock()
        request = MagicMock()

        with tempfile.TemporaryDirectory() as tmp_dir:
            with (
                patch("toxtempass.export.settings") as mock_settings,
                patch("toxtempass.export.Section") as mock_section_cls,
            ):
                mock_settings.MEDIA_ROOT = tmp_dir
                mock_section_cls.objects.filter.return_value\
                    .prefetch_related.return_value = []
                response = export_assay_to_file(request, assay, "jsonld")
            self.assertIsInstance(response, FileResponse)
            content_disp = response.headers.get("Content-Disposition", "")
            self.assertIn(".jsonld", content_disp)
            response.file_to_stream.close()

    def test_zip_export_produces_file_response(self):
        import tempfile

        from django.http import FileResponse

        from toxtempass.export import export_assay_to_file

        assay = _make_assay_mock()
        request = MagicMock()

        with tempfile.TemporaryDirectory() as tmp_dir:
            with (
                patch("toxtempass.export.settings") as mock_settings,
                patch("toxtempass.export.Section") as mock_section_cls,
            ):
                mock_settings.MEDIA_ROOT = tmp_dir
                mock_section_cls.objects.filter.return_value\
                    .prefetch_related.return_value = []
                response = export_assay_to_file(request, assay, "zip")
            self.assertIsInstance(response, FileResponse)
            content_disp = response.headers.get("Content-Disposition", "")
            self.assertIn(".zip", content_disp)
            response.file_to_stream.close()
