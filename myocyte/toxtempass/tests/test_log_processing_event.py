"""Unit tests for the log_processing_event utility helper."""

from unittest.mock import MagicMock

from django.test import SimpleTestCase

from toxtempass import config
from toxtempass.utilities import log_processing_event


def _mock_assay(processing_log: str = "") -> MagicMock:
    """Return a mock assay with a processing_log attribute."""
    assay = MagicMock()
    assay.processing_log = processing_log
    return assay


class LogProcessingEventPreambleTests(SimpleTestCase):
    """Preamble and format tests."""

    def test_error_preamble(self):
        assay = _mock_assay()
        log_processing_event(assay, "something went wrong")
        self.assertIn("Error occurred: ", assay.processing_log)
        self.assertIn("something went wrong", assay.processing_log)
        # No double colon
        self.assertNotIn(": : ", assay.processing_log)

    def test_info_preamble(self):
        assay = _mock_assay()
        log_processing_event(assay, "task completed", is_error=False)
        self.assertIn("Info: ", assay.processing_log)
        self.assertIn("task completed", assay.processing_log)
        self.assertNotIn("Error occurred", assay.processing_log)


class LogProcessingEventAppendTests(SimpleTestCase):
    """Append vs clear_first behaviour."""

    def test_append_default(self):
        assay = _mock_assay(processing_log="existing line")
        log_processing_event(assay, "new entry")
        self.assertIn("existing line", assay.processing_log)
        self.assertIn("new entry", assay.processing_log)

    def test_clear_first(self):
        assay = _mock_assay(processing_log="old entry that should disappear")
        log_processing_event(assay, "fresh entry", clear_first=True)
        self.assertNotIn("old entry that should disappear", assay.processing_log)
        self.assertIn("fresh entry", assay.processing_log)

    def test_multiple_appends(self):
        assay = _mock_assay()
        log_processing_event(assay, "first")
        log_processing_event(assay, "second")
        log_processing_event(assay, "third")
        ctx = assay.processing_log
        self.assertIn("first", ctx)
        self.assertIn("second", ctx)
        self.assertIn("third", ctx)


class LogProcessingEventTrimmingTests(SimpleTestCase):
    """Length-cap / trimming behaviour."""

    def test_short_message_not_trimmed(self):
        assay = _mock_assay()
        msg = "short"
        log_processing_event(assay, msg)
        self.assertIn(msg, assay.processing_log)
        self.assertLessEqual(len(assay.processing_log), config.status_error_max_len)

    def test_trim_drops_oldest_lines(self):
        """With many old lines, oldest are dropped while newest is retained."""
        assay = _mock_assay()
        # Build an existing log exceeding the cap with dummy lines
        old_line = "old: " + "x" * 200
        old_log = "\n".join([old_line] * 40)  # ~8200 chars
        assay.processing_log = old_log

        new_msg = "[corr1234] ImportantError: remember this"
        log_processing_event(assay, new_msg)

        ctx = assay.processing_log
        # Cap is enforced
        self.assertLessEqual(len(ctx), config.status_error_max_len)
        # Most recent entry is preserved
        self.assertIn(new_msg, ctx)

    def test_single_oversized_message_preserved(self):
        """If a single new_entry exceeds the cap it is still stored (truncated from start)."""
        assay = _mock_assay()
        long_msg = "x" * (config.status_error_max_len + 100)
        log_processing_event(assay, long_msg)
        ctx = assay.processing_log
        # Cap is enforced
        self.assertLessEqual(len(ctx), config.status_error_max_len)
        # Not empty
        self.assertTrue(ctx)
