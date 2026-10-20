# =====================================================================================##
#
#  ██╗░░██╗███╗░░██╗██████╗░░█████╗░████████╗███████╗██████╗░
#  ██║░░██║████╗░██║██╔══██╗██╔══██╗╚══██╔══╝██╔════╝██╔══██╗
#  ██║░░██║██╔██╗██║██████╔╝███████║░░░██║░░░█████╗░░██║░░██║
#  ██║░░██║██║╚████║██╔══██╗██╔══██║░░░██║░░░██╔══╝░░██║░░██║
#  ╚██████╔╝██║░╚███║██║░░██║██║░░██║░░░██║░░░███████╗██████╔╝
#  ░╚═════╝░╚═╝░░╚══╝╚═╝░░╚═╝╚═╝░░╚═╝░░░╚═╝░░░╚══════╝╚═════╝░
#
#  ░██████╗░██████╗░██████╗░███████╗██████╗░
#  ██╔════╝██╔═══██╗██╔══██╗██╔════╝██╔══██╗
#  ██║░░░░░██║░░░██║██║░░██║█████╗░░██████╔╝
#  ██║░░░░░██║░░░██║██║░░██║██╔══╝░░██╔══██╗
#  ╚██████╗╚██████╔╝██████╔╝███████╗██║░░██║
#  ░╚═════╝░╚═════╝░╚═════╝░╚══════╝╚═╝░░╚═╝
#
#                         ✨ MADE BY ANIZONEFLIX ✨
#                  Join Updates Channel: https://t.me/anizoneflix
#=====================================================================================##

import base64
import re
import asyncio
import logging
import time
import random
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from config import *
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant
from pyrogram.errors import FloodWait
from database.database import *


async def check_admin(filter, client, update):
    try:
        user_id = update.from_user.id       
        return any([user_id == OWNER_ID, await db.admin_exist(user_id)])
    except Exception as e:
        print(f"! Exception in check_admin: {e}")
        return False

async def is_subscribed(client, user_id):
    channel_ids = await db.show_channels()

    if not channel_ids:
        return True

    if user_id == OWNER_ID:
        return True

    for cid in channel_ids:
        if not await is_sub(client, user_id, cid):
            mode = await db.get_channel_mode(cid)
            if mode == "on":
                await asyncio.sleep(2) 
                if await is_sub(client, user_id, cid):
                    continue
            return False

    return True


async def is_sub(client, user_id, channel_id):
    """Check membership without masking Telegram API failures as ordinary non-membership."""
    log = logging.getLogger(__name__)
    try:
        # Resolve the chat first so usernames, numeric IDs, and migrated chats are
        # handled consistently by Pyrogram.
        chat = await client.get_chat(channel_id)
        member = await client.get_chat_member(chat.id, int(user_id))
        status = getattr(member, "status", None)
        status_name = getattr(status, "value", status)
        if status_name in {"owner", "administrator", "member"}:
            return True
        # A restricted member can still be subscribed unless Telegram says they
        # are not participating; the status itself is not a subscription failure.
        if status_name == "restricted":
            return bool(getattr(member, "is_member", False))
        return False
    except UserNotParticipant:
        try:
            mode = await db.get_channel_mode(channel_id)
            if mode == "on":
                return bool(await db.req_user_exist(channel_id, user_id))
        except Exception:
            log.exception("Force-sub request-mode lookup failed (chat=%s user=%s)", channel_id, user_id)
        return False
    except Exception as exc:
        # BadRequest / PeerIdInvalid / ChatAdminRequired etc. are operational
        # errors, not proof that the user has not joined. Log enough to diagnose.
        log.warning(
            "Membership check failed: chat_id=%s user_id=%s error=%s: %s",
            channel_id, user_id, type(exc).__name__, exc,
        )
        return False


async def encode(string):
    string_bytes = string.encode("ascii")
    base64_bytes = base64.urlsafe_b64encode(string_bytes)
    base64_string = (base64_bytes.decode("ascii")).strip("=")
    return base64_string

async def decode(base64_string):
    try:
        base64_string = base64_string.strip("=")
        base64_bytes = (base64_string + "=" * (-len(base64_string) % 4)).encode("ascii")
        string_bytes = base64.urlsafe_b64decode(base64_bytes)
        string = string_bytes.decode("ascii")
        return string
    except Exception as e:
        raise ValueError(f"Invalid base64 encoding: {e}")

async def get_messages(client, message_ids, chat_id=None):
    messages = []
    if isinstance(message_ids, int):
        message_ids = [message_ids]
    else:
        message_ids = list(message_ids)

    target_chat_id = chat_id if chat_id is not None else (getattr(client, "db_channel", None).id if getattr(client, "db_channel", None) else CHANNEL_ID)

    total_messages = 0
    while total_messages < len(message_ids):
        temb_ids = message_ids[total_messages:total_messages+200]
        msgs = []
        try:
            msgs = await client.get_messages(
                chat_id=target_chat_id,
                message_ids=temb_ids
            )
        except FloodWait as e:
            await asyncio.sleep(e.x)
            try:
                msgs = await client.get_messages(
                    chat_id=target_chat_id,
                    message_ids=temb_ids
                )
            except Exception as e2:
                print(f"Error fetching messages in batch after FloodWait: {e2}")
        except Exception as e:
            print(f"Error fetching messages in batch: {e}")

        if msgs:
            if isinstance(msgs, list):
                messages.extend([m for m in msgs if m])
            else:
                messages.append(msgs)

        total_messages += len(temb_ids)
    return messages

async def get_message_id(client, message):
    if not message:
        return 0
    if getattr(message, "forward_from_chat", None):
        if getattr(client, "db_channel", None) and message.forward_from_chat.id == client.db_channel.id:
            return message.forward_from_message_id
        elif message.forward_from_chat.id == CHANNEL_ID:
            return message.forward_from_message_id
        else:
            return message.forward_from_message_id or 0
    elif getattr(message, "forward_sender_name", None):
        return 0
    text_to_parse = message.text or getattr(message, "caption", "") or ""
    if text_to_parse:
        pattern = r"https://(?:t\.me|telegram\.me|telegram\.dog)/(?:c/)?([^/?\s]+)/(\d+)"
        matches = re.search(pattern, text_to_parse)
        if matches:
            return int(matches.group(2))
        elif text_to_parse.strip().isdigit():
            return int(text_to_parse.strip())
        else:
            parts = text_to_parse.split()
            for part in parts:
                if part.isdigit():
                    return int(part)
            return 0
    else:
        return 0


def get_readable_time(seconds: int) -> str:
    seconds = int(seconds)
    if seconds <= 0:
        return "0s"

    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)


def get_exp_time(seconds):
    periods = [('year', 31536000), ('month', 2592000), ('day', 86400), ('hour', 3600), ('min', 60), ('sec', 1)]
    result = []
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            val, seconds = divmod(seconds, period_seconds)
            unit = f"{period_name}s" if val > 1 else period_name
            result.append(f"{val} {unit}")
    return " ".join(result) if result else "0 sec"

subscribed = filters.create(is_subscribed)
admin = filters.create(check_admin)


ISHTAR_IMAGES = [
    "https://imgyx.pages.dev/yyazg",
    "https://imgyx.pages.dev/ZFQ2L",
    "https://imgyx.pages.dev/M9sMX",
    "https://imgyx.pages.dev/t6xVX",
    "https://imgyx.pages.dev/sRVQy"
]

image_rotation_state = {}

def get_next_image(chat_id: int) -> str:
    """
    Returns an image URL configured by the admin (from database if present).
    Only falls back to ISHTAR_IMAGES if no admin images are configured.
    Maintains rotation state per chat_id.
    """
    admin_imgs = getattr(db, "ADMIN_IMAGES_CACHE", None)

    if not admin_imgs:
        try:
            if hasattr(db, "dbclient") and db.dbclient and DB_NAME:
                doc = db.dbclient[DB_NAME]['settings'].find_one({'_id': 'admin_images'})
                if doc and isinstance(doc.get('urls'), list) and doc.get('urls'):
                    admin_imgs = doc.get('urls')
                    db.ADMIN_IMAGES_CACHE = admin_imgs
        except Exception:
            pass

    pool = admin_imgs if admin_imgs else ISHTAR_IMAGES

    state = image_rotation_state.get(chat_id, [])
    available = [img for img in pool if img not in state]
    last_sent = state[-1] if state else None

    if not available:
        available = list(pool)
        if last_sent in available and len(available) > 1:
            available.remove(last_sent)
        chosen = random.choice(available)
        state = [chosen]
    else:
        chosen = random.choice(available)
        state.append(chosen)

    image_rotation_state[chat_id] = state
    return chosen

# =====================================================================================##
#                         ✨ MADE BY ANIZONEFLIX ✨
#                  Join Updates Channel: https://t.me/anizoneflix
#====================================================================================##

async def get_bot_username(client):
    username = getattr(client, "username", None)
    if username:
        return username.replace("@", "").strip()
    me = getattr(client, "me", None)
    if me and getattr(me, "username", None):
        return me.username.replace("@", "").strip()
    try:
        me = await client.get_me()
        if me and me.username:
            client.username = me.username
            return me.username.replace("@", "").strip()
    except Exception as e:
        print(f"Error fetching bot me: {e}")
    return "bot"
