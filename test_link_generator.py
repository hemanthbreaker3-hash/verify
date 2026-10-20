import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

# Import main to ensure InlineKeyboardButton monkey-patching is applied
import main

from plugins.link_generator import extract_file_info, batch, link_generator

class TestLinkGeneratorBatch(unittest.TestCase):

    def test_extract_file_info_with_media_and_caption(self):
        msg = MagicMock()
        media = MagicMock()
        media.file_name = "naruto_ep01.mkv"
        msg.document = media
        msg.video = None
        msg.audio = None
        msg.animation = None

        caption_mock = MagicMock()
        caption_mock.html = "<b>Naruto Episode 1</b>"
        msg.caption = caption_mock

        filename, filecaption = extract_file_info(msg)
        self.assertEqual(filename, "naruto_ep01.mkv")
        self.assertEqual(filecaption, "<b>Naruto Episode 1</b>")

    def test_extract_file_info_missing_media_or_caption(self):
        msg = MagicMock()
        msg.document = None
        msg.video = None
        msg.audio = None
        msg.animation = None
        msg.photo = None
        msg.voice = None
        msg.caption = None

        filename, filecaption = extract_file_info(msg)
        self.assertEqual(filename, "N/A")
        self.assertEqual(filecaption, "N/A")

    def test_batch_command_output_formatting(self):
        async def run_test():
            client = MagicMock()
            client.db_channel.id = -1001234567890

            with patch("plugins.link_generator.check_admin_or_owner", new_callable=AsyncMock) as mock_auth, \
                 patch("plugins.link_generator.get_message_id", new_callable=AsyncMock) as mock_msg_id, \
                 patch("plugins.link_generator.get_messages", new_callable=AsyncMock) as mock_get_msgs, \
                 patch("plugins.link_generator.get_bot_username", new_callable=AsyncMock) as mock_bot_user:

                mock_auth.return_value = True
                mock_msg_id.side_effect = [10, 20]
                mock_bot_user.return_value = "TestBot"

                first_ask_resp = MagicMock()
                second_ask_resp = MagicMock()
                second_ask_resp.reply_text = AsyncMock()
                client.ask = AsyncMock(side_effect=[first_ask_resp, second_ask_resp])

                f_msg = MagicMock()
                f_msg.id = 10
                f_media = MagicMock()
                f_media.file_name = "Episode_10.mkv"
                f_msg.document = f_media
                f_msg.video = None
                f_msg.audio = None
                f_msg.animation = None
                f_cap = MagicMock()
                f_cap.html = "Caption 10"
                f_msg.caption = f_cap

                s_msg = MagicMock()
                s_msg.id = 20
                s_media = MagicMock()
                s_media.file_name = "Episode_20.mkv"
                s_msg.document = s_media
                s_msg.video = None
                s_msg.audio = None
                s_msg.animation = None
                s_cap = MagicMock()
                s_cap.html = "Caption 20"
                s_msg.caption = s_cap

                mock_get_msgs.return_value = [f_msg, s_msg]

                message = MagicMock()
                message.from_user.id = 12345
                await batch(client, message)

                second_ask_resp.reply_text.assert_called_once()
                call_args = second_ask_resp.reply_text.call_args
                output_text = call_args[0][0]

                self.assertIn("<b>First Filename:</b> Episode_10.mkv", output_text)
                self.assertIn("<b>First Caption:</b> Caption 10", output_text)
                self.assertIn("<b>Last Filename:</b> Episode_20.mkv", output_text)
                self.assertIn("<b>Last Caption:</b> Caption 20", output_text)
                self.assertIn("<b>Here is your link:</b>", output_text)
                self.assertIn("<code>https://telegram.me/TestBot?start=", output_text)

        asyncio.run(run_test())

    def test_genlink_direct_link_argument(self):
        async def run_test():
            client = MagicMock()
            client.db_channel.id = -1001234567890

            message = MagicMock()
            message.from_user.id = 12345
            message.command = ["genlink", "https://t.me/hsjisksjs/23961"]
            message.text = "/genlink https://t.me/hsjisksjs/23961"
            message.reply_to_message = None
            message.reply_text = AsyncMock()

            target_db_msg = MagicMock()
            target_db_msg.id = 23961
            doc_media = MagicMock()
            doc_media.file_name = "Single_Movie.mkv"
            target_db_msg.document = doc_media
            target_db_msg.video = None
            target_db_msg.audio = None
            target_db_msg.animation = None
            target_cap = MagicMock()
            target_cap.html = "Movie Caption"
            target_db_msg.caption = target_cap

            with patch("plugins.link_generator.check_admin_or_owner", new_callable=AsyncMock) as mock_auth, \
                 patch("plugins.link_generator.get_messages", new_callable=AsyncMock) as mock_get_msgs, \
                 patch("plugins.link_generator.get_bot_username", new_callable=AsyncMock) as mock_bot_user:

                mock_auth.return_value = True
                mock_bot_user.return_value = "TestBot"
                mock_get_msgs.return_value = [target_db_msg]

                await link_generator(client, message)

                message.reply_text.assert_called_once()
                call_args = message.reply_text.call_args
                output_text = call_args[0][0]

                self.assertIn("<b>First Filename:</b> Single_Movie.mkv", output_text)
                self.assertIn("<b>First Caption:</b> Movie Caption", output_text)
                self.assertIn("<b>Last Filename:</b> Single_Movie.mkv", output_text)
                self.assertIn("<b>Last Caption:</b> Movie Caption", output_text)
                self.assertIn("<b>Here is your link:</b>", output_text)

        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main()
