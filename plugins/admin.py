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

import asyncio
import os
import random
import sys
import time

from pyrogram import Client, filters, __version__
from pyrogram.enums import ParseMode, ChatAction, ChatMemberStatus, ChatType
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ReplyKeyboardMarkup,
    ChatMemberUpdated,
    ChatPermissions,
)
from pyrogram.errors.exceptions.bad_request_400 import (
    UserNotParticipant,
    InviteHashEmpty,
    ChatAdminRequired,
    PeerIdInvalid,
    UserIsBlocked,
    InputUserDeactivated,
)


from config import *
from bot import Bot
from config import *
from helper_func import *
from database.database import *
from plugins.anizoneflix import check_owner_only, check_admin_or_owner


@Bot.on_message(filters.command('add_admin') & filters.private)
async def add_admins(client: Client, message: Message):
    if not await check_owner_only(message):
        return

    pro = await message.reply("<b><blockquote>⏳ Processing request... Please wait.</blockquote></b>", quote=True)
    check = 0
    admin_ids = await db.get_all_admins()
    admins = message.text.split()[1:]

    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Close", callback_data="close", style="danger")]])

    if not admins:
        return await pro.edit(
            "<b><blockquote>You need to provide user ID(s) to add as admin.</blockquote></b>\n\n"
            "<b>Usage:</b> <code>/add_admin <user_id1> [user_id2]</code>\n"
            "<b>Example:</b> <code>/add_admin 1234567890 9876543210</code>",
            reply_markup=reply_markup
        )

    admin_list = ""
    for uid in admins:
        try:
            uid_int = int(uid)
        except:
            admin_list += f"<blockquote><b>Invalid ID: <code>{uid}</code></b></blockquote>\n"
            continue

        if uid_int in admin_ids:
            admin_list += f"<blockquote><b>ID <code>{uid_int}</code> already exists.</b></blockquote>\n"
            continue

        if uid_int > 0:
            admin_list += f"<b><blockquote>(ID: <code>{uid_int}</code>) added.</blockquote></b>\n"
            check += 1
        else:
            admin_list += f"<blockquote><b>Invalid ID: <code>{uid}</code></b></blockquote>\n"

    if check == len(admins):
        for uid in admins:
            await db.add_admin(int(uid))
        await pro.edit(f"<b>✅ Admin(s) added successfully:</b>\n\n{admin_list}", reply_markup=reply_markup)
    else:
        await pro.edit(
            f"<b>❌ Some errors occurred while adding admins:</b>\n\n{admin_list.strip()}\n\n"
            "<b><i>Please check and try again.</i></b>",
            reply_markup=reply_markup
        )


@Bot.on_message(filters.command('deladmin') & filters.private)
async def delete_admins(client: Client, message: Message):
    if not await check_owner_only(message):
        return

    pro = await message.reply("<b><blockquote>⏳ Processing request... Please wait.</blockquote></b>", quote=True)
    admin_ids = await db.get_all_admins()
    admins = message.text.split()[1:]

    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Close", callback_data="close", style="danger")]])

    if not admins:
        return await pro.edit(
            "<b>Please provide valid admin ID(s) to remove.</b>\n\n"
            "<b>Usage:</b>\n"
            "<code>/deladmin [user_id]</code> — Remove specific IDs\n"
            "<code>/deladmin all</code> — Remove all admins",
            reply_markup=reply_markup
        )

    if len(admins) == 1 and admins[0].lower() == "all":
        if admin_ids:
            for a in admin_ids:
                await db.del_admin(a)
            ids = "\n".join(f"<blockquote><code>{admin}</code> ✅</blockquote>" for admin in admin_ids)
            return await pro.edit(f"<b>⛔️ All admin IDs have been removed:</b>\n{ids}", reply_markup=reply_markup)
        else:
            return await pro.edit("<b><blockquote>No admin IDs to remove.</blockquote></b>", reply_markup=reply_markup)

    if admin_ids:
        passed = ''
        for admin_id in admins:
            try:
                aid = int(admin_id)
            except:
                passed += f"<blockquote><b>Invalid ID: <code>{admin_id}</code></b></blockquote>\n"
                continue

            if aid in admin_ids:
                await db.del_admin(aid)
                passed += f"<blockquote><code>{aid}</code> ✅ Removed</blockquote>\n"
            else:
                passed += f"<blockquote><b>ID <code>{aid}</code> not found in admin list.</b></blockquote>\n"

        await pro.edit(f"<b>⛔️ Admin removal result:</b>\n\n{passed}", reply_markup=reply_markup)
    else:
        await pro.edit("<b><blockquote>No admin IDs available to delete.</blockquote></b>", reply_markup=reply_markup)


@Bot.on_message(filters.command('admins') & filters.private)
async def get_admins(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return

    pro = await message.reply("<b><blockquote>⏳ Fetching admin list...</blockquote></b>", quote=True)
    admin_ids = await db.get_all_admins()

    if not admin_ids:
        admin_list = "<b><blockquote>❌ No additional admins added.</blockquote></b>"
    else:
        admin_list = "\n".join(f"<b><blockquote>• Admin ID: <code>{id}</code></blockquote></b>" for id in admin_ids)

    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Close", callback_data="close", style="danger")]])
    await pro.edit(f"<b>⚡ Current Admin List:</b>\n\n{admin_list}", reply_markup=reply_markup)


@Bot.on_message(filters.command('delete') & filters.private)
async def delete_content_command(client: Client, message: Message):
    """
    Deletes message(s) from this specific bot's database channel.
    Only enabled for the admin/owner of the specific bot where the command is used.
    """
    if not await check_admin_or_owner(message):
        return

    # Identify the target DB channel specifically for this bot client
    target_db_channel = getattr(client, "db_channel", None)
    target_db_id = target_db_channel.id if target_db_channel else CHANNEL_ID

    if not target_db_id:
        return await message.reply("<b>❌ DB Channel is not configured for this bot.</b>", quote=True)

    msg_ids_to_delete = []

    # Case 1: Command invoked as a reply to a message or link
    if message.reply_to_message:
        reply_msg_id = await get_message_id(client, message.reply_to_message)
        if reply_msg_id:
            msg_ids_to_delete.append(reply_msg_id)

    # Case 2: Command arguments provided (e.g. /delete 100 or /delete 100-110 or /delete <link>)
    args = message.text.split()[1:]
    if args:
        for arg in args:
            arg_str = arg.strip()
            # Check for range: e.g. 100-110
            if "-" in arg_str and not arg_str.startswith("-100"):
                parts = arg_str.split("-")
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    start_id, end_id = int(parts[0]), int(parts[1])
                    if start_id > end_id:
                        start_id, end_id = end_id, start_id
                    msg_ids_to_delete.extend(range(start_id, end_id + 1))
                    continue

            # Check if link or single ID
            parsed_id = await get_message_id(client, message)
            if parsed_id and parsed_id not in msg_ids_to_delete:
                msg_ids_to_delete.append(parsed_id)
            elif arg_str.isdigit():
                val = int(arg_str)
                if val not in msg_ids_to_delete:
                    msg_ids_to_delete.append(val)

    # Deduplicate while preserving order
    unique_ids = []
    for mid in msg_ids_to_delete:
        if mid > 0 and mid not in unique_ids:
            unique_ids.append(mid)

    if not unique_ids:
        return await message.reply(
            "<b>🗑️ Delete Content Usage:</b>\n\n"
            "• Reply to a forwarded post/link with <code>/delete</code>\n"
            "• <code>/delete <message_id></code> — Delete a specific message\n"
            "• <code>/delete <start_id>-<end_id></code> — Delete a range of messages\n"
            "• <code>/delete <post_link></code> — Delete content by link",
            quote=True
        )

    pro_msg = await message.reply(f"<b>⏳ Deleting {len(unique_ids)} message(s) from DB channel...</b>", quote=True)
    deleted_count = 0
    failed_count = 0

    chunk_size = 100
    for i in range(0, len(unique_ids), chunk_size):
        chunk = unique_ids[i:i + chunk_size]
        try:
            await client.delete_messages(chat_id=target_db_id, message_ids=chunk)
            deleted_count += len(chunk)
        except Exception as e:
            # If batch delete fails, try individual deletions
            for mid in chunk:
                try:
                    await client.delete_messages(chat_id=target_db_id, message_ids=mid)
                    deleted_count += 1
                except Exception:
                    failed_count += 1

    bot_un = getattr(client, "username", None) or "this bot"
    await pro_msg.edit(
        f"<b>✅ Delete operation complete for @{bot_un}!</b>\n\n"
        f"• <b>Target DB Channel:</b> <code>{target_db_id}</code>\n"
        f"• <b>Successfully Deleted:</b> <code>{deleted_count}</code>\n"
        f"• <b>Failed / Not Found:</b> <code>{failed_count}</code>"
    )

# =====================================================================================##
#                         ✨ MADE BY ANIZONEFLIX ✨
#                  Join Updates Channel: https://t.me/anizoneflix
#====================================================================================##
