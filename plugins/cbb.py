import re
from pyrogram import Client, filters
from bot import Bot
from config import *
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database.database import *
from helper_func import get_next_image

from pyrogram.types import InputMediaPhoto

@Bot.on_callback_query(filters.regex("^(help|about|start|close|rfs_ch_|rfs_toggle_|fsub_back)"))
async def cb_handler(client: Bot, query: CallbackQuery):
    data = query.data

    if data == "help":
        await query.answer()
        from plugins.help import get_help_page_content
        text, reply_markup = get_help_page_content(1)

        if query.message.photo or query.message.document or query.message.video or query.message.animation:
            await query.message.edit_media(
                media=InputMediaPhoto(
                    media=get_next_image(query.message.chat.id),
                    caption=text,
                    has_spoiler=True
                ),
                reply_markup=reply_markup
            )
        else:
            await query.message.edit_text(
                text=text,
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )

    elif data == "about":
        await query.answer()
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton('🏠 Home', callback_data='start', style="primary"),
             InlineKeyboardButton('✖️ Close', callback_data='close', style="danger")]
        ])

        if query.message.photo or query.message.document or query.message.video or query.message.animation:
            await query.message.edit_media(
                media=InputMediaPhoto(
                    media=get_next_image(query.message.chat.id),
                    caption=ABOUT_TXT.replace("{first}", query.from_user.first_name),
                    has_spoiler=True
                ),
                reply_markup=reply_markup
            )
        else:
            await query.message.edit_text(
                text=ABOUT_TXT.replace("{first}", query.from_user.first_name),
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )

    elif data == "start":
        await query.answer()
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton('📢 Main Channel', url='https://t.me/anizoneflix', style="primary"),
             InlineKeyboardButton('💬 Support', url='https://t.me/anizoneflix', style="primary")],
            [InlineKeyboardButton('ℹ️ About', callback_data='about', style="primary"),
             InlineKeyboardButton('📜 Help', callback_data='help', style="primary")],
            [InlineKeyboardButton("🚀 Join Updates Channel", url='https://t.me/anizoneflix', style="success")]
        ])

        if query.message.photo or query.message.document or query.message.video or query.message.animation:
            caption = START_MSG
            if "{first}" in caption: caption = caption.replace("{first}", query.from_user.first_name or "")
            if "{last}" in caption: caption = caption.replace("{last}", query.from_user.last_name or "")
            if "{username}" in caption: caption = caption.replace("{username}", "" if not query.from_user.username else '@' + query.from_user.username)
            if "{mention}" in caption: caption = caption.replace("{mention}", query.from_user.mention or "")
            if "{id}" in caption: caption = caption.replace("{id}", str(query.from_user.id))

            await query.message.edit_media(
                media=InputMediaPhoto(
                    media=get_next_image(query.message.chat.id),
                    caption=caption,
                    has_spoiler=True
                ),
                reply_markup=reply_markup
            )
        else:
            text = START_MSG
            if "{first}" in text: text = text.replace("{first}", query.from_user.first_name or "")
            if "{last}" in text: text = text.replace("{last}", query.from_user.last_name or "")
            if "{username}" in text: text = text.replace("{username}", "" if not query.from_user.username else '@' + query.from_user.username)
            if "{mention}" in text: text = text.replace("{mention}", query.from_user.mention or "")
            if "{id}" in text: text = text.replace("{id}", str(query.from_user.id))

            await query.message.edit_text(
                text=text,
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )

    elif data == "close":
        await query.answer()
        await query.message.delete()
        try:
            await query.message.reply_to_message.delete()
        except:
            pass

    elif data.startswith("rfs_ch_"):
        await query.answer()
        cid = int(data.split("_")[2])
        try:
            chat = await client.get_chat(cid)
            mode = await db.get_channel_mode(cid)
            status = "🟢 ᴏɴ" if mode == "on" else "🔴 ᴏғғ"
            new_mode = "ᴏғғ" if mode == "on" else "on"
            buttons = [
                [InlineKeyboardButton(f"ʀᴇǫ ᴍᴏᴅᴇ {'OFF' if mode == 'on' else 'ON'}", callback_data=f"rfs_toggle_{cid}_{new_mode}", style="danger" if mode == 'on' else "success")],
                [InlineKeyboardButton("‹ ʙᴀᴄᴋ", callback_data="fsub_back", style="primary")]
            ]
            await query.message.edit_text(
                f"Channel: {chat.title}\nCurrent Force-Sub Mode: {status}",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except Exception:
            await query.answer("Failed to fetch channel info", show_alert=True)

    elif data.startswith("rfs_toggle_"):
        cid, action = data.split("_")[2:]
        cid = int(cid)
        mode = "on" if action == "on" else "off"

        await db.set_channel_mode(cid, mode)
        await query.answer(f"Force-Sub set to {'ON' if mode == 'on' else 'OFF'}")

        chat = await client.get_chat(cid)
        status = "🟢 ON" if mode == "on" else "🔴 OFF"
        new_mode = "off" if mode == "on" else "on"
        buttons = [
            [InlineKeyboardButton(f"ʀᴇǫ ᴍᴏᴅᴇ {'OFF' if mode == 'on' else 'ON'}", callback_data=f"rfs_toggle_{cid}_{new_mode}", style="danger" if mode == 'on' else "success")],
            [InlineKeyboardButton("‹ ʙᴀᴄᴋ", callback_data="fsub_back", style="primary")]
        ]
        await query.message.edit_text(
            f"Channel: {chat.title}\nCurrent Force-Sub Mode: {status}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data == "fsub_back":
        await query.answer()
        channels = await db.show_channels()
        buttons = []
        for cid in channels:
            try:
                chat = await client.get_chat(cid)
                mode = await db.get_channel_mode(cid)
                status = "🟢" if mode == "on" else "🔴"
                buttons.append([InlineKeyboardButton(f"{status} {chat.title}", callback_data=f"rfs_ch_{cid}", style="primary")])
            except:
                continue

        await query.message.edit_text(
            "sᴇʟᴇᴄᴛ ᴀ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴛᴏɢɢʟᴇ ɪᴛs ғᴏʀᴄᴇ-sᴜʙ ᴍᴏᴅᴇ:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )


# ==================== Panel Callback Handlers ====================
from plugins.anizoneflix import check_admin_or_owner, is_admin, is_owner
from plugins.panel import build_panel_menu, active_clones
import psutil

@Bot.on_callback_query(filters.regex(r"^panel_(?!verify_log$)"))
async def panel_callback_handler(client: Bot, query: CallbackQuery):
    user_id = query.from_user.id
    if not (await is_owner(user_id) or await is_admin(user_id)):
        return await query.answer("⛔ Unauthorized access!", show_alert=True)

    data = query.data

    if data == "panel_main":
        await query.answer()
        text = (
            "<b>✨ ᴀɴɪᴢᴏɴᴇғʟɪx — Control Panel</b>\n"
            "<i>Welcome to the centralized management dashboard. Select a module below to configure your bot:</i>"
        )
        return await query.message.edit_text(text, reply_markup=build_panel_menu())

    elif data == "panel_core":
        await query.answer()
        base_url = await db.get_config_val("BASE_URL", "https://your-render-service.onrender.com")
        owner_id = OWNER_ID
        text = (
            "<b>⚙️ Core Configuration</b>\n\n"
            f"<b>• Base URL:</b> <code>{base_url}</code>\n"
            f"<b>• Owner ID:</b> <code>{owner_id}</code>\n"
            f"<b>• API ID:</b> <code>{client.api_id}</code>\n\n"
            "<i>Use dynamic options or environment settings to adjust core variables.</i>"
        )
        btn = [
            [InlineKeyboardButton("🌐 Set / Change Base URL", callback_data="panel_set_base_url", style="primary")],
            [InlineKeyboardButton("‹ Back", callback_data="panel_main", style="primary")]
        ]
        return await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))

    elif data == "panel_admins":
        await query.answer()
        admins = await db.get_all_admins()
        admin_list = "\n".join([f"• <code>{a}</code>" for a in admins]) if admins else "<i>No extra admins added.</i>"
        text = (
            "<b>👥 Admin Manager</b>\n\n"
            f"<b>Current Admins:</b>\n{admin_list}\n\n"
            "<i>Use /add_admin <id> or /deladmin <id> to add/remove admins.</i>"
        )
        btn = [[InlineKeyboardButton("‹ Back", callback_data="panel_main", style="primary")]]
        return await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))

    elif data == "panel_db_channels":
        await query.answer()
        db_ch = await db.get_db_channels()
        ch_list = "\n".join([f"• <code>{c}</code>" for c in db_ch]) if db_ch else "<i>No secondary DB channels added.</i>"
        text = (
            "<b>🗄️ DB Channel Manager</b>\n\n"
            f"<b>Primary Channel ID:</b> <code>{(getattr(client, 'db_channel', None) and client.db_channel.id) or CHANNEL_ID}</code>\n"
            f"<b>Secondary Channels:</b>\n{ch_list}"
        )
        btn = [[InlineKeyboardButton("‹ Back", callback_data="panel_main", style="primary")]]
        return await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))

    elif data == "panel_fsub":
        await query.answer()
        fsub_ch = await db.show_channels()
        ch_list = "\n".join([f"• <code>{c}</code>" for c in fsub_ch]) if fsub_ch else "<i>No Force Sub channels added.</i>"
        text = (
            "<b>📢 Force Subscription Manager</b>\n\n"
            f"<b>Configured Channels/Groups:</b>\n{ch_list}\n\n"
            "<i>Use /addchnl <id> or /delchnl <id> to manage.</i>"
        )
        btn = [[InlineKeyboardButton("‹ Back", callback_data="panel_main", style="primary")]]
        return await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))

    elif data == "panel_verify":
        await query.answer()
        status = await db.get_config_val("VERIFY_ENABLED", False)
        status_str = "🟢 ENABLED" if status else "🔴 DISABLED"
        toggle_action = "panel_toggle_verify"
        from helper_func import get_readable_time
        expire_sec = await db.get_config_val("VERIFY_EXPIRE_SECONDS", 86400)
        session_sec = await db.get_config_val("SESSION_EXPIRE_SECONDS", 3000)
        exp_time_str = get_readable_time(int(expire_sec))
        sess_time_str = get_readable_time(int(session_sec)) if session_sec > 0 else "Permanent (0s)"

        btn = [
            [InlineKeyboardButton(f"Toggle Status ({'DISABLE' if status else 'ENABLE'})", callback_data=toggle_action, style="danger" if status else "success")],
            [InlineKeyboardButton("🌐 Set / Change Base URL", callback_data="panel_set_base_url", style="primary")],
            [InlineKeyboardButton("⏱️ Set Verified Access Duration", callback_data="panel_set_verify_expire", style="primary")],
            [InlineKeyboardButton("⌛ Set Session Link Expiry", callback_data="panel_set_session_expire", style="primary")],
            [InlineKeyboardButton("‹ Back", callback_data="panel_main", style="primary")]
        ]
        text = (
            "<b>🛡️ Verification System</b>\n\n"
            f"<b>• Status:</b> {status_str}\n"
            f"<b>• Verified Access Duration:</b> <code>{exp_time_str}</code> ({expire_sec}s)\n"
            f"<b>• Session Link Expiry:</b> <code>{sess_time_str}</code> ({session_sec}s)\n"
            f"<b>• Base URL:</b> <code>{await db.get_config_val('BASE_URL', 'https://your-render-service.onrender.com')}</code>\n\n"
            "<i>Redirects unverified users through shorteners before granting file access.</i>"
        )
        return await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))

    elif data == "panel_toggle_verify":
        curr = await db.get_config_val("VERIFY_ENABLED", False)
        now_utc = datetime.now(timezone.utc)
        if curr:
            # Disabling verification: record pause start time
            await db.update_config("VERIFY_PAUSE_START_TS", now_utc.isoformat())
            await db.update_config("VERIFY_ENABLED", False)
            await query.answer("Verification DISABLED!")
        else:
            # Enabling verification: apply compensation for pause duration
            pause_start = await db.get_config_val("VERIFY_PAUSE_START_TS", None)
            if pause_start:
                try:
                    start_dt = datetime.fromisoformat(pause_start)
                    pause_duration = int((now_utc - start_dt).total_seconds())
                    if pause_duration > 0:
                        await db.apply_downtime_compensation(pause_duration)
                except Exception as e:
                    print(f"Error applying verification pause compensation: {e}")
                await db.update_config("VERIFY_PAUSE_START_TS", None)
            await db.update_config("VERIFY_ENABLED", True)
            await query.answer("Verification ENABLED!")
        return await panel_callback_handler(client, query)

    elif data == "panel_set_api_base_url":
        await query.answer()
        current_api_url = await db.get_config_val("API_BASE_URL", "")
        if not current_api_url:
            current_api_url = await db.get_config_val("BASE_URL", "")
        await query.message.edit_text(
            "<b>🌐 Set API Base URL</b>\n\n"
            f"<b>Current API Base URL:</b> <code>{current_api_url or 'Not set'}</code>\n\n"
            "Send the public HTTPS origin of this Verify Bot web service, for example "
            "<code>https://your-verify-service.onrender.com</code>.\n"
            "This URL is used by FileStore as the API origin; the API endpoints are "
            "<code>/api/request</code>, <code>/api/{user_id}</code>, and "
            "<code>/api/request-status/{user_id}</code>.\n\n"
            "Send <code>/cancel</code> to abort."
        )
        try:
            answer = await client.listen(query.message.chat.id, timeout=120)
            value = (answer.text or "").strip()
            if value.lower() == "/cancel":
                await answer.reply_text("<b>❌ API Base URL setup cancelled.</b>")
                return
            if not value.startswith(("https://", "http://")):
                value = "https://" + value
            from urllib.parse import urlsplit
            parsed = urlsplit(value)
            if parsed.scheme not in ("https", "http") or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
                return await answer.reply_text("<b>❌ Invalid URL.</b> Send a complete public URL such as <code>https://your-verify-service.onrender.com</code> without a query string or fragment.")
            value = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}".rstrip("/")
            saved_api = await db.update_config("API_BASE_URL", value)
            # Keep the canonical web base URL aligned so verification callbacks and API clients use the same origin.
            saved_web = await db.update_config("BASE_URL", value)
            confirmed = await db.get_config_val("API_BASE_URL", None)
            if not saved_api or not saved_web or confirmed != value:
                return await answer.reply_text("<b>❌ Could not confirm the API Base URL was saved.</b> Check MongoDB connectivity and retry.")
            await answer.reply_text(
                "<b>✅ API Base URL saved.</b>\n\n"
                f"<b>API Base URL:</b> <code>{value}</code>\n"
                f"<b>FileStore API value:</b> <code>{value}</code>\n\n"
                "In FileStore, run <code>/verifyapi</code> and enter this URL, the same client API key if configured, and your Verify Bot username.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛡️ Open Panel", callback_data="panel_main", style="primary")]])
            )
        except Exception as exc:
            await query.message.reply_text(f"<b>❌ API Base URL setup failed:</b> <code>{str(exc)[:400]}</code>")

    elif data == "panel_set_base_url":
        await query.answer()
        curr_url = await db.get_config_val("BASE_URL", "https://your-render-service.onrender.com")
        await query.message.edit_text(
            "<b>🌐 Set / Change Base URL</b>\n\n"
            f"<b>Current Base URL:</b> <code>{curr_url}</code>\n\n"
            "<i>Please send the new Base URL now (e.g. <code>https://mybot.onrender.com</code>).</i>\n\n"
            "<i>(Send /cancel to abort)</i>"
        )
        try:
            ask_url = await client.listen(query.message.chat.id, timeout=60)
            if not ask_url.text or ask_url.text.strip() == "/cancel":
                await ask_url.reply_text("<b>❌ Operation cancelled.</b>")
                query.data = "panel_verify"
                return await panel_callback_handler(client, query)

            new_url = ask_url.text.strip()
            if not (new_url.startswith("http://") or new_url.startswith("https://")):
                new_url = "https://" + new_url

            from urllib.parse import urlsplit
            new_url = new_url.rstrip("/")
            parsed = urlsplit(new_url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                await ask_url.reply_text("<b>❌ Invalid URL.</b> Please send a valid HTTPS URL.")
                return
            saved = await db.update_config("BASE_URL", new_url)
            confirmed = await db.get_config_val("BASE_URL", None)
            if not saved or confirmed != new_url:
                await ask_url.reply_text("<b>❌ MongoDB did not confirm the new URL. Check database connectivity and retry.</b>")
                return
            btn = [[InlineKeyboardButton("🛡️ View Verification Panel", callback_data="panel_verify", style="primary")]]
            await ask_url.reply_text(
                f"<b>✅ Base URL Updated and Verified</b>\n\n<blockquote><b>New Base URL:</b> <code>{new_url}</code></blockquote>",
                reply_markup=InlineKeyboardMarkup(btn)
            )
        except Exception as e:
            await query.message.reply_text(f"<b>❌ Error updating Base URL:</b> <code>{e}</code>")

    elif data == "panel_set_session_expire":
        await query.answer()
        await query.message.edit_text(
            "<b>⌛ Set Session Link Expiry Time</b>\n\n"
            "<i>Please send the session link expiration duration in seconds, minutes, or hours (0 for permanent).</i>\n"
            "<i>Examples:</i> <code>1h</code>, <code>30m</code>, <code>3000</code>, or <code>0</code>\n\n"
            "<i>(Send /cancel to abort)</i>"
        )
        try:
            ask_exp = await client.listen(query.message.chat.id, timeout=60)
            if not ask_exp.text or ask_exp.text.strip() == "/cancel":
                await ask_exp.reply_text("<b>❌ Operation cancelled.</b>")
                query.data = "panel_verify"
                return await panel_callback_handler(client, query)

            raw_val = ask_exp.text.strip().lower()
            seconds = 3000
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
            btn = [[InlineKeyboardButton("🛡️ View Verification Panel", callback_data="panel_verify", style="primary")]]
            disp_time = get_readable_time(seconds) if seconds > 0 else "Permanent (0s)"
            await ask_exp.reply_text(
                f"<b>✅ Session Link Expiry Updated!</b>\n\n"
                f"<b>Duration:</b> <code>{disp_time}</code> ({seconds} seconds)",
                reply_markup=InlineKeyboardMarkup(btn)
            )
        except Exception as e:
            await query.message.reply_text(f"<b>❌ Invalid duration or error:</b> <code>{e}</code>")

    elif data == "panel_set_verify_expire":
        await query.answer()
        await query.message.edit_text(
            "<b>⏱️ Set Verification Access Duration</b>\n\n"
            "<i>Please send the verification access expiration duration in seconds, minutes, or hours.</i>\n"
            "<i>Examples:</i> <code>24h</code>, <code>12h</code>, <code>30m</code>, or <code>86400</code>\n\n"
            "<i>(Send /cancel to abort)</i>"
        )
        try:
            ask_exp = await client.listen(query.message.chat.id, timeout=60)
            if not ask_exp.text or ask_exp.text.strip() == "/cancel":
                await ask_exp.reply_text("<b>❌ Operation cancelled.</b>")
                query.data = "panel_verify"
                return await panel_callback_handler(client, query)

            raw_val = ask_exp.text.strip().lower()
            seconds = 86400
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
            btn = [[InlineKeyboardButton("🛡️ View Verification Panel", callback_data="panel_verify", style="primary")]]
            await ask_exp.reply_text(
                f"<b>✅ Verification Expire Time Updated!</b>\n\n"
                f"<b>Duration:</b> <code>{get_readable_time(seconds)}</code> ({seconds} seconds)",
                reply_markup=InlineKeyboardMarkup(btn)
            )
        except Exception as e:
            await query.message.reply_text(f"<b>❌ Invalid duration or error:</b> <code>{e}</code>")

    elif data == "panel_referrer":
        await query.answer()
        shorteners = await db.get_shorteners() or []
        buttons = []
        if shorteners:
            text = "<b>🧭 Per-Shortener Referer Protection</b>\n\nEach configured shortener has its own independent switch. 🟢 ON requires the browser callback Referer host to match that shortener's configured domain; 🔴 OFF skips only the Referer check for that shortener. The remaining token, browser-session, tab, and expiry checks still apply. New shorteners default to OFF. Some providers/browsers omit Referer, so test before enabling.\n\n"
            for item in shorteners:
                enabled = bool(item.get('referer_enabled', False))
                text += f"• <b>{item.get('domain', 'Unknown')}</b>: {'🟢 ON' if enabled else '🔴 OFF'}\n"
                buttons.append([InlineKeyboardButton(f"{'🟢 Disable' if enabled else '🔴 Enable'} — {item.get('domain', 'Shortener')}", callback_data=f"panel_toggle_ref_{item['_id']}", style="success" if not enabled else "danger")])
        else:
            text = "<b>🧭 Shortener Referrer Protection</b>\n\n<i>No shorteners configured yet. Add one with /addshortener.</i>"
        buttons.append([InlineKeyboardButton("‹ Back", callback_data="panel_main", style="primary")])
        return await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    elif data == "panel_shortener":
        await query.answer()
        shorteners = await db.get_shorteners()
        buttons = []
        if shorteners:
            text = "<b>🔗 Shortener Manager</b>\n\n<b>Active Shorteners:</b>\n"
            for s in shorteners:
                is_enabled = bool(s.get('enabled', True))
                text += f"• <b>{s['domain']}</b> | {'🟢 Enabled' if is_enabled else '🔴 Disabled'} | Key: <code>{s['api_key'][:4]}***</code>\n"
                buttons.append([InlineKeyboardButton(f"{'🔴 Turn OFF' if is_enabled else '🟢 Turn ON'} — {s['domain']}", callback_data=f"panel_toggle_short_{s['_id']}", style="danger" if is_enabled else "success")])
                ref_on = bool(s.get('referer_enabled', False))
                buttons.append([InlineKeyboardButton(f"🧭 Referrer: {'ON' if ref_on else 'OFF'} — {s['domain']}", callback_data=f"panel_toggle_ref_{s['_id']}", style="success" if ref_on else "primary")])
                buttons.append([InlineKeyboardButton(f"🗑️ Delete {s['domain']}", callback_data=f"panel_del_short_{s['_id']}", style="danger")])
        else:
            text = "<b>🔗 Shortener Manager</b>\n\n<i>No shorteners configured. Use /addshortener to add one.</i>"
        buttons.append([InlineKeyboardButton("‹ Back", callback_data="panel_main", style="primary")])
        return await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    elif data == "panel_images":
        await query.answer()
        images = await db.get_admin_images()
        text = "<b>🖼️ Admin Configured Images:</b>\n\n"
        if images:
            for idx, img in enumerate(images, start=1):
                text += f"{idx}. <code>{img}</code>\n"
        else:
            text += "<i>No custom image URLs configured. Currently using default images pool.</i>\n"

        buttons = [
            [InlineKeyboardButton("➕ Add Image URLs", callback_data="panel_add_images", style="primary")],
        ]
        if images:
            buttons.append([InlineKeyboardButton("🧹 Clear All Images", callback_data="panel_clear_images", style="danger")])
            del_row = []
            for idx, img in enumerate(images[:5], start=1):
                del_row.append(InlineKeyboardButton(f"🗑️ {idx}", callback_data=f"panel_del_img_{idx - 1}", style="danger"))
            buttons.append(del_row)

        buttons.append([InlineKeyboardButton("‹ Back", callback_data="panel_main", style="primary")])
        return await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)

    elif data == "panel_add_images":
        await query.answer()
        await query.message.edit_text(
            "<b>🖼️ Add Admin Image URLs</b>\n\n"
            "<i>Please send single or multiple bulk image URLs in your next message.</i>\n"
            "• Separate multiple URLs using line breaks, commas, or spaces.\n"
            "• Example:\n"
            "<code>https://example.com/image1.jpg\nhttps://example.com/image2.jpg</code>\n\n"
            "<i>(Send /cancel to abort)</i>"
        )
        try:
            ask_msg = await client.listen(query.message.chat.id, timeout=60)
            if not ask_msg.text or ask_msg.text.strip() == "/cancel":
                await ask_msg.reply_text("<b>❌ Operation cancelled.</b>")
                query.data = "panel_images"
                return await panel_callback_handler(client, query)

            raw_input = ask_msg.text.strip()
            urls = [u.strip() for u in re.split(r"[\n,\s]+", raw_input) if u.strip().startswith(("http://", "https://"))]
            if urls:
                await db.add_admin_images(urls)
                btn = [[InlineKeyboardButton("🖼️ View Images Panel", callback_data="panel_images", style="primary")]]
                await ask_msg.reply_text(f"<b>✅ Successfully saved {len(urls)} image URL(s)!</b>", reply_markup=InlineKeyboardMarkup(btn))
            else:
                await ask_msg.reply_text("<b>❌ No valid HTTP/HTTPS image URLs found in message.</b>")
        except Exception as e:
            await query.message.reply_text(f"<b>❌ Error or timeout:</b> <code>{e}</code>")

    elif data == "panel_clear_images":
        await db.clear_admin_images()
        await query.answer("Cleared all custom image URLs!", show_alert=True)
        query.data = "panel_images"
        return await panel_callback_handler(client, query)

    elif data.startswith("panel_del_img_"):
        try:
            idx = int(data.replace("panel_del_img_", ""))
            images = await db.get_admin_images()
            if 0 <= idx < len(images):
                target_url = images[idx]
                await db.delete_admin_image(target_url)
                await query.answer("Image URL removed!", show_alert=True)
            else:
                await query.answer("Invalid image selection.", show_alert=True)
        except Exception:
            await query.answer("Failed to remove image.", show_alert=True)
        query.data = "panel_images"
        return await panel_callback_handler(client, query)

    elif data == "panel_clones":
        await query.answer()
        clones = await db.get_all_clones()
        c_list = "\n".join([f"• @{c['bot_username']} | DB: <code>{c['db_channel_id']}</code>" for c in clones]) if clones else "<i>No clone bots configured.</i>"
        text = (
            "<b>🤖 Clone Bot Manager</b>\n\n"
            f"<b>Active Clones Count:</b> <code>{len(active_clones)}</code>\n"
            f"<b>Configured Clones:</b>\n{c_list}\n\n"
            "<i>Add clone bots with custom DB channel configuration. Clone bots inherit all AniZoneFlix features.</i>"
        )
        btn = [[InlineKeyboardButton("‹ Back", callback_data="panel_main", style="primary")]]
        return await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))

    elif data == "panel_custom_btn":
        await query.answer()
        btn_name = await db.get_config_val("CUSTOM_BUTTON_NAME", None)
        btn_url = await db.get_config_val("CUSTOM_BUTTON_URL", None)

        if btn_name and btn_url:
            status_text = f"<b>Current Button:</b> [{btn_name}]({btn_url})\n<b>Name:</b> <code>{btn_name}</code>\n<b>URL:</b> <code>{btn_url}</code>"
            btn = [
                [InlineKeyboardButton("➕ Update / Replace Button", callback_data="panel_add_custom_btn", style="primary")],
                [InlineKeyboardButton("🗑️ Remove Custom Button", callback_data="panel_del_custom_btn", style="danger")],
                [InlineKeyboardButton("‹ Back", callback_data="panel_main", style="primary")]
            ]
        else:
            status_text = "<b>Current Button:</b> <i>None configured</i>"
            btn = [
                [InlineKeyboardButton("➕ Add Custom Button", callback_data="panel_add_custom_btn", style="primary")],
                [InlineKeyboardButton("‹ Back", callback_data="panel_main", style="primary")]
            ]

        text = (
            "<b>🔘 Custom Button Configuration</b>\n\n"
            f"{status_text}\n\n"
            "<i>The custom button will be automatically attached to every delivered file, video, media, text, sticker, or any other content.</i>"
        )
        try:
            return await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
        except Exception:
            pass

    elif data == "panel_add_custom_btn":
        await query.answer()
        await query.message.edit_text("<b>🔘 Add Custom Button</b>\n\n<i>Please send the button text/name now (or send /cancel to abort):</i>")
        try:
            ask_name = await client.listen(query.message.chat.id, timeout=60)
            if not ask_name.text or ask_name.text.strip() == "/cancel":
                await ask_name.reply_text("<b>❌ Operation cancelled.</b>")
                query.data = "panel_custom_btn"
                return await panel_callback_handler(client, query)

            button_name = ask_name.text.strip()
            await ask_name.reply_text(f"<b>Button Name set to:</b> <code>{button_name}</code>\n\n<i>Now send the target URL/link for this button (or send /cancel to abort):</i>")

            ask_url = await client.listen(query.message.chat.id, timeout=60)
            if not ask_url.text or ask_url.text.strip() == "/cancel":
                await ask_url.reply_text("<b>❌ Operation cancelled.</b>")
                query.data = "panel_custom_btn"
                return await panel_callback_handler(client, query)

            button_url = ask_url.text.strip()
            if not (button_url.startswith("http://") or button_url.startswith("https://") or button_url.startswith("t.me/")):
                button_url = "https://" + button_url

            await db.update_config("CUSTOM_BUTTON_NAME", button_name)
            await db.update_config("CUSTOM_BUTTON_URL", button_url)

            btn = [[InlineKeyboardButton("🔘 View Custom Button Panel", callback_data="panel_custom_btn", style="primary")]]
            await ask_url.reply_text(f"<b>✅ Custom Button Successfully Saved!</b>\n\n<b>Name:</b> {button_name}\n<b>URL:</b> {button_url}", reply_markup=InlineKeyboardMarkup(btn))
        except Exception as e:
            await query.message.reply_text(f"<b>❌ Error or timeout:</b> <code>{e}</code>")

    elif data == "panel_del_custom_btn":
        await db.update_config("CUSTOM_BUTTON_NAME", None)
        await db.update_config("CUSTOM_BUTTON_URL", None)
        await query.answer("Custom button removed!", show_alert=True)
        query.data = "panel_custom_btn"
        return await panel_callback_handler(client, query)

    elif data == "panel_stats":
        await query.answer()
        total_users = len(await db.full_userbase())
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        text = (
            "<b>📊 AniZoneFlix Statistics</b>\n\n"
            f"<b>• Total Users:</b> <code>{total_users}</code>\n"
            f"<b>• CPU Usage:</b> <code>{cpu}%</code>\n"
            f"<b>• RAM Usage:</b> <code>{ram}%</code>\n"
            f"<b>• Active Clones:</b> <code>{len(active_clones)}</code>"
        )
        btn = [[InlineKeyboardButton("‹ Back", callback_data="panel_main", style="primary")]]
        return await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))

    elif data == "panel_sync":
        # Do not recursively dispatch the same callback: that re-answers an expired
        # callback query and causes QUERY_ID_INVALID / unbounded recursion.
        await query.answer("System configuration synced!", show_alert=True)
        return await query.message.edit_text(
            "<b>✨ ᴀɴɪᴢᴏɴᴇғʟɪx — Control Panel</b>\n"
            "<i>Welcome to the centralized management dashboard. Select a module below to configure your bot:</i>",
            reply_markup=build_panel_menu(),
        )

    elif data.startswith("panel_del_admin_"):
        aid = int(data.split("_")[3])
        await db.del_admin(aid)
        await query.answer("Admin removed!", show_alert=True)
        query.data = "panel_admins"
        return await panel_callback_handler(client, query)

    elif data.startswith("panel_del_dbch_"):
        cid = int(data.split("_")[3])
        await db.remove_db_channel(cid)
        await query.answer("DB Channel removed!", show_alert=True)
        query.data = "panel_db_channels"
        return await panel_callback_handler(client, query)

    elif data.startswith("panel_del_fsub_"):
        cid = int(data.split("_")[3])
        await db.rem_channel(cid)
        await query.answer("Force Sub channel removed!", show_alert=True)
        query.data = "panel_fsub"
        return await panel_callback_handler(client, query)

    elif data.startswith("panel_toggle_short_"):
        sid = data[len("panel_toggle_short_"):]
        shorteners = await db.get_shorteners() or []
        selected = next((item for item in shorteners if str(item.get('_id')) == sid), None)
        if not selected:
            await query.answer("Shortener not found", show_alert=True)
            return
        new_value = not bool(selected.get('enabled', True))
        await db.update_shortener(sid, {'enabled': new_value})
        await query.answer(f"{selected.get('domain', 'Shortener')} {'enabled' if new_value else 'disabled'}", show_alert=True)
        query.data = "panel_shortener"
        return await panel_callback_handler(client, query)

    elif data.startswith("panel_toggle_ref_"):
        sid = data[len("panel_toggle_ref_"):]
        shorteners = await db.get_shorteners() or []
        selected = next((item for item in shorteners if str(item.get('_id')) == sid), None)
        if not selected:
            await query.answer("Shortener not found", show_alert=True)
            return
        new_value = not bool(selected.get('referer_enabled', False))
        await db.update_shortener(sid, {'referer_enabled': new_value})
        await query.answer(f"Referrer check {'enabled' if new_value else 'disabled'}", show_alert=True)
        query.data = "panel_referrer"
        return await panel_callback_handler(client, query)

    elif data.startswith("panel_del_short_"):
        sid = data.split("_")[3]
        await db.delete_shortener(sid)
        await query.answer("Shortener deleted!", show_alert=True)
        query.data = "panel_shortener"
        return await panel_callback_handler(client, query)

    elif data.startswith("panel_del_clone_"):
        un = data.split("_")[3]
        await db.delete_clone(un)
        if un in active_clones:
            try: await active_clones[un].stop()
            except: pass
            active_clones.pop(un, None)
        await query.answer("Clone bot removed!", show_alert=True)
        query.data = "panel_clones"
        return await panel_callback_handler(client, query)
