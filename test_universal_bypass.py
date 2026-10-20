import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from plugins.universal_bypass import (
    extract_raw_input_text,
    extract_target_and_referer,
    is_bypass_message,
    resolve_universal,
    run_universal_bypass,
    upload_to_spacebin,
    universal_bypass_handler,
)

class DummyEntity:
    def __init__(self, type_name, url=None, offset=0, length=0):
        self.type = MagicMock()
        self.type.name = type_name
        self.url = url
        self.offset = offset
        self.length = length

class DummyMessage:
    def __init__(self, text="", caption="", entities=None, caption_entities=None):
        self.text = text
        self.caption = caption
        self.entities = entities or []
        self.caption_entities = caption_entities or []
        self.replied_text = None
        self.edited_text = None

    async def reply_text(self, text, quote=True):
        self.replied_text = text
        return self

    async def edit(self, text, disable_web_page_preview=False):
        self.edited_text = text
        return self

class TestUniversalBypassFilter(unittest.TestCase):
    def test_filter_matches(self):
        msg1 = DummyMessage(text="https://domain.com=https://target.com")
        self.assertTrue(is_bypass_message(None, None, msg1))

        msg2 = DummyMessage(text="domain.com=target.com")
        self.assertTrue(is_bypass_message(None, None, msg2))

        msg3 = DummyMessage(text="https://domain.com/links?nicktrick=https://target.com")
        self.assertTrue(is_bypass_message(None, None, msg3))

        msg4 = DummyMessage(text="short4cash.com/links?nicktrick=target.com")
        self.assertTrue(is_bypass_message(None, None, msg4))

    def test_filter_hyperlinks(self):
        entity = DummyEntity("TEXT_LINK", url="short4cash.com/links?nicktrick=https://target.com")
        msg = DummyMessage(text="Click Here", entities=[entity])
        self.assertTrue(is_bypass_message(None, None, msg))
        self.assertEqual(extract_raw_input_text(msg), "short4cash.com/links?nicktrick=https://target.com")

    def test_filter_non_matches(self):
        msg1 = DummyMessage(text="/start")
        self.assertFalse(is_bypass_message(None, None, msg1))

        msg2 = DummyMessage(text="hello world")
        self.assertFalse(is_bypass_message(None, None, msg2))

        msg3 = DummyMessage(text="https://google.com")
        self.assertFalse(is_bypass_message(None, None, msg3))

class TestTargetRefererExtraction(unittest.TestCase):
    def test_extract_equal_format(self):
        target, referer = extract_target_and_referer("https://domain.com=https://target.com")
        self.assertEqual(target, "https://target.com")
        self.assertEqual(referer, "https://domain.com")

    def test_extract_equal_format_no_scheme(self):
        target, referer = extract_target_and_referer("domain.com=target.com")
        self.assertEqual(target, "https://target.com")
        self.assertEqual(referer, "https://domain.com")

    def test_extract_query_param(self):
        target, referer = extract_target_and_referer("https://domain.com/path?url=https://target.com")
        self.assertEqual(target, "https://target.com")
        self.assertEqual(referer, "https://domain.com/")

    def test_extract_custom_domain_query_param(self):
        target, referer = extract_target_and_referer("short4cash.com/links?nicktrick=https://target.com")
        self.assertEqual(target, "https://target.com")
        self.assertEqual(referer, "https://short4cash.com/")

class TestPurePythonBypass(unittest.IsolatedAsyncioTestCase):
    @patch("requests.get")
    def test_resolve_universal_redirect(self, mock_get):
        resp1 = MagicMock()
        resp1.status_code = 301
        resp1.headers = {"location": "https://finaldest.com"}

        resp2 = MagicMock()
        resp2.status_code = 200
        resp2.headers = {}

        mock_get.side_effect = [resp1, resp2]

        final_url = resolve_universal("https://domain.com=https://target.com", "https://domain.com")
        self.assertEqual(final_url, "https://finaldest.com")

    @patch("plugins.universal_bypass.run_universal_bypass")
    async def test_handler_success(self, mock_bypass):
        mock_bypass.return_value = "https://finaldest.com"

        msg = DummyMessage(text="https://domain.com=https://target.com")
        client = MagicMock()

        await universal_bypass_handler(client, msg)

        self.assertIsNotNone(msg.replied_text)
        self.assertIn("Resolving URL", msg.replied_text)
        self.assertIsNotNone(msg.edited_text)
        self.assertIn("Universal Bypass Success", msg.edited_text)
        self.assertIn("https://finaldest.com", msg.edited_text)

    @patch("plugins.universal_bypass.upload_to_spacebin")
    @patch("plugins.universal_bypass.run_universal_bypass")
    async def test_handler_spacebin(self, mock_bypass, mock_upload):
        long_url = "https://finaldest.com/" + ("x" * 2100)
        mock_bypass.return_value = long_url
        mock_upload.return_value = "https://spaceb.in/doc123"

        msg = DummyMessage(text="https://domain.com=https://target.com")
        client = MagicMock()

        await universal_bypass_handler(client, msg)

        self.assertIsNotNone(msg.edited_text)
        self.assertIn("Spacebin Link", msg.edited_text)
        self.assertIn("https://spaceb.in/doc123", msg.edited_text)

if __name__ == "__main__":
    unittest.main()
