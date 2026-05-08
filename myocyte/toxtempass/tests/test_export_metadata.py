"""Tests for export author metadata."""

import tempfile
from pathlib import Path
from types import SimpleNamespace

import yaml
from django.test import TestCase

from toxtempass.export import get_create_meta_data_yaml
from toxtempass.tests.fixtures.factories import AnswerFactory, AssayFactory, PersonFactory


class ExportMetadataAuthorTests(TestCase):
    """Export YAML metadata includes a flat ordered author list."""

    def _save_answer_with_user(
        self,
        answer,
        *,
        user,
        answer_text: str | None = None,
        accepted: bool | None = None,
    ) -> None:
        if answer_text is not None:
            answer.answer_text = answer_text
        if accepted is not None:
            answer.accepted = accepted
        answer._history_user = user
        answer.save()

    def test_metadata_lists_creator_then_contributors_then_owner(self):
        owner = PersonFactory(first_name="Owner", last_name="Person")
        creator = PersonFactory(first_name="Creator", last_name="Author")
        contributor_one = PersonFactory(first_name="Alice", last_name="Editor")
        contributor_two = PersonFactory(first_name="Bob", last_name="Reviewer")
        exporter = PersonFactory(first_name="Exporter", last_name="Only")
        assay = AssayFactory(study__investigation__owner=owner, created_by=creator)

        answer_one = AnswerFactory(
            assay=assay,
            answer_text="draft",
            question__subsection__section__question_set__label="authtrk1",
        )

        self._save_answer_with_user(
            answer_one,
            user=contributor_one,
            answer_text="edited once",
        )
        self._save_answer_with_user(
            answer_one,
            user=contributor_one,
            accepted=True,
        )
        self._save_answer_with_user(
            answer_one,
            user=contributor_two,
            answer_text="edited twice",
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            yaml_path = get_create_meta_data_yaml(
                SimpleNamespace(user=exporter),
                assay,
                file_path=Path(tmp_dir) / "toxtemp.pdf",
            )
            metadata = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))

        self.assertEqual(
            metadata["author"],
            [
                "Creator Author",
                "Alice Editor",
                "Bob Reviewer",
                "Owner Person",
            ],
        )
        self.assertNotIn("main_author", metadata)
        self.assertNotIn("co_authors", metadata)
        self.assertNotIn("Exporter Only", metadata["author"])

    def test_owner_is_listed_once_and_first_when_creator_matches_owner(self):
        owner = PersonFactory(first_name="Owner", last_name="Creator")
        contributor = PersonFactory(first_name="Middle", last_name="Editor")
        assay = AssayFactory(study__investigation__owner=owner, created_by=owner)

        answer = AnswerFactory(
            assay=assay,
            answer_text="draft",
            question__subsection__section__question_set__label="ownerdedup",
        )
        self._save_answer_with_user(answer, user=owner, answer_text="owner edit")
        self._save_answer_with_user(
            answer,
            user=contributor,
            answer_text="contributor edit",
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            yaml_path = get_create_meta_data_yaml(
                SimpleNamespace(user=owner),
                assay,
                file_path=Path(tmp_dir) / "toxtemp.pdf",
            )
            metadata = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))

        self.assertEqual(metadata["author"], ["Owner Creator", "Middle Editor"])
        self.assertNotIn("main_author", metadata)
        self.assertNotIn("co_authors", metadata)
