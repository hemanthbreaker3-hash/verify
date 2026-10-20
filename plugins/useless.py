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
from datetime import datetime, timedelta
from pyrogram import Client, filters, __version__
from pyrogram.enums import ParseMode, ChatAction
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, ChatInviteLink, ChatPrivileges
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated, UserNotParticipant
from bot import Bot
from config import *
from helper_func import *
from database.database import *
from plugins.anizoneflix import check_owner_only, check_admin_or_owner


@Bot.on_message(filters.command('stats'))
async def stats(bot: Bot, message: Message):
    if not await check_admin_or_owner(message):
        return

    uptime = getattr(bot, "uptime", None)
    if not uptime:
        bot.uptime = datetime.now()
        uptime = bot.uptime
    now = datetime.now()
    delta = now - uptime
    uptime_str = get_readable_time(int(delta.total_seconds()))
    if not uptime_str:
        uptime_str = "0s"

    import psutil
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent

    users = await db.full_userbase()
    users_count = len(users)

    await message.reply(BOT_STATS_TEXT.format(
        uptime=uptime_str,
        cpu=cpu,
        ram=ram,
        users=users_count
    ))



WAIT_MSG = "<b><blockquote>⏳ Processing request... Please wait a moment.</blockquote></b>"


@Bot.on_message(filters.command('users') & filters.private)
async def get_users(client: Bot, message: Message):
    if not await check_admin_or_owner(message):
        return
    msg = await client.send_message(chat_id=message.chat.id, text=WAIT_MSG)
    users = await db.full_userbase()
    await msg.edit(f"<b><blockquote>👥 Total Registered Users: <code>{len(users)}</code></blockquote></b>")


@Bot.on_message(filters.private & filters.command('dlt_time'))
async def set_delete_time(client: Bot, message: Message):
    if not await check_admin_or_owner(message):
        return
    try:
        duration = int(message.command[1])
        await db.set_del_timer(duration)
        await message.reply(f"<b><blockquote>✅ Auto-delete timer updated to <code>{duration}</code> seconds.</blockquote></b>")

    except (IndexError, ValueError):
        await message.reply("<b><blockquote>❌ Usage: <code>/dlt_time <seconds></code></blockquote></b>")

@Bot.on_message(filters.private & filters.command('check_dlt_time'))
async def check_delete_time(client: Bot, message: Message):
    if not await check_admin_or_owner(message):
        return
    duration = await db.get_del_timer()
    await message.reply(f"<b><blockquote>⏱️ Current auto-delete timer: <code>{duration}</code> seconds.</blockquote></b>")


@Bot.on_message(filters.private & filters.command('retrieve_on'))
async def retrieve_on_command(client: Bot, message: Message):
    if not await check_admin_or_owner(message):
        return
    await db.set_retrieve_status(True)
    await message.reply("<b><blockquote>✅ File retrieval alert enabled! 'Get File Again' button will be active after deletion.</blockquote></b>")


@Bot.on_message(filters.private & filters.command('retrieve_off'))
async def retrieve_off_command(client: Bot, message: Message):
    if not await check_admin_or_owner(message):
        return
    await db.set_retrieve_status(False)
    await message.reply("<b><blockquote>❌ File retrieval alert disabled! Messages will be completely deleted.</blockquote></b>")


@Bot.on_message(filters.command('ping'))
async def ping(bot: Bot, message: Message):
    start_time = time.time()
    reply = await message.reply("<b><blockquote>🏓 Pinging system...</blockquote></b>")
    end_time = time.time()
    latency = (end_time - start_time) * 1000
    await reply.edit(f"<b><blockquote>🏓 Pong! Latency: <code>{latency:.2f} ms</code></blockquote></b>")

# =====================================================================================##
#                         ✨ MADE BY ANIZONEFLIX ✨
#                  Join Updates Channel: https://t.me/anizoneflix
#====================================================================================##
