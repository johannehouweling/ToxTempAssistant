import base64
import pytest

from toxtempass.filehandling import split_doc_dict_by_type
from toxtempass.tests.fixtures.factories import DocumentDictFactory


def test_split_doc_dict_by_type_decodes():
    """split_doc_dict_by_type should separate text and base64-encoded bytes and decode bytes when requested."""
    docdict = DocumentDictFactory(num_text=2, num_bytes=2)

    text_dict, bytes_dict = split_doc_dict_by_type(docdict, decode=True)

    # All entries that had 'text' should be in text_dict
    assert all("text" in v for v in text_dict.values())
    # All entries that had 'encodedbytes' should be decoded into 'bytes' in bytes_dict
    assert all("bytes" in v for v in bytes_dict.values())
    # Ensure decoded bytes are of bytes type
    for v in bytes_dict.values():
        assert isinstance(v["bytes"], (bytes, bytearray))


def test_split_doc_dict_by_type_no_decode():
    """When decode=False, encodedbytes entries should be preserved as-is in the bytes dict."""
    docdict = DocumentDictFactory(num_text=1, num_bytes=1)

    text_dict, bytes_dict = split_doc_dict_by_type(docdict, decode=False)

    # text entries remain the same
    assert any("text" in v for v in text_dict.values())
    # bytes_dict should contain the original 'encodedbytes' entries
    assert any("encodedbytes" in v for v in bytes_dict.values())
