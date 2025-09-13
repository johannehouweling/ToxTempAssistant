import base64
import pytest

from toxtempass.tests.fixtures.factories import DocumentDictFactory


def test_documentdictfactory_generates_entries():
    """DocumentDictFactory should produce a mapping of filenames -> dict entries
    where each entry contains either 'text' or 'encodedbytes'."""
    docdict = DocumentDictFactory()
    assert isinstance(docdict, dict)
    assert len(docdict) > 0

    has_text = False
    has_bytes = False
    for filename, entry in docdict.items():
        assert isinstance(filename, str)
        assert isinstance(entry, dict)
        # Each entry must contain at least one of the expected keys
        assert "text" in entry or "encodedbytes" in entry

        if "text" in entry:
            has_text = True
            assert isinstance(entry["text"], str)
            assert entry["text"].strip() != ""

        if "encodedbytes" in entry:
            has_bytes = True
            # encodedbytes should be base64-decoded cleanly
            assert isinstance(entry["encodedbytes"], str)
            decoded = base64.b64decode(entry["encodedbytes"])
            assert isinstance(decoded, (bytes, bytearray))

    # Ensure we got at least one of each type by default (factory default: num_text=2, num_bytes=1)
    assert has_text
    assert has_bytes


def test_documentdictfactory_respects_counts():
    """When given explicit counts, factory should return the requested number of text/binary entries."""
    requested_text = 3
    requested_bytes = 2
    docdict = DocumentDictFactory(num_text=requested_text, num_bytes=requested_bytes)

    count_text = sum(1 for v in docdict.values() if "text" in v)
    count_bytes = sum(1 for v in docdict.values() if "encodedbytes" in v)

    assert count_text == requested_text
    assert count_bytes == requested_bytes
