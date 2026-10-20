import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import main
from helper_func import encode, decode
from helper_func import get_readable_time
from plugins.panel import parse_duration_string
from plugins.hyperlink import HYPERLINK_SESSIONS
from plugins.autobatch import parse_mixed_inputs, resolve_db_source, generate_list_link, clean_emojis_and_html, parse_metadata_universal, detect_quality, state_manager, AUTO_BATCH_QUEUES, serielbatch_command
from plugins.admin import delete_content_command
from plugins.start import start_command
from database.database import db

class TestAdvbatchAndSystem(unittest.TestCase):

    def test_parse_mixed_inputs_format_a(self):
        # Format A: https://t.me/c/1234567890/100-https://t.me/c/1234567890/200
        text = "https://t.me/c/1234567890/100-https://t.me/c/1234567890/200"
        parsed = parse_mixed_inputs(text)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]['channel'], "1234567890")
        self.assertEqual(parsed[0]['start_id'], 100)
        self.assertEqual(parsed[0]['end_id'], 200)

    def test_parse_mixed_inputs_format_b(self):
        # Format B: https://t.me/c/1234567890/100-200
        text = "https://t.me/c/1234567890/100-200"
        parsed = parse_mixed_inputs(text)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]['channel'], "1234567890")
        self.assertEqual(parsed[0]['start_id'], 100)
        self.assertEqual(parsed[0]['end_id'], 200)

    def test_parse_mixed_inputs_inverted_range(self):
        text = "https://t.me/c/1234567890/200-100"
        parsed = parse_mixed_inputs(text)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]['start_id'], 100)
        self.assertEqual(parsed[0]['end_id'], 200)

    def test_resolve_db_source(self):
        async def run_test():
            main_client = MagicMock()
            main_client.username = "MainBot"

            with patch.object(db, 'get_db_channels', new_callable=AsyncMock) as mock_sec, \
                 patch.object(db, 'get_all_clones', new_callable=AsyncMock) as mock_clones:

                mock_sec.return_value = [-1009876543210]
                mock_clones.return_value = [
                    {'bot_username': 'CloneBot1', 'bot_token': '123:abc', 'db_channel_id': -1005555555555, 'enabled': True}
                ]

                # Resolve main channel
                cid, bot_un, cli = await resolve_db_source(main_client, None)
                self.assertEqual(bot_un, "mainbot")

                # Resolve clone channel by ID
                cid, bot_un, cli = await resolve_db_source(main_client, "5555555555")
                self.assertEqual(cid, -1005555555555)
                self.assertEqual(bot_un, "clonebot1")

                # Resolve clone channel by username
                cid, bot_un, cli = await resolve_db_source(main_client, "CloneBot1")
                self.assertEqual(cid, -1005555555555)
                self.assertEqual(bot_un, "clonebot1")

        asyncio.run(run_test())

    def test_generate_and_decode_link(self):
        async def run_test():
            client = MagicMock()
            client.username = "TestBot"
            channel_id = -1001234567890
            mids = [10, 15, 20]

            link = await generate_list_link(client, channel_id, mids, bot_username="TestBot")
            self.assertIn("https://telegram.me/TestBot?start=", link)

            # Decode token and verify start.py logic
            payload_token = link.split("start=")[1]
            decoded_string = await decode(payload_token)
            self.assertTrue(decoded_string.startswith("get-"))

            parts = decoded_string.split("-")
            val1 = int(parts[1])
            val2 = int(parts[2])

            divisor = abs(channel_id)
            self.assertEqual(val1 % divisor, 0)
            self.assertEqual(val2 % divisor, 0)
            self.assertEqual(val1 // divisor, 10)
            self.assertEqual(val2 // divisor, 20)

        asyncio.run(run_test())

    def test_state_and_queue_isolation(self):
        state_manager.set_state("mainbot", 123, "advbatch", "data_main")
        state_manager.set_state("clonebot1", 123, "advbatch", "data_clone")

        self.assertEqual(state_manager.get_state("mainbot", 123), "data_main")
        self.assertEqual(state_manager.get_state("clonebot1", 123), "data_clone")

        AUTO_BATCH_QUEUES["mainbot"].append({"task": 1})
        AUTO_BATCH_QUEUES["clonebot1"].append({"task": 2})

        self.assertEqual(len(AUTO_BATCH_QUEUES["mainbot"]), 1)
        self.assertEqual(len(AUTO_BATCH_QUEUES["clonebot1"]), 1)
        self.assertEqual(AUTO_BATCH_QUEUES["mainbot"][0]["task"], 1)
        self.assertEqual(AUTO_BATCH_QUEUES["clonebot1"][0]["task"], 2)

    def test_clean_and_metadata_parsing(self):
        cleaned = clean_emojis_and_html("Naruto.Shippuden.[1080p].S01E05.mkv")
        self.assertEqual(cleaned, "Naruto Shippuden 1080p S01E05 mkv")

        season, ep, num_type = parse_metadata_universal(cleaned)
        self.assertEqual(season, 1)
        self.assertEqual(ep, 5)
        self.assertEqual(num_type, 'episode')

        q = detect_quality(cleaned)
        self.assertEqual(q, "1080P")

    def test_readable_time_and_duration_parsing(self):
        # Test parse_duration_string
        self.assertEqual(parse_duration_string("365 days"), 365 * 86400)
        self.assertEqual(parse_duration_string("7 days"), 7 * 86400)
        self.assertEqual(parse_duration_string("1 year"), 365 * 86400)
        self.assertEqual(parse_duration_string("1 hour"), 3600)

        # Test get_readable_time formatting
        self.assertEqual(get_readable_time(365 * 86400), "365d")
        self.assertEqual(get_readable_time(7 * 86400), "7d")
        self.assertEqual(get_readable_time(3600), "1h")
        self.assertEqual(get_readable_time(5 * 86400 + 3 * 3600 + 120 + 5), "5d 3h 2m 5s")

    def test_hyperlink_session_and_extraction(self):
        # Test HYPERLINK_SESSIONS store
        user_id = 99999
        HYPERLINK_SESSIONS[user_id] = ["https://t.me/test1", "https://t.me/test2", "https://t.me/test1"]

        # De-duplication logic
        urls = HYPERLINK_SESSIONS.pop(user_id, [])
        seen = set()
        unique = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique.append(u)

        self.assertEqual(len(unique), 2)
        self.assertEqual(unique, ["https://t.me/test1", "https://t.me/test2"])

    def test_clone_bot_db_channel_range_examples(self):
        async def run_test():
            main_client = MagicMock()
            main_client.username = "MainBot"

            with patch.object(db, 'get_db_channels', new_callable=AsyncMock) as mock_sec, \
                 patch.object(db, 'get_all_clones', new_callable=AsyncMock) as mock_clones:

                mock_sec.return_value = []
                mock_clones.return_value = [
                    {'bot_username': 'CloneBot1', 'db_channel_id': -1003903003195, 'enabled': True},
                    {'bot_username': 'CloneBot2', 'db_channel_id': -1004491781113, 'enabled': True},
                    {'bot_username': 'CloneBot3', 'db_channel_id': -1004446716010, 'enabled': True}
                ]

                # Test example 1: https://t.me/c/3903003195/19790-19819
                parsed1 = parse_mixed_inputs("https://t.me/c/3903003195/19790-19819")
                cid1, bot_un1, _ = await resolve_db_source(main_client, parsed1[0]['channel'])
                self.assertEqual(cid1, -1003903003195)
                self.assertEqual(bot_un1, "clonebot1")

                # Test example 2: https://t.me/c/4491781113/20400-20429
                parsed2 = parse_mixed_inputs("https://t.me/c/4491781113/20400-20429")
                cid2, bot_un2, _ = await resolve_db_source(main_client, parsed2[0]['channel'])
                self.assertEqual(cid2, -1004491781113)
                self.assertEqual(bot_un2, "clonebot2")

                # Test example 3: https://t.me/c/4446716010/39722-39751
                parsed3 = parse_mixed_inputs("https://t.me/c/4446716010/39722-39751")
                cid3, bot_un3, _ = await resolve_db_source(main_client, parsed3[0]['channel'])
                self.assertEqual(cid3, -1004446716010)
                self.assertEqual(bot_un3, "clonebot3")

        asyncio.run(run_test())

    def test_invalid_base64_decode_error_handling(self):
        async def run_test():
            # 13 character invalid base64 string from the error log
            invalid_b64 = "invalid_b64_13"
            with self.assertRaises(ValueError):
                await decode(invalid_b64)

        asyncio.run(run_test())

    def test_database_clone_methods(self):
        async def run_db_test():
            if db.database is None:
                return # Skip live MongoDB call if DB not connected

            await db.add_clone("TestClone", "token123", -100111222333)
            c = await db.get_clone("TestClone")
            if c:
                self.assertEqual(c['bot_username'], "TestClone")
                self.assertEqual(c['db_channel_id'], -100111222333)

                await db.update_clone("TestClone", {'db_channel_id': -100444555666})
                c_updated = await db.get_clone("TestClone")
                self.assertEqual(c_updated['db_channel_id'], -100444555666)

                await db.delete_clone("TestClone")
                c_deleted = await db.get_clone("TestClone")
                self.assertIsNone(c_deleted)

        asyncio.run(run_db_test())

    def test_delete_command_per_bot_admin_and_db_channel(self):
        async def run_test():
            # Create two different bot instances with different db channels
            client_bot1 = MagicMock()
            client_bot1.username = "BotOne"
            class ChannelObj1:
                id = -1001111111111
            client_bot1.db_channel = ChannelObj1()
            client_bot1.delete_messages = AsyncMock()

            client_bot2 = MagicMock()
            client_bot2.username = "BotTwo"
            class ChannelObj2:
                id = -1002222222222
            client_bot2.db_channel = ChannelObj2()
            client_bot2.delete_messages = AsyncMock()

            # Non-admin user message
            msg_non_admin = MagicMock()
            msg_non_admin.from_user.id = 999
            msg_non_admin.text = "/delete 10"

            with patch("plugins.admin.check_admin_or_owner", new_callable=AsyncMock) as mock_auth:
                mock_auth.return_value = False
                await delete_content_command(client_bot1, msg_non_admin)
                client_bot1.delete_messages.assert_not_called()

            # Admin user message for bot 1 (range deletion: 10-12)
            msg_admin_b1 = MagicMock()
            msg_admin_b1.from_user.id = 123
            msg_admin_b1.reply_to_message = None
            msg_admin_b1.text = "/delete 10-12"
            pro_msg_b1 = MagicMock()
            pro_msg_b1.edit = AsyncMock()
            msg_admin_b1.reply = AsyncMock(return_value=pro_msg_b1)

            with patch("plugins.admin.check_admin_or_owner", new_callable=AsyncMock) as mock_auth, \
                 patch("plugins.admin.get_message_id", new_callable=AsyncMock) as mock_get_msg_id:
                mock_auth.return_value = True
                mock_get_msg_id.return_value = 0
                await delete_content_command(client_bot1, msg_admin_b1)
                # Ensure deleted specifically from client_bot1's DB channel
                client_bot1.delete_messages.assert_called_once_with(chat_id=-1001111111111, message_ids=[10, 11, 12])
                client_bot2.delete_messages.assert_not_called()

            # Admin user message for bot 2 (single ID deletion: 50)
            msg_admin_b2 = MagicMock()
            msg_admin_b2.from_user.id = 123
            msg_admin_b2.reply_to_message = None
            msg_admin_b2.text = "/delete 50"
            pro_msg_b2 = MagicMock()
            pro_msg_b2.edit = AsyncMock()
            msg_admin_b2.reply = AsyncMock(return_value=pro_msg_b2)

            with patch("plugins.admin.check_admin_or_owner", new_callable=AsyncMock) as mock_auth, \
                 patch("plugins.admin.get_message_id", new_callable=AsyncMock) as mock_get_msg_id:
                mock_auth.return_value = True
                mock_get_msg_id.return_value = 0
                await delete_content_command(client_bot2, msg_admin_b2)
                # Ensure deleted specifically from client_bot2's DB channel
                client_bot2.delete_messages.assert_called_once_with(chat_id=-1002222222222, message_ids=[50])

        asyncio.run(run_test())

    def test_start_delivery_with_deleted_db_content(self):
        async def run_test():
            client = MagicMock()
            client.username = "TestBot"
            class ChannelObj:
                id = -1001234567890
            client.db_channel = ChannelObj()

            # Generate payload token for message IDs 10, 11, 12
            divisor = abs(client.db_channel.id)
            string = f"get-{10 * divisor}-{12 * divisor}"
            base64_string = await encode(string)

            msg = MagicMock()
            msg.from_user.id = 555
            msg.from_user.first_name = "User"
            msg.text = f"/start {base64_string}"
            temp_msg = MagicMock()
            temp_msg.delete = AsyncMock()
            msg.reply = AsyncMock(return_value=temp_msg)
            msg.reply_text = AsyncMock()

            # Create DB messages where msg 11 was deleted (returns empty/None message)
            m10 = MagicMock()
            m10.id = 10
            m10.empty = False
            m10.video = None
            m10.caption = "Episode 10"
            m10.reply_markup = None
            m10.copy = AsyncMock(return_value=MagicMock())

            m11_deleted = MagicMock()
            m11_deleted.id = 11
            m11_deleted.empty = True

            m12 = MagicMock()
            m12.id = 12
            m12.empty = False
            m12.video = None
            m12.caption = "Episode 12"
            m12.reply_markup = None
            m12.copy = AsyncMock(return_value=MagicMock())

            with patch("plugins.start.is_subscribed", new_callable=AsyncMock) as mock_sub, \
                 patch("plugins.start.get_messages", new_callable=AsyncMock) as mock_get_msgs, \
                 patch.object(db, "get_ban_users", new_callable=AsyncMock) as mock_ban, \
                 patch.object(db, "present_user", new_callable=AsyncMock) as mock_pres, \
                 patch.object(db, "is_premium_user", new_callable=AsyncMock) as mock_prem, \
                 patch.object(db, "get_del_timer", new_callable=AsyncMock) as mock_timer, \
                 patch.object(db, "get_all_clones", new_callable=AsyncMock) as mock_clones, \
                 patch.object(db, "get_db_channels", new_callable=AsyncMock) as mock_sec:

                mock_sub.return_value = True
                mock_ban.return_value = []
                mock_pres.return_value = True
                mock_prem.return_value = True
                mock_timer.return_value = 0
                mock_clones.return_value = []
                mock_sec.return_value = []
                mock_get_msgs.return_value = [m10, m11_deleted, m12]

                await start_command(client, msg)

                # Ensure m10 and m12 were successfully copied despite m11 being deleted
                m10.copy.assert_called_once()
                m12.copy.assert_called_once()

        asyncio.run(run_test())

    def test_serielbatch_command_flow(self):
        async def run_test():
            client = MagicMock()
            client.db_channel.id = -1001234567890

            message = MagicMock()
            message.chat.id = 12345
            message.from_user.id = 12345
            message.reply_to_message = None
            message.text = "/serielbatch https://t.me/hsjisksjs/10-https://t.me/hsjisksjs/12"
            prog_msg = MagicMock()
            prog_msg.edit_text = AsyncMock()
            message.reply_text = AsyncMock(return_value=prog_msg)

            ask_filter_resp = MagicMock()
            ask_filter_resp.text = "Naruto"
            client.ask = AsyncMock(return_value=ask_filter_resp)

            # Create mock DB messages for 10, 11, 12
            m10 = MagicMock()
            m10.id = 10
            m10.empty = False
            m10_doc = MagicMock()
            m10_doc.file_name = "Naruto_EP10.mkv"
            m10.document = m10_doc
            m10.video = None
            m10.audio = None
            m10.animation = None
            m10.photo = None
            m10.voice = None
            m10.caption = "Naruto Episode 10"

            m11 = MagicMock()
            m11.id = 11
            m11.empty = False
            m11_doc = MagicMock()
            m11_doc.file_name = "OnePiece_EP11.mkv"
            m11.document = m11_doc
            m11.video = None
            m11.audio = None
            m11.animation = None
            m11.photo = None
            m11.voice = None
            m11.caption = "One Piece Episode 11"

            m12 = MagicMock()
            m12.id = 12
            m12.empty = False
            m12_doc = MagicMock()
            m12_doc.file_name = "Naruto_EP12.mkv"
            m12.document = m12_doc
            m12.video = None
            m12.audio = None
            m12.animation = None
            m12.photo = None
            m12.voice = None
            m12.caption = "Naruto Episode 12"

            with patch("plugins.autobatch.check_admin_or_owner", new_callable=AsyncMock) as mock_auth, \
                 patch("plugins.autobatch.get_messages", new_callable=AsyncMock) as mock_get_msgs, \
                 patch("plugins.autobatch.resolve_db_source", new_callable=AsyncMock) as mock_resolve:

                mock_auth.return_value = True
                mock_resolve.return_value = (-1001234567890, "TestBot", client)
                mock_get_msgs.return_value = [m10, m11, m12]

                await serielbatch_command(client, message)

                # Should call reply_text for progress msg + 1 combined output message for matched files m10 & m12 (skipped m11 since filter "Naruto" not in OnePiece)
                self.assertEqual(message.reply_text.call_count, 2)

                combined_text = message.reply_text.call_args_list[1][0][0]
                self.assertIn("<b>First Filename:</b> Naruto_EP10.mkv", combined_text)
                self.assertIn("<b>First Filename:</b> Naruto_EP12.mkv", combined_text)
                self.assertIn("<b>Here is your link:</b>", combined_text)

                prog_msg.edit_text.assert_called_once()
                completion_text = prog_msg.edit_text.call_args[0][0]
                self.assertIn("Matched Links Generated:</b> <code>2</code>", completion_text)

        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main()
