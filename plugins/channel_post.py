import asyncio
from pyrogram import filters, Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

from bot import Bot
from config import *
from helper_func import encode, admin, get_bot_username
from plugins.link_generator import extract_file_info

@Bot.on_message(filters.private & admin & (filters.document | filters.video | filters.audio | filters.photo | filters.animation | filters.voice))
async def channel_post(client: Client, message: Message):
    reply_text = await message.reply_text("⚡ <i>Generating link...</i>", quote=True)
    try:
        post_message = await message.copy(chat_id=client.db_channel.id, disable_notification=True)
    except FloodWait as e:
        await asyncio.sleep(e.x)
        post_message = await message.copy(chat_id=client.db_channel.id, disable_notification=True)
    except Exception as e:
        print(f"Error forwarding media to DB channel: {e}")
        await reply_text.edit_text(f"<b>❌ Error:</b> <code>{e}</code>")
        return

    first_filename, first_caption = extract_file_info(message)
    if first_filename == "N/A":
        first_filename, _ = extract_file_info(post_message)
    last_filename, last_caption = first_filename, first_caption

    converted_id = post_message.id * abs(client.db_channel.id)
    base64_string = await encode(f"get-{converted_id}")
    bot_user = await get_bot_username(client)
    link = f"https://telegram.me/{bot_user}?start={base64_string}"

    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Share URL", url=f'https://telegram.me/share/url?url={link}', style="primary")]])

    output_text = (
        f"<b><blockquote>📁 File Info:</b>\n"
        f"• <b>Filename:</b> {first_filename}\n"
        f"• <b>Caption:</b> {first_caption}</blockquote>\n\n"
        f"<b>🔗 Shareable Link:</b>\n"
        f"<code>{link}</code>"
    )

    await reply_text.edit(output_text, reply_markup=reply_markup, disable_web_page_preview=True)

    if not DISABLE_CHANNEL_BUTTON:
        try:
            asyncio.create_task(post_message.edit_reply_markup(reply_markup))
        except Exception:
            pass
