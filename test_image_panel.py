import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import main  # Imports monkeypatched Pyrofork with style= parameter support on InlineKeyboardButton
from database.database import db
from helper_func import ISHTAR_IMAGES, get_next_image
from plugins.cbb import panel_callback_handler

class TestImagePanelManagement(unittest.IsolatedAsyncioTestCase):
    @patch.object(db, "get_admin_images", new_callable=AsyncMock)
    @patch.object(db, "add_admin_images", new_callable=AsyncMock)
    @patch.object(db, "delete_admin_image", new_callable=AsyncMock)
    @patch.object(db, "clear_admin_images", new_callable=AsyncMock)
    async def test_admin_images_db_methods(self, mock_clear, mock_del, mock_add, mock_get):
        mock_get.return_value = ["https://example.com/1.jpg"]

        imgs = await db.get_admin_images()
        self.assertEqual(imgs, ["https://example.com/1.jpg"])

        await db.add_admin_images(["https://example.com/2.jpg"])
        mock_add.assert_called_once_with(["https://example.com/2.jpg"])

        await db.delete_admin_image("https://example.com/1.jpg")
        mock_del.assert_called_once_with("https://example.com/1.jpg")

        await db.clear_admin_images()
        mock_clear.assert_called_once()

    def test_get_next_image_custom_pool(self):
        db.ADMIN_IMAGES_CACHE = ["https://custom.com/image.jpg"]
        img = get_next_image(999)
        self.assertEqual(img, "https://custom.com/image.jpg")
        db.ADMIN_IMAGES_CACHE = None

    @patch("plugins.cbb.is_owner", new_callable=AsyncMock)
    @patch("plugins.cbb.is_admin", new_callable=AsyncMock)
    @patch.object(db, "get_admin_images", new_callable=AsyncMock)
    async def test_panel_images_callback(self, mock_get_imgs, mock_is_admin, mock_is_owner):
        mock_is_owner.return_value = True
        mock_is_admin.return_value = True
        mock_get_imgs.return_value = ["https://example.com/img1.png"]

        cb = MagicMock()
        cb.from_user.id = 123456
        cb.data = "panel_images"
        cb.answer = AsyncMock()
        cb.message.edit_text = AsyncMock()

        client = MagicMock()

        await panel_callback_handler(client, cb)

        cb.answer.assert_called_once()
        cb.message.edit_text.assert_called_once()
        self.assertIn("Admin Configured Images", cb.message.edit_text.call_args[0][0])

if __name__ == "__main__":
    unittest.main()
