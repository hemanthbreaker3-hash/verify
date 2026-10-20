import main
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from plugins.help import (
    ALL_COMMANDS,
    COMMANDS_PER_PAGE,
    TOTAL_COMMANDS,
    TOTAL_PAGES,
    get_help_page_content,
    help_command,
    help_page_callback,
)

class TestHelpMenu(unittest.IsolatedAsyncioTestCase):
    def test_commands_alphabetical_order(self):
        cmd_names = [c["cmd"].lower() for c in ALL_COMMANDS]
        sorted_cmd_names = sorted(cmd_names)
        self.assertEqual(cmd_names, sorted_cmd_names)

    def test_command_fields(self):
        for item in ALL_COMMANDS:
            self.assertIn("cmd", item)
            self.assertIn("desc", item)
            self.assertIn("usage", item)
            self.assertIn("example", item)
            self.assertTrue(item["cmd"].startswith("/"))

    def test_pagination_bounds(self):
        text_p1, markup_p1 = get_help_page_content(1)
        self.assertIn("Page:</b> <code>1/", text_p1)
        self.assertIn("AniZoneFlix", text_p1)

        text_last, markup_last = get_help_page_content(TOTAL_PAGES)
        self.assertIn(f"Page:</b> <code>{TOTAL_PAGES}/", text_last)

    @patch("plugins.help.get_next_image", return_value="test.jpg")
    async def test_help_command(self, mock_img):
        msg = MagicMock()
        msg.chat.id = 12345
        msg.reply_photo = AsyncMock()

        client = MagicMock()

        await help_command(client, msg)

        msg.reply_photo.assert_called_once()
        _, kwargs = msg.reply_photo.call_args
        self.assertIn("AniZoneFlix", kwargs["caption"])

    async def test_help_page_callback(self):
        cb = MagicMock()
        cb.matches = [MagicMock()]
        cb.matches[0].group.return_value = "2"
        cb.answer = AsyncMock()
        cb.message.edit_caption = AsyncMock()

        client = MagicMock()

        await help_page_callback(client, cb)

        cb.answer.assert_called_once()
        cb.message.edit_caption.assert_called_once()
        _, kwargs = cb.message.edit_caption.call_args
        self.assertIn("Page:</b> <code>2/", kwargs["caption"])

if __name__ == "__main__":
    unittest.main()
