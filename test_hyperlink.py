import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from plugins.hyperlink import (
    HYPERLINK_SESSIONS,
    HYPERLINK_FILTER_SESSIONS,
    hyperlink_cmd,
    collect_hyperlinks_handler,
    filter_hyperlinks_handler,
)

class TestHyperlinkFlow(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.check_patcher = patch("plugins.hyperlink.check_admin_or_owner", AsyncMock(return_value=True))
        self.check_patcher.start()

    def tearDown(self):
        self.check_patcher.stop()

        HYPERLINK_SESSIONS.clear()
        HYPERLINK_FILTER_SESSIONS.clear()

    async def test_hyperlink_flow_with_skip(self):
        msg = MagicMock()
        msg.from_user.id = 12345
        msg.reply_text = AsyncMock()

        # Step 1: /hyperlink command
        await hyperlink_cmd(MagicMock(), msg)
        self.assertIn(12345, HYPERLINK_SESSIONS)

        # Step 2: collect message with TEXT_LINK entity
        collect_msg = MagicMock()
        collect_msg.from_user.id = 12345
        collect_msg.text = "Click Download 720p here"
        collect_msg.caption = None

        entity = MagicMock()
        entity.type.name = "TEXT_LINK"
        entity.url = "https://example.com/720p"
        entity.offset = 6
        entity.length = 13  # "Download 720p"
        collect_msg.entities = [entity]
        collect_msg.caption_entities = None

        await collect_hyperlinks_handler(MagicMock(), collect_msg)
        self.assertEqual(len(HYPERLINK_SESSIONS[12345]), 1)
        self.assertEqual(HYPERLINK_SESSIONS[12345][0]["label"], "Download 720p")

        # Step 3: send /done
        done_msg = MagicMock()
        done_msg.from_user.id = 12345
        done_msg.text = "/done"
        done_msg.caption = None
        done_msg.reply_text = AsyncMock()

        await collect_hyperlinks_handler(MagicMock(), done_msg)
        self.assertNotIn(12345, HYPERLINK_SESSIONS)
        self.assertIn(12345, HYPERLINK_FILTER_SESSIONS)

        # Step 4: send /skip
        skip_msg = MagicMock()
        skip_msg.from_user.id = 12345
        skip_msg.text = "/skip"
        skip_msg.caption = None
        skip_msg.reply_text = AsyncMock()

        await filter_hyperlinks_handler(MagicMock(), skip_msg)
        self.assertNotIn(12345, HYPERLINK_FILTER_SESSIONS)
        skip_msg.reply_text.assert_called_once_with("https://example.com/720p", disable_web_page_preview=True)

    async def test_hyperlink_flow_with_comma_filter(self):
        msg = MagicMock()
        msg.from_user.id = 999
        msg.reply_text = AsyncMock()

        await hyperlink_cmd(MagicMock(), msg)

        # Collect 2 links
        HYPERLINK_SESSIONS[999] = [
            {"label": "Download 480p", "url": "https://example.com/480p"},
            {"label": "Download 1080p", "url": "https://example.com/1080p"},
        ]

        # Send /done
        done_msg = MagicMock()
        done_msg.from_user.id = 999
        done_msg.text = "/done"
        done_msg.caption = None
        done_msg.reply_text = AsyncMock()
        await collect_hyperlinks_handler(MagicMock(), done_msg)

        # Filter by "1080p"
        filter_msg = MagicMock()
        filter_msg.from_user.id = 999
        filter_msg.text = "1080p"
        filter_msg.caption = None
        filter_msg.reply_text = AsyncMock()

        await filter_hyperlinks_handler(MagicMock(), filter_msg)
        self.assertNotIn(999, HYPERLINK_FILTER_SESSIONS)
        filter_msg.reply_text.assert_called_once_with("https://example.com/1080p", disable_web_page_preview=True)

if __name__ == "__main__":
    unittest.main()
