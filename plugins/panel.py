import re
from datetime import datetime, timezone
# =====================================================================================##
#                         ✨ MADE BY ANIZONEFLIX ✨
#                  Join Updates Channel: https://t.me/anizoneflix
#=====================================================================================##

import asyncio
import os
import psutil
import time
import traceback
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from bot import Bot
from config import OWNER_ID, TG_BOT_TOKEN
from database.database import db
from plugins.anizoneflix import check_admin_or_owner, is_admin, is_owner

active_clones = {}

def build_panel_menu():
    buttons = [
        [InlineKeyboardButton("⚙️ Core Config", callback_data="panel_core", style="primary"), InlineKeyboardButton("👥 Admin Manager", callback_data="panel_admins", style="primary")],
        [InlineKeyboardButton("🗄️ DB Channels", callback_data="panel_db_channels", style="primary"), InlineKeyboardButton("📢 Force Sub", callback_data="panel_fsub", style="primary")],
        [InlineKeyboardButton("🛡️ Verification", callback_data="panel_verify", style="primary"), InlineKeyboardButton("🧾 Verify Log", callback_data="panel_verify_log", style="primary")],
        [InlineKeyboardButton("🌐 Set API Base URL", callback_data="panel_set_api_base_url", style="primary")],
        [InlineKeyboardButton("🔗 Shorteners", callback_data="panel_shortener", style="primary")],
        [InlineKeyboardButton("🤖 Clone Bots", callback_data="panel_clones", style="primary"), InlineKeyboardButton("🖼️ Images", callback_data="panel_images", style="primary")],
        [InlineKeyboardButton("🔘 Custom Button", callback_data="panel_custom_btn", style="primary"), InlineKeyboardButton("📊 Statistics", callback_data="panel_stats", style="primary")],
        [InlineKeyboardButton("🧭 Referer Settings", callback_data="panel_referrer", style="primary")],
        [InlineKeyboardButton("🔄 Restart & Sync", callback_data="panel_sync", style="success"), InlineKeyboardButton("❌ Close", callback_data="close", style="danger")]
    ]
    return InlineKeyboardMarkup(buttons)

@Bot.on_message(filters.command("panel") & filters.private)
async def panel_command(client: Client, message: Message):
    try:
        if not await check_admin_or_owner(message):
            return

        me = await client.get_me()
        username = f"@{me.username}" if getattr(me, "username", None) else "<i>Unavailable</i>"
        bot_link = f"https://t.me/{me.username}" if getattr(me, "username", None) else "Not available"
        text = (
            "<b>✨ ᴀɴɪᴢᴏɴᴇғʟɪx — Control Panel</b>\n"
            f"<b>🤖 Verify Bot Username:</b> {username}\n"
            f"<b>🔗 Bot Link:</b> <code>{bot_link}</code>\n\n"
            "<i>Welcome to the centralized management dashboard. Select a module below to configure your bot:</i>"
        )
        await message.reply_text(text, reply_markup=build_panel_menu())
    except Exception as e:
        traceback.print_exc()
        await message.reply_text(f"<b>❌ Panel Error:</b> <code>{e}</code>")

async def start_all_clones(main_client: Client):
    try:
        clones = await db.get_all_clones()
        for clone in clones:
            if not clone.get('enabled', True):
                continue
            username = clone['bot_username']
            token = clone['bot_token']
            channel_id = clone['db_channel_id']
            if username in active_clones:
                continue
            try:
                clone_app = Client(
                    name=f"clone_{username}",
                    api_id=main_client.api_id,
                    api_hash=main_client.api_hash,
                    bot_token=token,
                    plugins={"root": "plugins"}
                )
                await clone_app.start()
                try:
                    clone_app.db_channel = await clone_app.get_chat(channel_id)
                except Exception:
                    class ChannelObj:
                        def __init__(self, cid): self.id = cid
                    clone_app.db_channel = ChannelObj(channel_id)

                # Send test message to clone bot's own DB channel upon startup
                try:
                    probe_msg = await clone_app.send_message(chat_id=clone_app.db_channel.id, text="Clone DB Test Message")
                    await probe_msg.delete()
                except Exception as db_err:
                    print(f"Clone bot @{username} failed to write to DB channel {channel_id}: {db_err}")

                active_clones[username] = clone_app
                try:
                    await clone_app.send_message(OWNER_ID, text=f"<b><blockquote>🤖 Cʟᴏɴᴇ Bᴏᴛ @{username} Rᴇsᴛᴀʀᴛᴇᴅ Sᴜᴄᴄᴇssғᴜʟʟʏ by @anizoneflix</blockquote></b>")
                except Exception:
                    pass
            except Exception as e:
                print(f"Failed to start clone {username}: {e}")
    except Exception as e:
        print(f"Error in start_all_clones: {e}")

# ==================== Clone Bot Direct Commands ====================
@Bot.on_message(filters.command("addclone") & filters.private)
async def add_clone_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return
    args = message.text.split()
    if len(args) < 4:
        return await message.reply_text(
            "<b>Usage:</b> <code>/addclone <bot_username> <bot_token> <db_channel_id></code>\n\n"
            "<i>Example:</i> <code>/addclone MyCloneBot 123456:ABC-DEF -1001234567890</code>"
        )
    username = args[1].replace("@", "").strip()
    token = args[2].strip()
    try:
        db_channel_id = int(args[3])
    except ValueError:
        return await message.reply_text("<b>Error:</b> DB Channel ID must be an integer.")

    await db.add_clone(username, token, db_channel_id)
    btn = [[InlineKeyboardButton("🤖 View Clones Panel", callback_data="panel_clones", style="primary")]]
    await message.reply_text(f"<b>✅ Clone bot @{username} added successfully!</b>", reply_markup=InlineKeyboardMarkup(btn))

@Bot.on_message(filters.command("delclone") & filters.private)
async def del_clone_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return
    args = message.text.split()
    if len(args) < 2:
        return await message.reply_text("<b>Usage:</b> <code>/delclone <bot_username></code>")
    username = args[1].replace("@", "").strip()
    await db.delete_clone(username)
    if username in active_clones:
        try:
            await active_clones[username].stop()
        except Exception:
            pass
        active_clones.pop(username, None)
    btn = [[InlineKeyboardButton("🤖 View Clones Panel", callback_data="panel_clones", style="primary")]]
    await message.reply_text(f"<b>✅ Clone bot @{username} removed successfully!</b>", reply_markup=InlineKeyboardMarkup(btn))

@Bot.on_message(filters.command("clones") & filters.private)
async def list_clones_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return
    clones = await db.get_all_clones()
    if not clones:
        return await message.reply_text("<b>No clone bots configured.</b>")
    text = "<b>🤖 Configured Clone Bots:</b>\n\n"
    for c in clones:
        text += f"• @{c['bot_username']} | DB: <code>{c['db_channel_id']}</code> | Status: {'🟢 Active' if c['bot_username'] in active_clones else '🔴 Inactive'}\n"
    btn = [[InlineKeyboardButton("🤖 Manage Clones", callback_data="panel_clones", style="primary")]]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btn))

# ==================== Shortener Direct Commands ====================
@Bot.on_message(filters.command("addshortener") & filters.private)
async def add_shortener_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return
    args = message.text.split()
    if len(args) < 3:
        return await message.reply_text("<b>Usage:</b> <code>/addshortener <domain> <api_key></code>")
    domain = args[1].strip()
    api_key = args[2].strip()
    s_id = await db.add_shortener(domain, api_key)
    btn = [[InlineKeyboardButton("🔗 Shorteners Panel", callback_data="panel_shortener", style="primary")]]
    await message.reply_text(f"<b>✅ Shortener {domain} added successfully!</b> (ID: <code>{s_id}</code>)", reply_markup=InlineKeyboardMarkup(btn))

@Bot.on_message(filters.command("delshortener") & filters.private)
async def del_shortener_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return
    shorteners = await db.get_shorteners()
    if not shorteners:
        return await message.reply_text("<b>No active shorteners to delete.</b>")

    buttons = []
    for s in shorteners:
        buttons.append([InlineKeyboardButton(f"🗑️ Delete {s['domain']}", callback_data=f"panel_del_short_{s['_id']}", style="danger")])
    buttons.append([InlineKeyboardButton("‹ Back to Panel", callback_data="panel_main", style="primary")])

    await message.reply_text("<b>🗑️ Select a shortener below to delete instantly:</b>", reply_markup=InlineKeyboardMarkup(buttons))

@Bot.on_message(filters.command("shorteners") & filters.private)
async def list_shorteners_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return
    shorteners = await db.get_shorteners()
    if not shorteners:
        return await message.reply_text("<b>No shorteners configured.</b>")
    text = "<b>🔗 Configured Shorteners:</b>\n\n"
    for s in shorteners:
        text += f"• ID: <code>{s['_id']}</code> | Domain: <b>{s['domain']}</b> | Key: <code>{s['api_key'][:4]}***</code>\n"
    btn = [[InlineKeyboardButton("🔗 Manage Shorteners", callback_data="panel_shortener", style="primary")]]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btn))

# ==================== DB Channel Direct Commands ====================
@Bot.on_message(filters.command("add_db_channel") & filters.private)
async def add_db_channel_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return
    args = message.text.split()
    if len(args) < 2:
        return await message.reply_text("<b>Usage:</b> <code>/add_db_channel <channel_id></code>")
    try:
        cid = int(args[1])
    except ValueError:
        return await message.reply_text("<b>Error:</b> Channel ID must be an integer.")
    await db.add_db_channel(cid)
    btn = [[InlineKeyboardButton("🗄️ DB Channels Panel", callback_data="panel_db_channels", style="primary")]]
    await message.reply_text(f"<b>✅ DB Channel <code>{cid}</code> added successfully!</b>", reply_markup=InlineKeyboardMarkup(btn))

@Bot.on_message(filters.command("del_db_channel") & filters.private)
async def del_db_channel_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return
    args = message.text.split()
    if len(args) < 2:
        return await message.reply_text("<b>Usage:</b> <code>/del_db_channel <channel_id></code>")
    try:
        cid = int(args[1])
    except ValueError:
        return await message.reply_text("<b>Error:</b> Channel ID must be an integer.")
    await db.remove_db_channel(cid)
    btn = [[InlineKeyboardButton("🗄️ DB Channels Panel", callback_data="panel_db_channels", style="primary")]]
    await message.reply_text(f"<b>✅ DB Channel <code>{cid}</code> removed!</b>", reply_markup=InlineKeyboardMarkup(btn))

@Bot.on_message(filters.command("list_db_channels") & filters.private)
async def list_db_channels_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return
    channels = await db.get_db_channels()
    if not channels:
        return await message.reply_text("<b>No secondary DB channels configured.</b>")
    text = "<b>🗄️ Secondary DB Channels:</b>\n\n"
    for c in channels:
        text += f"• <code>{c}</code>\n"
    btn = [[InlineKeyboardButton("🗄️ DB Channels Panel", callback_data="panel_db_channels", style="primary")]]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btn))

# ==================== Verification Log ====================
@Bot.on_message(filters.command("verify_log") & filters.private)
async def verify_log_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return
    args = message.text.split(maxsplit=1)
    current = await db.get_config_val("VERIFY_LOG_CHAT_ID", None)
    if len(args) < 2:
        status = f"<code>{current}</code>" if current else "Not configured"
        return await message.reply_text(
            "<b>🧾 Verification Log Settings</b>\n\n"
            f"<b>Current log group/channel:</b> {status}\\n\\n"
            "Set a destination with <code>/verify_log -1001234567890</code> or disable with <code>/verify_log off</code>.\n"
            "Make sure the main bot can send messages in the destination."
        )
    value = args[1].strip()
    if value.lower() in {"off", "disable", "none"}:
        await db.update_config("VERIFY_LOG_CHAT_ID", None)
        return await message.reply_text("<b>✅ Verification log disabled.</b>")
    try:
        chat_id = int(value)
        chat = await client.get_chat(chat_id)
        await client.send_message(chat_id, "<b>✅ Verification log connected.</b> New successful verifications will be logged here.")
        await db.update_config("VERIFY_LOG_CHAT_ID", chat_id)
        await message.reply_text(f"<b>✅ Verification log configured:</b> <code>{chat.id}</code>")
    except Exception as exc:
        await message.reply_text(
            "<b>❌ Could not configure verification log.</b> Check the group/channel ID, add the bot, and grant permission to send messages.\\n"
            f"<code>{str(exc)[:500]}</code>"
        )


# ==================== Verification Direct Commands ====================
@Bot.on_message(filters.command("verify_on") & filters.private)
async def verify_on_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return
    await db.update_config("VERIFY_ENABLED", True)
    btn = [[InlineKeyboardButton("🛡️ Verification Panel", callback_data="panel_verify", style="primary")]]
    await message.reply_text("<b>🟢 Shortener Verification ENABLED!</b>", reply_markup=InlineKeyboardMarkup(btn))

@Bot.on_message(filters.command("verify_off") & filters.private)
async def verify_off_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return
    await db.update_config("VERIFY_ENABLED", False)
    btn = [[InlineKeyboardButton("🛡️ Verification Panel", callback_data="panel_verify", style="primary")]]
    await message.reply_text("<b>🔴 Shortener Verification DISABLED!</b>", reply_markup=InlineKeyboardMarkup(btn))



# ==================== Restart System Command ====================
@Bot.on_message(filters.command("restart") & filters.private)
async def restart_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return
    msg = await message.reply_text("<b>🔄 Restarting AniZoneFlix Bot System...</b>")
    await asyncio.sleep(1)
    await msg.edit_text("<b>✅ System Restart Triggered! Bot is reloading...</b>")
    os.execl(sys.executable, sys.executable, *sys.argv)

# ==================== Custom Button Direct Commands ====================
@Bot.on_message(filters.command("set_button") & filters.private)
async def set_button_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        return await message.reply_text(
            "<b>Usage:</b> <code>/set_button <Button Text> <Button URL></code>\n\n"
            "<i>Example:</i> <code>/set_button Main Channel https://t.me/anizoneflix</code>"
        )
    b_name = args[1].strip()
    b_url = args[2].strip()
    if not (b_url.startswith("http://") or b_url.startswith("https://") or b_url.startswith("t.me/")):
        b_url = "https://" + b_url

    await db.update_config("CUSTOM_BUTTON_NAME", b_name)
    await db.update_config("CUSTOM_BUTTON_URL", b_url)
    btn = [[InlineKeyboardButton("🔘 Custom Button Panel", callback_data="panel_custom_btn", style="primary")]]
    await message.reply_text(f"<b>✅ Custom Button updated!</b>\n\n<b>Name:</b> {b_name}\n<b>URL:</b> {b_url}", reply_markup=InlineKeyboardMarkup(btn))

@Bot.on_message(filters.command("del_button") & filters.private)
async def del_button_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return
    await db.update_config("CUSTOM_BUTTON_NAME", None)
    await db.update_config("CUSTOM_BUTTON_URL", None)
    btn = [[InlineKeyboardButton("🔘 Custom Button Panel", callback_data="panel_custom_btn", style="primary")]]
    await message.reply_text("<b>✅ Custom Button removed!</b>", reply_markup=InlineKeyboardMarkup(btn))

# ==================== Verification Expire Direct Command ====================
# ==================== Base URL Command ====================
@Bot.on_message(filters.command("set_base_url") & filters.private)
async def set_base_url_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        curr_url = await db.get_config_val("BASE_URL", "https://your-render-service.onrender.com")
        return await message.reply_text(
            f"<b>Usage:</b> <code>/set_base_url <url></code>\n\n"
            f"<b>Current Base URL:</b> <code>{curr_url}</code>\n\n"
            "<i>Example:</i> <code>/set_base_url https://mybot.onrender.com</code>"
        )
    from urllib.parse import urlsplit
    new_url = args[1].strip().rstrip("/")
    if not new_url.startswith(("http://", "https://")):
        new_url = "https://" + new_url
    parsed = urlsplit(new_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return await message.reply_text("<b>❌ Invalid URL.</b> Send a valid HTTPS URL, such as <code>https://your-service.onrender.com</code>.")
    new_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}".rstrip("/")
    saved = await db.update_config("BASE_URL", new_url)
    confirmed = await db.get_config_val("BASE_URL", None)
    if not saved or confirmed != new_url:
        return await message.reply_text("<b>❌ Base URL was not saved.</b> Check MongoDB connectivity and try again.")
    btn = [[InlineKeyboardButton("🛡️ Verification Panel", callback_data="panel_verify", style="primary")]]
    await message.reply_text(
        f"<b>✅ Base URL Updated and Verified</b>\n\n<blockquote><b>New Base URL:</b> <code>{new_url}</code></blockquote>",
        reply_markup=InlineKeyboardMarkup(btn)
    )

# ==================== Session Expiry Command ====================
@Bot.on_message(filters.command("set_session_expire") & filters.private)
async def set_session_expire_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply_text(
            "<b>Usage:</b> <code>/set_session_expire <time></code>\n\n"
            "<i>Examples:</i> <code>1h</code>, <code>30m</code>, <code>3000</code>, or <code>0</code> (Permanent)"
        )
    raw_val = args[1].strip().lower()
    try:
        if raw_val.endswith("h"):
            seconds = int(float(raw_val[:-1]) * 3600)
        elif raw_val.endswith("m"):
            seconds = int(float(raw_val[:-1]) * 60)
        elif raw_val.endswith("d"):
            seconds = int(float(raw_val[:-1]) * 86400)
        elif raw_val.endswith("s"):
            seconds = int(float(raw_val[:-1]))
        else:
            seconds = int(float(raw_val))

        if seconds < 0:
            raise ValueError("Duration cannot be negative.")

        await db.update_config("SESSION_EXPIRE_SECONDS", seconds)
        from helper_func import get_readable_time
        btn = [[InlineKeyboardButton("🛡️ Verification Panel", callback_data="panel_verify", style="primary")]]
        disp_time = get_readable_time(seconds) if seconds > 0 else "Permanent (0s)"
        await message.reply_text(
            f"<b>✅ Session Link Expiry Time Updated!</b>\n\n"
            f"<b>Duration:</b> <code>{disp_time}</code> ({seconds} seconds)",
            reply_markup=InlineKeyboardMarkup(btn)
        )
    except Exception as e:
        await message.reply_text(f"<b>❌ Error setting session duration:</b> <code>{e}</code>")

@Bot.on_message(filters.command("set_verify_expire") & filters.private)
async def set_verify_expire_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply_text(
            "<b>Usage:</b> <code>/set_verify_expire <time></code>\n\n"
            "<i>Examples:</i> <code>24h</code>, <code>12h</code>, <code>30m</code>, or <code>86400</code>"
        )
    raw_val = args[1].strip().lower()
    try:
        if raw_val.endswith("h"):
            seconds = int(float(raw_val[:-1]) * 3600)
        elif raw_val.endswith("m"):
            seconds = int(float(raw_val[:-1]) * 60)
        elif raw_val.endswith("d"):
            seconds = int(float(raw_val[:-1]) * 86400)
        elif raw_val.endswith("s"):
            seconds = int(float(raw_val[:-1]))
        else:
            seconds = int(float(raw_val))

        if seconds <= 0:
            raise ValueError("Duration must be greater than 0.")

        await db.update_config("VERIFY_EXPIRE_SECONDS", seconds)
        from helper_func import get_readable_time
        btn = [[InlineKeyboardButton("🛡️ Verification Panel", callback_data="panel_verify", style="primary")]]
        await message.reply_text(
            f"<b>✅ Verification Expire Time Updated!</b>\n\n"
            f"<b>Duration:</b> <code>{get_readable_time(seconds)}</code> ({seconds} seconds)",
            reply_markup=InlineKeyboardMarkup(btn)
        )
    except Exception as e:
        await message.reply_text(f"<b>❌ Error setting duration:</b> <code>{e}</code>")


# ==================== Reset Verification Command ====================
@Bot.on_message(filters.command("reset") & filters.private)
async def reset_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return
    args = message.text.split()[1:]
    if not args:
        return await message.reply_text(
            "<b>Usage:</b>\n"
            "• <code>/reset all</code> - Expire verification for ALL users instantly.\n"
            "• <code>/reset <user_id> [user_id2 ...]</code> - Expire verification for specific user ID(s)."
        )

    if args[0].lower() == "all":
        await db.reset_all_verified_users()
        return await message.reply_text("<b>✅ Verification expired for ALL users instantly!</b>")

    user_ids = []
    for arg in args:
        if arg.isdigit():
            user_ids.append(int(arg))

    if not user_ids:
        return await message.reply_text("<b>❌ Please provide valid integer user ID(s) or 'all'.</b>")

    deleted_count = await db.reset_verified_users(user_ids)
    await message.reply_text(f"<b>✅ Expired verification for {deleted_count} user(s).</b>")


# ==================== /count Command ====================
@Bot.on_message(filters.command("count") & filters.private)
async def count_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return

    from zoneinfo import ZoneInfo
    ist_tz = ZoneInfo("Asia/Kolkata")
    args = message.text.split()[1:]
    filter_date = None
    filter_label = "All Time"

    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc.astimezone(ist_tz)

    if args:
        raw_arg = args[0].strip().lower()
        if raw_arg in ["today", "td"]:
            filter_date = now_ist.date()
            filter_label = f"Today ({filter_date.strftime('%d-%b-%Y')})"
        elif raw_arg in ["yesterday", "yd"]:
            from datetime import timedelta
            filter_date = (now_ist - timedelta(days=1)).date()
            filter_label = f"Yesterday ({filter_date.strftime('%d-%b-%Y')})"
        else:
            for fmt in ["%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"]:
                try:
                    filter_date = datetime.strptime(raw_arg, fmt).date()
                    filter_label = filter_date.strftime("%d-%b-%Y")
                    break
                except ValueError:
                    pass
            if not filter_date:
                return await message.reply_text(
                    "<b><blockquote>❌ Invalid date format. Use DD-MM-YYYY, DD/MM/YYYY, 'today', or 'yesterday'.</blockquote></b>"
                )

    verified_users = await db.get_all_verified_users()
    report_items = []
    matched_count = 0
    active_count = 0
    expired_count = 0

    for idx, u in enumerate(verified_users, start=1):
        uid = u.get('_id')
        username = u.get('username', '')
        first_name = u.get('first_name', '')
        u_str = f"@{username}" if username else "None"
        fn_str = first_name if first_name else "N/A"

        ver_at = u.get('verified_at')
        exp_at = u.get('expire_at')

        ver_ist_str = "N/A"
        exp_ist_str = "N/A"
        rem_str = "Expired"
        is_active = False

        if ver_at:
            if hasattr(ver_at, "tzinfo") and ver_at.tzinfo is None:
                ver_at = ver_at.replace(tzinfo=timezone.utc)
            ver_ist = ver_at.astimezone(ist_tz)
            ver_ist_str = ver_ist.strftime("%d-%b-%Y %H:%M:%S IST")

        if filter_date:
            if not ver_at or ver_at.astimezone(ist_tz).date() != filter_date:
                continue

        if exp_at:
            if hasattr(exp_at, "tzinfo") and exp_at.tzinfo is None:
                exp_at = exp_at.replace(tzinfo=timezone.utc)
            exp_ist = exp_at.astimezone(ist_tz)
            exp_ist_str = exp_ist.strftime("%d-%b-%Y %H:%M:%S IST")

            if exp_at > now_utc:
                is_active = True
                rem_sec = int((exp_at - now_utc).total_seconds())
                from helper_func import get_readable_time
                rem_str = get_readable_time(rem_sec)

        matched_count += 1
        if is_active:
            active_count += 1
        else:
            expired_count += 1

        status_emoji = "🟢 Active" if is_active else "🔴 Expired"
        item = (
            f"<b><blockquote>{matched_count}. User Record ({status_emoji}):\n"
            f"• Name: {fn_str} | Username: {u_str}\n"
            f"• User ID: <code>{uid}</code>\n"
            f"• Verified: <code>{ver_ist_str}</code>\n"
            f"• Expires: <code>{exp_ist_str}</code>\n"
            f"• Remaining: <code>{rem_str}</code></blockquote></b>"
        )
        report_items.append(item)

    if not report_items:
        return await message.reply_text(
            f"<b><blockquote>📊 No verified user records found for filter: {filter_label}.</blockquote></b>"
        )

    header = (
        f"<b>📊 Verified Users Count Report</b>\n\n"
        f"<b><blockquote>• Total Users Recorded: <code>{matched_count}</code>\n"
        f"• Active Verified: <code>{active_count}</code>\n"
        f"• Expired Verification: <code>{expired_count}</code>\n"
        f"• Date Filter: <code>{filter_label}</code></blockquote></b>\n\n"
    )

    parts = []
    current_part = header

    for item in report_items:
        if len(current_part) + len(item) > 3800:
            parts.append(current_part)
            current_part = item + "\n\n"
        else:
            current_part += item + "\n\n"
    if current_part:
        parts.append(current_part)

    for p in parts:
        await message.reply_text(p)


# ==================== Premium Management Commands ====================
def parse_duration_string(text):
    text = text.strip().lower()
    pattern = r"(\d+)\s*([a-z]+)?"
    matches = re.findall(pattern, text)
    if not matches:
        return None

    total_seconds = 0
    for num_str, unit in matches:
        if not num_str:
            continue
        val = int(num_str)
        if not unit or unit.startswith("s"):
            total_seconds += val
        elif unit.startswith("min") or unit == "m":
            total_seconds += val * 60
        elif unit.startswith("h"):
            total_seconds += val * 3600
        elif unit.startswith("d"):
            total_seconds += val * 86400
        elif unit.startswith("mon") or unit.startswith("mo"):
            total_seconds += val * 30 * 86400
        elif unit.startswith("y"):
            total_seconds += val * 365 * 86400
    return total_seconds if total_seconds > 0 else None

@Bot.on_message(filters.command("addpremium") & filters.private)
async def addpremium_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        return await message.reply_text(
            "<b>Usage:</b> <code>/addpremium <user_id or @username> <duration></code>\n\n"
            "<i>Examples:</i>\n"
            "• <code>/addpremium 123456789 1 hour</code>\n"
            "• <code>/addpremium @username 7 days</code>\n"
            "• <code>/addpremium 123456789 30 minutes</code>"
        )

    target_user = args[1].strip()
    duration_str = args[2].strip()

    duration_sec = parse_duration_string(duration_str)
    if not duration_sec:
        return await message.reply_text("<b>❌ Invalid duration string. Example units: minutes, hours, days, years.</b>")

    target_uid = None
    target_un = ""

    if target_user.isdigit():
        target_uid = int(target_user)
        try:
            chat = await client.get_users(target_uid)
            target_un = chat.username or ""
        except Exception:
            pass
    else:
        try:
            chat = await client.get_users(target_user)
            target_uid = chat.id
            target_un = chat.username or target_user.replace("@", "")
        except Exception as e:
            return await message.reply_text(f"<b>❌ Could not find user {target_user}:</b> <code>{e}</code>")

    await db.add_premium_user(target_uid, target_un, duration_sec)
    from helper_func import get_readable_time
    await message.reply_text(
        f"<b>✅ Premium Granted!</b>\n\n"
        f"• <b>User ID:</b> <code>{target_uid}</code>\n"
        f"• <b>Username:</b> @{target_un or 'None'}\n"
        f"• <b>Duration:</b> <code>{get_readable_time(duration_sec)}</code>"
    )

    try:
        await client.send_message(
            chat_id=target_uid,
            text=(
                f"🎉 <b>PREMIUM ACTIVATED INSTANTLY!</b>\n\n"
                f"✨ <b>Congratulations!</b> You have been granted Premium access.\n"
                f"⌛ <b>Duration:</b> <code>{get_readable_time(duration_sec)}</code>\n\n"
                f"<i>Enjoy ad-free instant access to all files without verification links!</i> 🚀"
            )
        )
    except Exception as notify_err:
        print(f"Failed to send instant premium activation message: {notify_err}")

@Bot.on_message(filters.command("delpremium") & filters.private)
async def delpremium_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply_text("<b>Usage:</b> <code>/delpremium <user_id or @username></code>")

    target = args[1].strip()
    removed = await db.del_premium_user(target)
    if removed:
        await message.reply_text(f"<b>✅ Premium status removed for {target}.</b>")
        if target.isdigit():
            try:
                await client.send_message(
                    chat_id=int(target),
                    text=(
                        f"<b>⚠️ YOUR PREMIUM STATUS HAS EXPIRED!</b>\n\n"
                        f"Your premium access period has ended. Contact support to renew your premium access anytime."
                    )
                )
            except Exception:
                pass
    else:
        await message.reply_text(f"<b>❌ User {target} not found in premium list.</b>")

@Bot.on_message(filters.command("premium_users") & filters.private)
async def list_premium_users_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return

    from zoneinfo import ZoneInfo
    ist_tz = ZoneInfo("Asia/Kolkata")
    premiums = await db.get_all_premium_users()

    if not premiums:
        return await message.reply_text("<b>💎 No active premium users found.</b>")

    now_utc = datetime.now(timezone.utc)
    report_items = []

    for idx, p in enumerate(premiums, start=1):
        uid = p.get('_id')
        un = p.get('username', '')
        u_str = f"@{un}" if un else "None"

        start_at = p.get('start_at') or p.get('created_at')
        exp_at = p.get('expire_at')

        start_str = "N/A"
        exp_str = "N/A"
        rem_str = "Expired"
        status = "🔴 Expired"

        if start_at:
            if hasattr(start_at, "tzinfo") and start_at.tzinfo is None:
                start_at = start_at.replace(tzinfo=timezone.utc)
            start_str = start_at.astimezone(ist_tz).strftime("%d-%b-%Y %H:%M:%S IST")

        if exp_at:
            if hasattr(exp_at, "tzinfo") and exp_at.tzinfo is None:
                exp_at = exp_at.replace(tzinfo=timezone.utc)
            exp_str = exp_at.astimezone(ist_tz).strftime("%d-%b-%Y %H:%M:%S IST")

            if exp_at > now_utc:
                status = "🟢 Active"
                rem_sec = int((exp_at - now_utc).total_seconds())
                from helper_func import get_readable_time
                rem_str = get_readable_time(rem_sec)

        item = (
            f"<b>{idx}. Premium User:</b>\n"
            f"• <b>Username:</b> {u_str}\n"
            f"• <b>User ID:</b> <code>{uid}</code>\n"
            f"• <b>Premium Start:</b> <code>{start_str}</code>\n"
            f"• <b>Premium Expire:</b> <code>{exp_str}</code>\n"
            f"• <b>Remaining Time:</b> <code>{rem_str}</code>\n"
            f"• <b>Status:</b> {status}\n"
        )
        report_items.append(item)

    header = f"<b>💎 Active Premium Users ({len(premiums)} Total):</b>\n\n"
    parts = []
    current_part = header

    for item in report_items:
        if len(current_part) + len(item) > 3800:
            parts.append(current_part)
            current_part = header + item
        else:
            current_part += item + "\n"
    if current_part:
        parts.append(current_part)

    for p in parts:
        await message.reply_text(p)


async def _panel_callback_allowed(query: CallbackQuery) -> bool:
    """Callback-safe authorization; unlike Message, CallbackQuery has no reply()."""
    user = getattr(query, "from_user", None)
    if not user:
        return False
    uid = int(user.id)
    try:
        owner_id = int(OWNER_ID)
    except (TypeError, ValueError):
        owner_id = -1
    if uid == owner_id:
        return True
    try:
        admins = await db.get_all_admins() or []
        return uid in {int(x) for x in admins}
    except Exception:
        return False


@Bot.on_callback_query(filters.regex(r"^panel_verify_log$"))
async def verify_log_panel_callback(client: Client, query: CallbackQuery):
    try:
        if not await _panel_callback_allowed(query):
            await query.answer("Admins only", show_alert=True)
            return
        current = await db.get_config_val("VERIFY_LOG_CHAT_ID", None)
        status = f"<code>{current}</code>" if current else "<i>Not configured</i>"
        text = (
            "<b>🧾 Verification Log Settings</b>\n\n"
            f"<b>Status:</b> {status}\n\n"
            "Configure the destination using one of these commands in this private chat:\n"
            "• <code>/verify_log -1001234567890</code> — set a group/channel\n"
            "• <code>/verify_log off</code> — disable logging\n\n"
            "The <b>main bot</b> must be able to post in the destination. Clone bots do not need channel admin rights."
        )
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="panel_verify_log", style="primary")],
            [InlineKeyboardButton("‹ Back to Panel", callback_data="panel_main", style="primary")],
        ])
        await query.answer()
        try:
            await query.message.edit_text(text, reply_markup=buttons)
        except Exception as edit_exc:
            # For old messages that cannot be edited, send a fresh settings message.
            if "message is not modified" not in str(edit_exc).lower():
                await query.message.reply_text(text, reply_markup=buttons)
    except Exception as exc:
        try:
            await query.answer(f"Verify Log error: {str(exc)[:120]}", show_alert=True)
        except Exception:
            pass


@Bot.on_callback_query(filters.regex(r"^panel_main$"))
async def panel_main_callback(client: Client, query: CallbackQuery):
    try:
        if not await _panel_callback_allowed(query):
            await query.answer("Admins only", show_alert=True)
            return
        await query.answer()
        await query.message.edit_text(
            "<b>✨ ᴀɴɪᴢᴏɴᴇғʟɪx — Control Panel</b>\n"
            "<i>Select a module below to configure your bot.</i>",
            reply_markup=build_panel_menu(),
        )
    except Exception as exc:
        try:
            await query.answer(f"Panel error: {str(exc)[:120]}", show_alert=True)
        except Exception:
            pass
