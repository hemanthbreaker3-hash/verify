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
#                  Join Updates Channel: https://telegram.me/anizoneflix
#=====================================================================================##

import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from bot import Bot
from helper_func import encode, get_message_id, get_bot_username, get_messages
from plugins.anizoneflix import check_admin_or_owner

def extract_file_info(msg):
    if not msg:
        return "N/A", "N/A"
    media = (
        getattr(msg, "document", None) or
        getattr(msg, "video", None) or
        getattr(msg, "audio", None) or
        getattr(msg, "animation", None)
    )
    filename = "N/A"
    if media and getattr(media, "file_name", None) and isinstance(getattr(media, "file_name"), str):
        filename = media.file_name
    elif media and getattr(media, "file_name", None) and not str(getattr(media, "file_name")).startswith("<MagicMock"):
        filename = str(media.file_name)
    elif getattr(msg, "photo", None) and not str(getattr(msg, "photo")).startswith("<MagicMock"):
        filename = "Photo"

    caption = msg.caption.html if (msg.caption and hasattr(msg.caption, "html")) else (msg.caption or "")
    if isinstance(caption, str):
        filecaption = caption.strip() if caption.strip() else "N/A"
    else:
        filecaption = "N/A"

    return filename, filecaption

@Bot.on_message(filters.private & filters.command('batch'))
async def batch(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return

    while True:
        try:
            first_message = await client.ask(
                text="Forward the First Message from DB Channel (with Quotes)..\n\nor Send the DB Channel Post Link",
                chat_id=message.from_user.id,
                filters=(filters.forwarded | (filters.text & ~filters.forwarded)),
                timeout=60
            )
        except asyncio.TimeoutError:
            return

        f_msg_id = await get_message_id(client, first_message)
        if f_msg_id:
            break
        await first_message.reply("❌ Error\n\nThis Forwarded Post is not from my DB Channel or the Link is invalid.", quote=True)

    while True:
        try:
            second_message = await client.ask(
                text="Forward the Last Message from DB Channel (with Quotes)..\nor Send the DB Channel Post link",
                chat_id=message.from_user.id,
                filters=(filters.forwarded | (filters.text & ~filters.forwarded)),
                timeout=60
            )
        except asyncio.TimeoutError:
            return

        s_msg_id = await get_message_id(client, second_message)
        if s_msg_id:
            break
        await second_message.reply("❌ Error\n\nThis Forwarded Post is not from my DB Channel or the Link is invalid.", quote=True)

    msgs = await get_messages(client, [f_msg_id, s_msg_id])
    f_msg = next((m for m in msgs if m and m.id == f_msg_id), None)
    s_msg = next((m for m in msgs if m and m.id == s_msg_id), None)

    first_filename, first_caption = extract_file_info(f_msg)
    last_filename, last_caption = extract_file_info(s_msg)

    string = f"get-{f_msg_id * abs(client.db_channel.id)}-{s_msg_id * abs(client.db_channel.id)}"
    base64_string = await encode(string)
    bot_user = await get_bot_username(client)
    link = f"https://telegram.me/{bot_user}?start={base64_string}"
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Share URL", url=f'https://telegram.me/share/url?url={link}', style="primary")]])

    output_text = (
        f"<b>First Filename:</b> {first_filename}\n"
        f"<b>First Caption:</b> {first_caption}\n"
        f"<b>Last Filename:</b> {last_filename}\n"
        f"<b>Last Caption:</b> {last_caption}\n\n"
        f"<b>Here is your link:</b>\n\n"
        f"<code>{link}</code>"
    )
    await second_message.reply_text(output_text, quote=True, reply_markup=reply_markup)


@Bot.on_message(filters.private & filters.command('genlink'))
async def link_generator(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return

    channel_message = None
    msg_id = 0

    if len(message.command) > 1 or (message.reply_to_message and (message.reply_to_message.text or message.reply_to_message.forward_from_chat)):
        target_msg = message.reply_to_message if message.reply_to_message else message
        msg_id = await get_message_id(client, target_msg)
        if msg_id:
            channel_message = target_msg

    if not msg_id:
        while True:
            try:
                channel_message = await client.ask(
                    text="Forward Message from the DB Channel (with Quotes)..\nor Send the DB Channel Post link",
                    chat_id=message.from_user.id,
                    filters=(filters.forwarded | (filters.text & ~filters.forwarded)),
                    timeout=60
                )
            except asyncio.TimeoutError:
                return

            msg_id = await get_message_id(client, channel_message)
            if msg_id:
                break
            await channel_message.reply("❌ Error\n\nThis Forwarded Post is not from my DB Channel or the Link is invalid.", quote=True)

    msgs = await get_messages(client, [msg_id])
    db_msg = msgs[0] if msgs else channel_message
    first_filename, first_caption = extract_file_info(db_msg or channel_message)
    last_filename, last_caption = first_filename, first_caption

    base64_string = await encode(f"get-{msg_id * abs(client.db_channel.id)}")
    bot_user = await get_bot_username(client)
    link = f"https://telegram.me/{bot_user}?start={base64_string}"
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Share URL", url=f'https://telegram.me/share/url?url={link}', style="primary")]])

    output_text = (
        f"<b>First Filename:</b> {first_filename}\n"
        f"<b>First Caption:</b> {first_caption}\n"
        f"<b>Last Filename:</b> {last_filename}\n"
        f"<b>Last Caption:</b> {last_caption}\n\n"
        f"<b>Here is your link:</b>\n\n"
        f"<code>{link}</code>"
    )
    reply_target = channel_message if channel_message else message
    await reply_target.reply_text(output_text, quote=True, reply_markup=reply_markup)


@Bot.on_message(filters.private & filters.command("custom_batch"))
async def custom_batch(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return

    collected = []
    STOP_KEYBOARD = ReplyKeyboardMarkup([["STOP"]], resize_keyboard=True)
    await message.reply("Send all messages you want to include in batch.\n\nPress STOP when you're done.", reply_markup=STOP_KEYBOARD)

    while True:
        try:
            user_msg = await client.ask(
                chat_id=message.chat.id,
                text="Waiting for files/messages...\nPress STOP to finish.",
                timeout=60
            )
        except asyncio.TimeoutError:
            break

        if user_msg.text and user_msg.text.strip().upper() == "STOP":
            break

        try:
            sent = await user_msg.copy(client.db_channel.id, disable_notification=True)
            collected.append(sent.id)
        except Exception as e:
            await message.reply(f"❌ Failed to store a message:\n<code>{e}</code>")
            continue

    await message.reply("✅ Batch collection complete.", reply_markup=ReplyKeyboardRemove())

    if not collected:
        await message.reply("❌ No messages were added to batch.")
        return

    start_msg = (await get_messages(client, [collected[0]]))[0] if collected else None
    end_msg = (await get_messages(client, [collected[-1]]))[0] if collected else None
    first_filename, first_caption = extract_file_info(start_msg)
    last_filename, last_caption = extract_file_info(end_msg)

    start_id = collected[0] * abs(client.db_channel.id)
    end_id = collected[-1] * abs(client.db_channel.id)
    string = f"get-{start_id}-{end_id}"
    base64_string = await encode(string)
    bot_user = await get_bot_username(client)
    link = f"https://telegram.me/{bot_user}?start={base64_string}"

    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Share URL", url=f'https://telegram.me/share/url?url={link}', style="primary")]])
    output_text = (
        f"<b>First Filename:</b> {first_filename}\n"
        f"<b>First Caption:</b> {first_caption}\n"
        f"<b>Last Filename:</b> {last_filename}\n"
        f"<b>Last Caption:</b> {last_caption}\n\n"
        f"<b>Here is your link:</b>\n\n"
        f"<code>{link}</code>"
    )
    await message.reply(output_text, reply_markup=reply_markup)

# =====================================================================================##
#                         ✨ MADE BY ANIZONEFLIX ✨
#                  Join Updates Channel: https://telegram.me/anizoneflix
#====================================================================================##
