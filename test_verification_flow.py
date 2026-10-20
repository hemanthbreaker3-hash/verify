import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import main  # Import Flask app and helpers from main
from main import app, is_supported_chrome_browser

class TestVerificationFlow(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_chrome_browser_validation(self):
        chrome_ua = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        firefox_ua = "Mozilla/5.0 (Android 10; Mobile; rv:109.0) Gecko/109.0 Firefox/119.0"
        edge_ua = "Mozilla/5.0 (Linux; Android 10; HD1913) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 EdgA/120.0.2210.141"
        opera_ua = "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 OPR/72.3.3767.68685"
        bot_ua = "Python-requests/2.28.0"

        self.assertTrue(is_supported_chrome_browser(chrome_ua))
        self.assertTrue(is_supported_chrome_browser(firefox_ua))
        self.assertTrue(is_supported_chrome_browser(edge_ua))
        self.assertTrue(is_supported_chrome_browser(opera_ua))
        self.assertFalse(is_supported_chrome_browser(bot_ua))
        self.assertFalse(is_supported_chrome_browser(""))

    @patch("main.run_async")
    @patch("requests.post")
    def test_verify_backend_unsupported_browser(self, mock_post, mock_run_async):
        # Mock token finding user 123456
        mock_run_async.side_effect = [
            {"user_id": 123456, "username": "testuser"},  # get_verify_token
            {},  # get_config
            True, # add_ban_user
        ]

        resp = self.app.get("/api/verify?token=test_token_123", headers={"User-Agent": "Python-requests/2.28.0"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"BYPASS DETECTED", resp.data)
        self.assertIn(b"temporarily banned for 1 day", resp.data)

    @patch("main.run_async")
    def test_verify_backend_valid_chrome(self, mock_run_async):
        mock_run_async.side_effect = [
            {"user_id": 123456, "username": "testuser"},  # get_verify_token
            {"BOT_USERNAME": "test_bot"},  # get_config
            86400,  # get_config_val VERIFY_EXPIRE_SECONDS
            True,   # set_user_verified
            True,   # mark_verify_token_used
        ]

        chrome_ua = "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        resp = self.app.get("/api/verify?token=test_token_123", headers={"User-Agent": chrome_ua})

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Verification Complete", resp.data)
        self.assertIn(b"https://telegram.me/test_bot?start=verify_test_token_123", resp.data)

if __name__ == "__main__":
    unittest.main()
