"""Unit tests for the add_status_context utility helper."""

from unittest.mock import MagicMock

from django.test import SimpleTestCase

from toxtempass import config
from toxtempass.utilities import add_status_context


def _mock_assay(status_context: str = "") -> MagicMock:
    """Return a mock assay with a status_context attribute."""
    assay = MagicMock()
    assay.status_context = status_context
    return assay


class AddStatusContextPreambleTests(SimpleTestCase):
    """Preamble and format tests."""

    def test_error_preamble(self):
        assay = _mock_assay()
        add_status_context(assay, "something went wrong")
        self.assertIn("Error occurred: ", assay.status_context)
        self.assertIn("something went wrong", assay.status_context)
        # No double colon
        self.assertNotIn(": : ", assay.status_context)

    def test_info_preamble(self):
        assay = _mock_assay()
        add_status_context(assay, "task completed", is_error=False)
        self.assertIn("Info: ", assay.status_context)
        self.assertIn("task completed", assay.status_context)
        self.assertNotIn("Error occurred", assay.status_context)


class AddStatusContextAppendTests(SimpleTestCase):
    """Append vs clear_first behaviour."""

    def test_append_default(self):
        assay = _mock_assay(status_context="existing line")
        add_status_context(assay, "new entry")
        self.assertIn("existing line", assay.status_context)
        self.assertIn("new entry", assay.status_context)

    def test_clear_first(self):
        assay = _mock_assay(status_context="old entry that should disappear")
        add_status_context(assay, "fresh entry", clear_first=True)
        self.assertNotIn("old entry that should disappear", assay.status_context)
        self.assertIn("fresh entry", assay.status_context)

    def test_multiple_appends(self):
        assay = _mock_assay()
        add_status_context(assay, "first")
        add_status_context(assay, "second")
        add_status_context(assay, "third")
        ctx = assay.status_context
        self.assertIn("first", ctx)
        self.assertIn("second", ctx)
        self.assertIn("third", ctx)


class AddStatusContextTrimmingTests(SimpleTestCase):
    """Length-cap / trimming behaviour."""

    def test_short_message_not_trimmed(self):
        assay = _mock_assay()
        msg = "short"
        add_status_context(assay, msg)
        self.assertIn(msg, assay.status_context)
        self.assertLessEqual(len(assay.status_context), config.status_error_max_len)

    def test_trim_drops_oldest_lines(self):
        """With many old lines, oldest are dropped while newest is retained."""
        assay = _mock_assay()
        # Build an existing context exceeding the cap with dummy lines
        old_line = "old: " + "x" * 200
        old_context = "\n".join([old_line] * 40)  # ~8200 chars
        assay.status_context = old_context

        new_msg = "[corr1234] ImportantError: remember this"
        add_status_context(assay, new_msg)

        ctx = assay.status_context
        # Cap is enforced
        self.assertLessEqual(len(ctx), config.status_error_max_len)
        # Most recent entry is preserved
        self.assertIn(new_msg, ctx)

    def test_single_oversized_message_preserved(self):
        """If a single new_entry exceeds the cap it is still stored (truncated from start)."""
        assay = _mock_assay()
        long_msg = "x" * (config.status_error_max_len + 100)
        add_status_context(assay, long_msg)
        ctx = assay.status_context
        # Cap is enforced
        self.assertLessEqual(len(ctx), config.status_error_max_len)
        # Not empty
        self.assertTrue(ctx)
