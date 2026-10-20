import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import main  # Imports monkeypatched Pyrofork
from database.database import db
from plugins.broadcast import broadcast_send_worker, run_parallel_broadcast, send_text

class TestBroadcastSystem(unittest.IsolatedAsyncioTestCase):
    @patch("plugins.broadcast.db.del_user", new_callable=AsyncMock)
    async def test_broadcast_send_worker_forward(self, mock_del_user):
        client = MagicMock()
        client.pin_chat_message = AsyncMock()

        msg = MagicMock()
        msg.forward_date = 123456789
        msg.forward_from_chat = MagicMock()
        msg.forward_from = None
        msg.forward_sender_name = None
        msg.reply_markup = None
        msg.forward = AsyncMock()
        msg.copy = AsyncMock()

        res = await broadcast_send_worker(client, msg, 1001, is_forward=True)

        self.assertEqual(res, "success")
        msg.forward.assert_called_once_with(1001)

    @patch("plugins.broadcast.db.del_user", new_callable=AsyncMock)
    async def test_broadcast_send_worker_copy_with_buttons(self, mock_del_user):
        client = MagicMock()

        btn = MagicMock()
        msg = MagicMock()
        msg.forward_date = None
        msg.forward_from_chat = None
        msg.forward_from = None
        msg.forward_sender_name = None
        msg.reply_markup = btn
        msg.copy = AsyncMock()

        res = await broadcast_send_worker(client, msg, 1002, is_forward=False)

        self.assertEqual(res, "success")
        msg.copy.assert_called_once_with(1002, reply_markup=btn)

    @patch("plugins.broadcast.broadcast_send_worker", new_callable=AsyncMock)
    async def test_run_parallel_broadcast(self, mock_worker):
        mock_worker.return_value = "success"
        client = MagicMock()
        msg = MagicMock()
        status_msg = MagicMock()
        status_msg.edit_text = AsyncMock()

        users = list(range(1001, 1051))  # 50 users

        final_status = await run_parallel_broadcast(client, users, msg, status_msg=status_msg)

        self.assertIn("AniZoneFlix Broadcast Completed", final_status)
        self.assertIn("Total Users:</b> <code>50</code>", final_status)
        self.assertEqual(mock_worker.call_count, 50)

    @patch("plugins.broadcast.check_admin_or_owner", new_callable=AsyncMock)
    @patch("plugins.broadcast.db.full_userbase", new_callable=AsyncMock)
    @patch("plugins.broadcast.run_parallel_broadcast", new_callable=AsyncMock)
    async def test_send_text_command(self, mock_parallel, mock_userbase, mock_auth):
        mock_auth.return_value = True
        mock_userbase.return_value = [1001, 1002]
        mock_parallel.return_value = "Done"

        client = MagicMock()
        msg = MagicMock()
        msg.reply_to_message = MagicMock()
        msg.reply = AsyncMock()
        pls_wait = MagicMock()
        pls_wait.edit = AsyncMock()
        msg.reply.return_value = pls_wait

        await send_text(client, msg)

        mock_parallel.assert_called_once()
        pls_wait.edit.assert_called_once_with("Done")

if __name__ == "__main__":
    unittest.main()
