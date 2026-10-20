import re
from pyrogram import Client, filters
from pyrogram.types import Message
from helper_func import admin
try:
    from plugins.anizoneflix import check_admin_or_owner
except ImportError:
    try:
        from anizoneflix import check_admin_or_owner
    except ImportError:
        async def check_admin_or_owner(message):
            from database.database import db
            from config import OWNER_ID
            uid = message.from_user.id
            return uid == OWNER_ID or await db.admin_exist(uid)

# Temporary in-memory session stores
# HYPERLINK_SESSIONS: user_id -> list of {"label": str, "url": str}
HYPERLINK_SESSIONS = {}
# HYPERLINK_FILTER_SESSIONS: user_id -> list of {"label": str, "url": str}
HYPERLINK_FILTER_SESSIONS = {}

def is_in_hyperlink_session(_, __, message: Message):
    if not message.from_user:
        return False
    return message.from_user.id in HYPERLINK_SESSIONS

def is_in_hyperlink_filter_session(_, __, message: Message):
    if not message.from_user:
        return False
    return message.from_user.id in HYPERLINK_FILTER_SESSIONS

hyperlink_session_filter = filters.create(is_in_hyperlink_session)
hyperlink_filter_session_filter = filters.create(is_in_hyperlink_filter_session)

@Client.on_message(filters.private & filters.command("hyperlink"))
async def hyperlink_cmd(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return
    user_id = message.from_user.id
    HYPERLINK_SESSIONS[user_id] = []
    HYPERLINK_FILTER_SESSIONS.pop(user_id, None)

    await message.reply_text(
        "<b>🔗 Hyperlink Collector</b>\n\n"
        "<b><blockquote>Send or forward any Telegram messages, posts, captions, or media containing hyperlinks.\n\n"
        "• You can send unlimited messages.\n"
        "• When finished, send /done.\n"
        "• Send /cancel to abort.</blockquote></b>"
    )

@Client.on_message(filters.private & hyperlink_session_filter & ~filters.command(["hyperlink"]))
async def collect_hyperlinks_handler(client: Client, message: Message):
    user_id = message.from_user.id
    raw_text = message.text or message.caption or ""
    text_stripped = raw_text.strip().lower()

    if text_stripped == "/done":
        collected_items = HYPERLINK_SESSIONS.pop(user_id, [])
        if not collected_items:
            return await message.reply_text("<b><blockquote>❌ No hyperlinks or URLs were found in the submitted messages.</blockquote></b>")

        # De-duplicate while preserving order
        unique_items = []
        seen_urls = set()
        for item in collected_items:
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                unique_items.append(item)

        if not unique_items:
            return await message.reply_text("<b><blockquote>❌ No hyperlinks or URLs were found in the submitted messages.</blockquote></b>")

        HYPERLINK_FILTER_SESSIONS[user_id] = unique_items
        return await message.reply_text(
            f"<b>🔗 Hyperlink Extraction Filter</b>\n\n"
            f"<b><blockquote>Found {len(unique_items)} hyperlink(s).\n\n"
            f"Which text hyperlinks would you like to extract?\n"
            f"• Enter single or multiple hyperlink labels/texts (separated by commas).\n"
            f"• Send <code>/skip</code> to extract ALL links.\n"
            f"• Send <code>/cancel</code> to abort.</blockquote></b>"
        )

    if text_stripped == "/cancel":
        HYPERLINK_SESSIONS.pop(user_id, None)
        return await message.reply_text("<b><blockquote>Hyperlink extraction has been cancelled.</blockquote></b>")

    # Extract hyperlinks and raw URLs from the message
    entities = message.entities or message.caption_entities
    if entities:
        for entity in entities:
            if entity.type.name == "TEXT_LINK":
                if entity.url:
                    label = raw_text[entity.offset : entity.offset + entity.length].strip() or entity.url
                    item = {"label": label, "url": entity.url}
                    if item not in HYPERLINK_SESSIONS[user_id]:
                        HYPERLINK_SESSIONS[user_id].append(item)
            elif entity.type.name == "URL":
                url_val = raw_text[entity.offset : entity.offset + entity.length].strip()
                if url_val:
                    item = {"label": url_val, "url": url_val}
                    if item not in HYPERLINK_SESSIONS[user_id]:
                        HYPERLINK_SESSIONS[user_id].append(item)

    # Regex fallback for plain URLs in text
    regex_pattern = r"(https?://[^\s<>\"'()]+)"
    found_regex = re.findall(regex_pattern, raw_text)
    if found_regex:
        for url in found_regex:
            cleaned = url.rstrip('.,;!?)]} ')
            item = {"label": cleaned, "url": cleaned}
            if item not in HYPERLINK_SESSIONS[user_id]:
                HYPERLINK_SESSIONS[user_id].append(item)

@Client.on_message(filters.private & hyperlink_filter_session_filter & ~filters.command(["hyperlink"]))
async def filter_hyperlinks_handler(client: Client, message: Message):
    user_id = message.from_user.id
    raw_text = (message.text or message.caption or "").strip()
    text_low = raw_text.lower()

    items = HYPERLINK_FILTER_SESSIONS.get(user_id, [])

    if text_low == "/cancel":
        HYPERLINK_FILTER_SESSIONS.pop(user_id, None)
        return await message.reply_text("<b><blockquote>Hyperlink extraction has been cancelled.</blockquote></b>")

    final_urls = []

    if text_low == "/skip":
        HYPERLINK_FILTER_SESSIONS.pop(user_id, None)
        final_urls = [item["url"] for item in items]
    else:
        # Comma-separated labels/texts
        queries = [q.strip().lower() for q in raw_text.split(",") if q.strip()]
        matched_items = []
        for item in items:
            lbl = item["label"].lower()
            url = item["url"].lower()
            if any(q in lbl or q in url for q in queries):
                if item["url"] not in final_urls:
                    final_urls.append(item["url"])

        if not final_urls:
            return await message.reply_text(
                "<b><blockquote>❌ No links matched your specified text filter(s).\n\n"
                "Please enter valid labels (separated by commas), send <code>/skip</code> to send all links, or <code>/cancel</code> to abort.</blockquote></b>"
            )
        HYPERLINK_FILTER_SESSIONS.pop(user_id, None)

    output_text = "\n".join(final_urls)
    if len(output_text) > 4096:
        chunks = [output_text[i:i+4096] for i in range(0, len(output_text), 4096)]
        for chunk in chunks:
            await message.reply_text(chunk, disable_web_page_preview=True)
    else:
        await message.reply_text(output_text, disable_web_page_preview=True)
