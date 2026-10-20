import asyncio
import os
import random
import sys
import time
from datetime import datetime, timedelta
from pyrogram import Client, filters, __version__
from pyrogram.enums import ParseMode, ChatAction
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated, UserNotParticipant
from bot import Bot
from config import *
from helper_func import *
from database.database import *
from plugins.anizoneflix import check_admin_or_owner

REPLY_ERROR = "<b><blockquote expandable>❌ ᴘʟᴇᴀꜱᴇ ᴜꜱᴇ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ᴀꜱ ᴀ ʀᴇᴘʟʏ ᴛᴏ ᴀɴʏ ᴛᴇʟᴇɢʀᴀᴍ ᴍᴇꜱꜱᴀɢᴇ, ᴍᴇᴅɪᴀ, ᴏʀ ꜰᴏʀᴡᴀʀᴅᴇᴅ ᴘᴏꜱᴛ! ✨</blockquote></b>"

MAX_CONCURRENT_TASKS = 100

async def broadcast_send_worker(client: Bot, broadcast_msg: Message, chat_id: int, is_pin: bool = False, pin_both_sides: bool = True, delete_duration: int = 0, is_forward: bool = False):
    """
    Worker function to send a broadcast message to a single user.
    Preserves forwarded tags if original message was forwarded.
    Preserves inline buttons (reply_markup).
    """
    try:
        # Determine whether to forward or copy
        # Forwarding preserves the original forwarded header ("Forwarded from ...")
        if is_forward or broadcast_msg.forward_date or broadcast_msg.forward_from_chat or broadcast_msg.forward_from or broadcast_msg.forward_sender_name:
            try:
                sent_msg = await broadcast_msg.forward(chat_id)
            except Exception:
                sent_msg = await broadcast_msg.copy(chat_id, reply_markup=broadcast_msg.reply_markup)
        else:
            sent_msg = await broadcast_msg.copy(chat_id, reply_markup=broadcast_msg.reply_markup)

        if is_pin and sent_msg:
            try:
                await client.pin_chat_message(chat_id=chat_id, message_id=sent_msg.id, both_sides=pin_both_sides)
            except Exception:
                pass

        if delete_duration > 0 and sent_msg:
            asyncio.create_task(delete_msg_after(sent_msg, delete_duration))

        return "success"

    except FloodWait as e:
        await asyncio.sleep(e.x)
        return await broadcast_send_worker(client, broadcast_msg, chat_id, is_pin, pin_both_sides, delete_duration, is_forward)
    except UserIsBlocked:
        await db.del_user(chat_id)
        return "blocked"
    except InputUserDeactivated:
        await db.del_user(chat_id)
        return "deleted"
    except Exception:
        return "unsuccessful"

async def delete_msg_after(msg: Message, duration: int):
    try:
        await asyncio.sleep(duration)
        await msg.delete()
    except Exception:
        pass

async def run_parallel_broadcast(client: Bot, users: list, broadcast_msg: Message, is_pin: bool = False, delete_duration: int = 0, status_msg: Message = None):
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
    total = len(users)
    successful = blocked = deleted = unsuccessful = 0

    is_fwd = bool(broadcast_msg.forward_date or broadcast_msg.forward_from_chat or broadcast_msg.forward_from or broadcast_msg.forward_sender_name)

    async def sem_worker(chat_id):
        nonlocal successful, blocked, deleted, unsuccessful
        async with semaphore:
            res = await broadcast_send_worker(client, broadcast_msg, chat_id, is_pin=is_pin, delete_duration=delete_duration, is_forward=is_fwd)
            if res == "success":
                successful += 1
            elif res == "blocked":
                blocked += 1
            elif res == "deleted":
                deleted += 1
            else:
                unsuccessful += 1

    # Execute in concurrent batches of 100 for maximum throughput
    batch_size = 100
    start_time = time.time()

    for i in range(0, total, batch_size):
        batch = users[i:i + batch_size]
        await asyncio.gather(*[sem_worker(uid) for uid in batch])

        if status_msg and (i % 500 == 0 or i + batch_size >= total):
            elapsed = time.time() - start_time
            rps = int((i + len(batch)) / elapsed) if elapsed > 0 else 0
            try:
                await status_msg.edit_text(
                    "✨ <b><u>AniZoneFlix Broadcast In Progress...</u></b> ✨\n\n"
                    "<blockquote expandable>"
                    f"<b>📊 Progress:</b> <code>{min(i + len(batch), total)} / {total}</code>\n"
                    f"<b>🟢 Successful:</b> <code>{successful}</code>\n"
                    f"<b>🔴 Blocked:</b> <code>{blocked}</code>\n"
                    f"<b>👻 Deleted:</b> <code>{deleted}</code>\n"
                    f"<b>❌ Unsuccessful:</b> <code>{unsuccessful}</code>\n"
                    f"<b>⚡ Speed:</b> <code>{rps} msg/sec</code>"
                    "</blockquote>\n\n"
                    "✨ <b>Powered by <a href='https://t.me/anizoneflix'>AniZoneFlix</a></b> ✨"
                )
            except Exception:
                pass

    elapsed = time.time() - start_time
    avg_speed = int(total / elapsed) if elapsed > 0 else total

    final_status = (
        "✨ <b><u>AniZoneFlix Broadcast Completed!</u></b> ✨\n\n"
        "<blockquote expandable>"
        f"<b>📊 Total Users:</b> <code>{total}</code>\n"
        f"<b>🟢 Successful:</b> <code>{successful}</code>\n"
        f"<b>🔴 Blocked Users:</b> <code>{blocked}</code>\n"
        f"<b>👻 Deleted Accounts:</b> <code>{deleted}</code>\n"
        f"<b>❌ Unsuccessful:</b> <code>{unsuccessful}</code>\n"
        f"<b>⚡ Execution Time:</b> <code>{elapsed:.2f}s</code>\n"
        f"<b>🚀 Average Speed:</b> <code>{avg_speed} msg/sec</code>"
        "</blockquote>\n\n"
        "✨ <b>Powered by <a href='https://t.me/anizoneflix'>AniZoneFlix</a></b> ✨"
    )
    return final_status

@Bot.on_message(filters.private & filters.command('pbroadcast'))
async def send_pin_text(client: Bot, message: Message):
    if not await check_admin_or_owner(message):
        return

    if not message.reply_to_message:
        msg = await message.reply(REPLY_ERROR)
        await asyncio.sleep(8)
        return await msg.delete()

    users = await db.full_userbase()
    if not users:
        return await message.reply("<b><blockquote expandable>❌ No users registered in database.</blockquote></b>")

    pls_wait = await message.reply("<b><blockquote expandable>⚡ AniZoneFlix Pin Broadcast Initializing...</blockquote></b>")
    final_text = await run_parallel_broadcast(client, users, message.reply_to_message, is_pin=True, status_msg=pls_wait)
    await pls_wait.edit(final_text)

@Bot.on_message(filters.private & filters.command('broadcast'))
async def send_text(client: Bot, message: Message):
    if not await check_admin_or_owner(message):
        return

    if not message.reply_to_message:
        msg = await message.reply(REPLY_ERROR)
        await asyncio.sleep(8)
        return await msg.delete()

    users = await db.full_userbase()
    if not users:
        return await message.reply("<b><blockquote expandable>❌ No users registered in database.</blockquote></b>")

    pls_wait = await message.reply("<b><blockquote expandable>⚡ AniZoneFlix High-Speed Broadcast Initializing...</blockquote></b>")
    final_text = await run_parallel_broadcast(client, users, message.reply_to_message, is_pin=False, status_msg=pls_wait)
    await pls_wait.edit(final_text)

@Bot.on_message(filters.private & filters.command('dbroadcast'))
async def delete_broadcast(client: Bot, message: Message):
    if not await check_admin_or_owner(message):
        return

    if not message.reply_to_message:
        msg = await message.reply(REPLY_ERROR)
        await asyncio.sleep(8)
        return await msg.delete()

    try:
        duration = int(message.command[1])
    except (IndexError, ValueError):
        return await message.reply("<b><blockquote expandable>Provide a valid duration in seconds.\nUsage: /dbroadcast {duration}</blockquote></b>")

    users = await db.full_userbase()
    if not users:
        return await message.reply("<b><blockquote expandable>❌ No users registered in database.</blockquote></b>")

    pls_wait = await message.reply(f"<b><blockquote expandable>⚡ AniZoneFlix Auto-Delete Broadcast ({duration}s) Initializing...</blockquote></b>")
    final_text = await run_parallel_broadcast(client, users, message.reply_to_message, is_pin=False, delete_duration=duration, status_msg=pls_wait)
    await pls_wait.edit(final_text)
