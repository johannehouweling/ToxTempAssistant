import base64
import os
import uuid
from pathlib import Path

import factory
from factory.django import DjangoModelFactory

from toxtempass.filehandling import get_text_or_bytes_perfile_dict
from toxtempass.models import Assay, Investigation, LLMStatus, Person, Study


class PersonFactory(DjangoModelFactory):
    class Meta:
        model = Person

    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    email = factory.LazyAttribute(
        lambda obj: "%s.%s@test.com" % (obj.first_name, obj.last_name)
    )


class InvestigationFactory(DjangoModelFactory):
    class Meta:
        model = Investigation

    owner = factory.SubFactory(PersonFactory)
    title = factory.Faker("sentence", locale="en_US", nb_words=6, variable_nb_words=True)
    description = factory.Faker(
        "sentence", locale="en_US", nb_words=20, variable_nb_words=True
    )


class StudyFactory(DjangoModelFactory):
    class Meta:
        model = Study

    investigation = factory.SubFactory(InvestigationFactory)
    title = factory.Faker("sentence", locale="en_US", nb_words=6, variable_nb_words=True)
    description = factory.Faker(
        "sentence", locale="en_US", nb_words=20, variable_nb_words=True
    )


class AssayFactory(DjangoModelFactory):
    class Meta:
        model = Assay

    study = factory.SubFactory(StudyFactory)
    title = factory.Faker("sentence", locale="en_US", nb_words=6, variable_nb_words=True)
    description = factory.Faker(
        "sentence", locale="en_US", nb_words=20, variable_nb_words=True
    )
    status = LLMStatus.NONE


class DocumentDictFactory(factory.Factory):
    class Meta:
        model = dict

    @classmethod
    def _create(
        cls,
        model_class,
        *args,
        num_text: int = 2,
        num_bytes: int = 1,
        document_filenames: list[Path | str] | None = None,
        unlink: bool = False,  # if by default we want to consume documents
        extract_images: bool = False,
        **kwargs,
    ) -> dict[str, dict[str, str]]:
        text_dict: dict[str, dict[str, str]] = {}

        # 1) If the user passed real files, load them first:
        if document_filenames:
            # Coerce to Path
            paths = [Path(p) for p in document_filenames]
            real_contents = get_text_or_bytes_perfile_dict(
                paths, unlink, extract_images=extract_images
            )
            text_dict.update(real_contents)
            # optionally re-raise or continue with dummy data

        # 2) Count how many real text vs. binary entries we already have:
        existing_text = sum(1 for v in text_dict.values() if "text" in v)
        existing_bytes = sum(1 for v in text_dict.values() if "encodedbytes" in v)

        # 3) Generate dummy text entries to hit num_text
        for _ in range(max(num_text - existing_text, 0)):
            entry = factory.build(
                dict,
                filename=f"{uuid.uuid4()}.txt",
                text=factory.Faker("text").evaluate(None, None, {"locale": "en_US"}),
            )
            text_dict[entry["filename"]] = {"text": entry["text"]}

        # 4) Generate dummy binary entries to hit num_bytes
        for _ in range(max(num_bytes - existing_bytes, 0)):
            entry = factory.build(
                dict,
                filename=f"{uuid.uuid4()}.bin",
                encodedbytes=base64.b64encode(os.urandom(10)).decode("utf-8"),
            )
            text_dict[entry["filename"]] = {"encodedbytes": entry["encodedbytes"]}

        return text_dict


class AdminFactory(PersonFactory):
    """Factory for admin users (superuser + staff)."""

    is_superuser = True
    is_staff = True
