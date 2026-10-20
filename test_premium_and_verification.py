import unittest
import sys
import types
from unittest.mock import AsyncMock, MagicMock

# Import parse_duration_string directly from plugins/panel.py
from plugins.panel import parse_duration_string
from helper_func import get_exp_time, get_readable_time

class TestDurationAndFormatting(unittest.TestCase):
    def test_parse_duration_string(self):
        test_cases = {
            "1 day": 86400,
            "7 days": 604800,
            "1 month": 2592000,
            "6 months": 15552000,
            "1 year": 31536000,
            "30 min": 1800,
            "2 hours": 7200,
            "10 sec": 10
        }
        for duration_str, expected_sec in test_cases.items():
            with self.subTest(duration_str=duration_str):
                self.assertEqual(parse_duration_string(duration_str), expected_sec)

    def test_get_exp_time(self):
        self.assertEqual(get_exp_time(86400), "1 day")
        self.assertEqual(get_exp_time(604800), "7 days")
        self.assertEqual(get_exp_time(2592000), "1 month")
        self.assertEqual(get_exp_time(15552000), "6 months")
        self.assertEqual(get_exp_time(31536000), "1 year")

if __name__ == "__main__":
    unittest.main()

class TestVerifyAndCommands(unittest.IsolatedAsyncioTestCase):
    async def test_verify_deep_link_formatting(self):
        token = "123456_payload_rand"
        expire_sec = 86400
        duration_text = get_exp_time(expire_sec).upper()
        self.assertEqual(duration_text, "1 DAY")

        expire_sec_7 = 604800
        duration_text_7 = get_exp_time(expire_sec_7).upper()
        self.assertEqual(duration_text_7, "7 DAYS")

    async def test_verify_fallback_token_parsing_complex_payload(self):
        import base64
        from database.database import db

        payload = "get-100_special_payload"
        enc_payload = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
        token = f"__________123456_sb_uuid__________/{enc_payload}_random888"

        mock_db = MagicMock()
        mock_tokens = MagicMock()
        mock_tokens.find_one = AsyncMock(return_value=None)
        mock_db.__getitem__.return_value = mock_tokens

        with unittest.mock.patch.object(db, "database", mock_db):
            res = await db.get_verify_token(token)
            self.assertIsNotNone(res)
            self.assertEqual(res["user_id"], 123456)
            self.assertEqual(res["payload"], payload)

    async def test_verify_token_returning_payload_message_command(self):
        from database.database import db
        client = MagicMock()
        message = MagicMock()
        message.from_user.id = 12345
        message.from_user.mention = "TestUser"
        message.text = "/start verify_testtoken123"
        message.reply_text = AsyncMock()
        message.reply = AsyncMock()

        token_doc = {"_id": "testtoken123", "user_id": 12345, "payload": "get-1000"}

        with unittest.mock.patch.object(db, "get_ban_users", AsyncMock(return_value=[])), \
             unittest.mock.patch("plugins.start.is_subscribed", AsyncMock(return_value=True)), \
             unittest.mock.patch.object(db, "get_verify_token", AsyncMock(return_value=token_doc)), \
             unittest.mock.patch.object(db, "get_config_val", AsyncMock(return_value=3600)), \
             unittest.mock.patch.object(db, "set_user_verified", AsyncMock()), \
             unittest.mock.patch.object(db, "mark_verify_token_used", AsyncMock()), \
             unittest.mock.patch.object(db, "is_premium_user", AsyncMock(return_value=True)):

            from plugins.start import start_command
            await start_command(client, message)

            self.assertEqual(message.text, "/start get-1000")
            self.assertEqual(message.command, ["start", "get-1000"])

    async def test_go_shortener_returns_loading_page(self):
        import main
        with main.app.test_client() as c:
            mock_doc = {"user_id": 12345, "payload": "get-100"}
            with unittest.mock.patch("main.run_async") as mock_run_async:
                def side_effect(coro):
                    if "get_verify_token" in str(coro):
                        return mock_doc
                    return None
                mock_run_async.side_effect = side_effect

                headers = {"User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Mobile Safari/537.36"}
                res = c.get("/go_shortener?token=tok123&st=short123", headers=headers)
                self.assertEqual(res.status_code, 200)
                self.assertIn("Redirecting, please wait", res.text)

    async def test_get_shortener_url_queries_shortener_and_returns_json(self):
        import main
        with main.app.test_client() as c:
            mock_doc = {"user_id": 12345, "payload": "get-100"}
            shortener_config = [{
                "_id": "s1",
                "domain": "https://anti-bypass-xkpb.onrender.com",
                "api_key": "abp_testkey123",
                "enabled": True
            }]
            with unittest.mock.patch("main.run_async") as mock_run_async, \
                 unittest.mock.patch("requests.get") as mock_get:
                def side_effect(coro):
                    if "get_verify_token" in str(coro):
                        return mock_doc
                    if "get_shorteners" in str(coro):
                        return shortener_config
                    if "get_config_val" in str(coro):
                        return "https://your-render-service.onrender.com"
                    if "get_config" in str(coro):
                        return {"BOT_USERNAME": "test_file_bot"}
                    return None
                mock_run_async.side_effect = side_effect

                mock_res = MagicMock()
                mock_res.json.return_value = {"shortenedUrl": "https://shortened.link/abc123"}
                mock_get.return_value = mock_res

                res = c.get("/api/get_shortener_url?token=tok123&st=short123")
                self.assertEqual(res.status_code, 200)
                self.assertEqual(res.json.get("url"), "https://shortened.link/abc123")

    def test_telegram_deep_link_token_length(self):
        import secrets
        short_token_id = secrets.token_urlsafe(24)
        deep_link_param = f"verify_{short_token_id}"
        self.assertLessEqual(len(deep_link_param), 64)

    async def test_instant_premium_activation_and_expiration_notifications(self):
        from database.database import db
        client = AsyncMock()

        # Test addpremium instant notification
        from plugins.panel import addpremium_command
        msg = MagicMock()
        msg.from_user.id = 999
        msg.text = "/addpremium 12345 1 hour"
        msg.reply_text = AsyncMock()

        with unittest.mock.patch("plugins.panel.check_admin_or_owner", AsyncMock(return_value=True)), \
             unittest.mock.patch.object(db, "add_premium_user", AsyncMock(return_value=True)):
            client.get_users = AsyncMock(return_value=MagicMock(username="testuser", id=12345))
            await addpremium_command(client, msg)

            client.send_message.assert_called_once()
            call_args = client.send_message.call_args
            self.assertEqual(call_args[1]["chat_id"], 12345)
            self.assertIn("PREMIUM ACTIVATED INSTANTLY!", call_args[1]["text"])

    async def test_check_and_notify_expirations(self):
        from database.database import db
        from datetime import datetime, timedelta

        mock_db = MagicMock()
        mock_verified = MagicMock()
        mock_premium = MagicMock()

        past_dt = datetime.utcnow() - timedelta(seconds=100)

        def mock_verified_find(query):
            mock_cursor = MagicMock()
            mock_cursor.to_list = AsyncMock(return_value=[{'_id': 111, 'expire_at': past_dt}])
            return mock_cursor

        def mock_premium_find(query):
            mock_cursor = MagicMock()
            mock_cursor.to_list = AsyncMock(return_value=[{'_id': 222, 'expire_at': past_dt}])
            return mock_cursor

        mock_verified.find = mock_verified_find
        mock_verified.delete_one = AsyncMock()
        mock_premium.find = mock_premium_find
        mock_premium.delete_one = AsyncMock()

        def mock_getitem(name):
            if name == 'verified_users': return mock_verified
            if name == 'premium_users': return mock_premium
            return MagicMock()

        mock_db.__getitem__.side_effect = mock_getitem

        client = AsyncMock()

        with unittest.mock.patch.object(db, "database", mock_db):
            await db.check_and_notify_expirations(client)

            self.assertEqual(client.send_message.call_count, 2)
            calls = client.send_message.call_args_list

            self.assertEqual(calls[0][1]["chat_id"], 111)
            self.assertIn("YOUR VERIFICATION HAS EXPIRED!", calls[0][1]["text"])

            self.assertEqual(calls[1][1]["chat_id"], 222)
            self.assertIn("YOUR PREMIUM STATUS HAS EXPIRED!", calls[1][1]["text"])

if __name__ == "__main__":
    unittest.main()
