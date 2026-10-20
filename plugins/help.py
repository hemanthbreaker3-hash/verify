import asyncio
import math
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, CallbackQuery
from pyrogram.enums import ParseMode
from bot import Bot
from helper_func import get_next_image

# All bot commands organized alphabetically (A-Z) with usage and example
ALL_COMMANDS = [
    {
        "cmd": "/add_admin",
        "desc": "Add a new admin user to the bot.",
        "usage": "/add_admin <user_id>",
        "example": "<code>/add_admin 123456789</code>"
    },
    {
        "cmd": "/add_db_channel",
        "desc": "Add a secondary database channel for file storage.",
        "usage": "/add_db_channel <channel_id>",
        "example": "<code>/add_db_channel -1001234567890</code>"
    },
    {
        "cmd": "/addchnl",
        "desc": "Add a new force subscription channel.",
        "usage": "/addchnl <channel_id> [mode: on/off]",
        "example": "<code>/addchnl -1001234567890 on</code>"
    },
    {
        "cmd": "/addclone",
        "desc": "Add a new clone bot using bot token.",
        "usage": "/addclone <bot_token>",
        "example": "<code>/addclone 123456789:ABCdefGHIjklMNOpqrs</code>"
    },
    {
        "cmd": "/addpremium",
        "desc": "Add premium access to a user with custom duration.",
        "usage": "/addpremium <user_id> <time>",
        "example": "<code>/addpremium 123456789 1d</code> or <code>1m</code> / <code>1y</code>"
    },
    {
        "cmd": "/addshortener",
        "desc": "Add a shortener API domain and key.",
        "usage": "/addshortener <domain> <api_key>",
        "example": "<code>/addshortener short4cash.com secret_key_123</code>"
    },
    {
        "cmd": "/admins",
        "desc": "List all active admin user IDs.",
        "usage": "/admins",
        "example": "<code>/admins</code>"
    },
    {
        "cmd": "/advbatch",
        "desc": "Create an advanced batch file link from DB channel post range.",
        "usage": "/advbatch or /auto_batch",
        "example": "<code>/advbatch</code>"
    },
    {
        "cmd": "/backup",
        "desc": "Save or backup current database configurations.",
        "usage": "/backup or /save",
        "example": "<code>/backup</code>"
    },
    {
        "cmd": "/ban",
        "desc": "Ban a user from accessing the bot.",
        "usage": "/ban <user_id>",
        "example": "<code>/ban 123456789</code>"
    },
    {
        "cmd": "/banlist",
        "desc": "View the list of all banned users.",
        "usage": "/banlist",
        "example": "<code>/banlist</code>"
    },
    {
        "cmd": "/batch",
        "desc": "Create a batch share link for multiple channel posts.",
        "usage": "/batch",
        "example": "<code>/batch</code>"
    },
    {
        "cmd": "/broadcast",
        "desc": "Broadcast a text message to all bot users.",
        "usage": "/broadcast (as reply to a message)",
        "example": "<code>/broadcast</code>"
    },
    {
        "cmd": "/cancel_batch",
        "desc": "Cancel an active ongoing batch operation.",
        "usage": "/cancel_batch",
        "example": "<code>/cancel_batch</code>"
    },
    {
        "cmd": "/check_dlt_time",
        "desc": "Check the current auto-delete timer setting.",
        "usage": "/check_dlt_time",
        "example": "<code>/check_dlt_time</code>"
    },
    {
        "cmd": "/clones",
        "desc": "List all active clone bots.",
        "usage": "/clones",
        "example": "<code>/clones</code>"
    },
    {
        "cmd": "/commands",
        "desc": "List all available bot commands in short text format.",
        "usage": "/commands",
        "example": "<code>/commands</code>"
    },
    {
        "cmd": "/count",
        "desc": "Show total count of verified users.",
        "usage": "/count",
        "example": "<code>/count</code>"
    },
    {
        "cmd": "/custom_batch",
        "desc": "Save custom uploaded messages directly into a batch link.",
        "usage": "/custom_batch",
        "example": "<code>/custom_batch</code>"
    },
    {
        "cmd": "/dbroadcast",
        "desc": "Send a silent broadcast message to all users.",
        "usage": "/dbroadcast (as reply to a message)",
        "example": "<code>/dbroadcast</code>"
    },
    {
        "cmd": "/del_db_channel",
        "desc": "Remove a secondary database channel.",
        "usage": "/del_db_channel <channel_id>",
        "example": "<code>/del_db_channel -1001234567890</code>"
    },
    {
        "cmd": "/deladmin",
        "desc": "Remove an admin user.",
        "usage": "/deladmin <user_id>",
        "example": "<code>/deladmin 123456789</code>"
    },
    {
        "cmd": "/delchnl",
        "desc": "Remove a force subscription channel.",
        "usage": "/delchnl <channel_id>",
        "example": "<code>/delchnl -1001234567890</code>"
    },
    {
        "cmd": "/delclone",
        "desc": "Remove a clone bot.",
        "usage": "/delclone <bot_token>",
        "example": "<code>/delclone 123456789:ABCdefGHIjklMNOpqrs</code>"
    },
    {
        "cmd": "/delete",
        "desc": "Delete messages from the DB channel.",
        "usage": "/delete <message_id_or_link>",
        "example": "<code>/delete 1234</code>"
    },
    {
        "cmd": "/delpremium",
        "desc": "Remove premium status from a user.",
        "usage": "/delpremium <user_id>",
        "example": "<code>/delpremium 123456789</code>"
    },
    {
        "cmd": "/delshortener",
        "desc": "Remove a shortener configuration.",
        "usage": "/delshortener <domain>",
        "example": "<code>/delshortener short4cash.com</code>"
    },
    {
        "cmd": "/dlt_time",
        "desc": "Set the auto-delete duration for shared files (in seconds).",
        "usage": "/dlt_time <seconds>",
        "example": "<code>/dlt_time 600</code>"
    },
    {
        "cmd": "/fsub_mode",
        "desc": "Toggle force subscription request mode on or off.",
        "usage": "/fsub_mode <channel_id> <on/off>",
        "example": "<code>/fsub_mode -1001234567890 on</code>"
    },
    {
        "cmd": "/genlink",
        "desc": "Generate a single shareable file link.",
        "usage": "/genlink (or reply to a post)",
        "example": "<code>/genlink</code>"
    },
    {
        "cmd": "/help",
        "desc": "Show this interactive paginated help menu.",
        "usage": "/help",
        "example": "<code>/help</code>"
    },
    {
        "cmd": "/hyperlink",
        "desc": "Extract and collect hyperlinks from sent or forwarded posts.",
        "usage": "/hyperlink",
        "example": "<code>/hyperlink</code>"
    },
    {
        "cmd": "/list_db_channels",
        "desc": "List all configured secondary database channels.",
        "usage": "/list_db_channels",
        "example": "<code>/list_db_channels</code>"
    },
    {
        "cmd": "/listchnl",
        "desc": "List all active force subscription channels.",
        "usage": "/listchnl",
        "example": "<code>/listchnl</code>"
    },
    {
        "cmd": "/panel",
        "desc": "Open the AniZoneFlix master admin control panel.",
        "usage": "/panel",
        "example": "<code>/panel</code>"
    },
    {
        "cmd": "/pbroadcast",
        "desc": "Broadcast a photo message to all users.",
        "usage": "/pbroadcast (as reply to a photo)",
        "example": "<code>/pbroadcast</code>"
    },
    {
        "cmd": "/ping",
        "desc": "Check bot latency and response speed.",
        "usage": "/ping",
        "example": "<code>/ping</code>"
    },
    {
        "cmd": "/premium_users",
        "desc": "List all active premium users.",
        "usage": "/premium_users",
        "example": "<code>/premium_users</code>"
    },
    {
        "cmd": "/reset",
        "desc": "Instantly expire a user's verification status.",
        "usage": "/reset <user_id>",
        "example": "<code>/reset 123456789</code>"
    },
    {
        "cmd": "/retrieve_off",
        "desc": "Disable deletion alert message after files vanish.",
        "usage": "/retrieve_off",
        "example": "<code>/retrieve_off</code>"
    },
    {
        "cmd": "/retrieve_on",
        "desc": "Enable deletion alert message and 'Get File Again' button.",
        "usage": "/retrieve_on",
        "example": "<code>/retrieve_on</code>"
    },
    {
        "cmd": "/serialbatch",
        "desc": "Create a serial batch of indexed episode posts.",
        "usage": "/serialbatch",
        "example": "<code>/serialbatch</code>"
    },
    {
        "cmd": "/set_base_url",
        "desc": "Set the web verification base URL domain.",
        "usage": "/set_base_url <url>",
        "example": "<code>/set_base_url https://mybot.onrender.com</code>"
    },
    {
        "cmd": "/shorteners",
        "desc": "List all configured shortener domains and keys.",
        "usage": "/shorteners",
        "example": "<code>/shorteners</code>"
    },
    {
        "cmd": "/start",
        "desc": "Start or restart the bot / retrieve files.",
        "usage": "/start [payload]",
        "example": "<code>/start</code>"
    },
    {
        "cmd": "/stats",
        "desc": "Show system RAM, CPU, uptime, and user statistics.",
        "usage": "/stats",
        "example": "<code>/stats</code>"
    },
    {
        "cmd": "/unban",
        "desc": "Unban a user from the bot.",
        "usage": "/unban <user_id>",
        "example": "<code>/unban 123456789</code>"
    },
    {
        "cmd": "/universal_bypass",
        "desc": "Bypass shortener links or target redirect URLs directly in chat.",
        "usage": "domainurl=targeturl or paste shortener link",
        "example": "<code>short4cash.com/links?nicktrick=https://target.com</code>"
    },
    {
        "cmd": "/users",
        "desc": "Show total registered user count.",
        "usage": "/users",
        "example": "<code>/users</code>"
    },
    {
        "cmd": "/verify",
        "desc": "Check or extend your shortener verification access.",
        "usage": "/verify",
        "example": "<code>/verify</code>"
    },
    {
        "cmd": "/verify_off",
        "desc": "Disable shortener verification requirement globally.",
        "usage": "/verify_off",
        "example": "<code>/verify_off</code>"
    },
    {
        "cmd": "/verify_on",
        "desc": "Enable shortener verification requirement globally.",
        "usage": "/verify_on",
        "example": "<code>/verify_on</code>"
    }
]

# Ensure ALL_COMMANDS is sorted A-Z by command name
ALL_COMMANDS = sorted(ALL_COMMANDS, key=lambda c: c["cmd"].lower())

COMMANDS_PER_PAGE = 5
TOTAL_COMMANDS = len(ALL_COMMANDS)
TOTAL_PAGES = math.ceil(TOTAL_COMMANDS / COMMANDS_PER_PAGE)


def get_help_page_content(page_num: int) -> tuple:
    """
    Generate page text and inline keyboard markup for a given page number (1-indexed).
    """
    if page_num < 1:
        page_num = 1
    elif page_num > TOTAL_PAGES:
        page_num = TOTAL_PAGES

    start_idx = (page_num - 1) * COMMANDS_PER_PAGE
    end_idx = start_idx + COMMANDS_PER_PAGE
    page_commands = ALL_COMMANDS[start_idx:end_idx]

    text = (
        "✨ <b><u>AniZoneFlix Help & Command Directory</u></b> ✨\n"
        "<i>Explore all available bot commands, usages, and examples below.</i>\n\n"
        f"<b>📊 Total Commands:</b> <code>{TOTAL_COMMANDS}</code> | <b>Page:</b> <code>{page_num}/{TOTAL_PAGES}</code>\n"
        "───────────────────────────────\n\n"
    )

    for item in page_commands:
        text += (
            f"🔹 <b>{item['cmd']}</b>\n"
            f"<b>Description:</b> {item['desc']}\n"
            f"<b>Usage:</b> <code>{item['usage']}</code>\n"
            f"<b>Example:</b> {item['example']}\n\n"
        )

    text += "✨ <b>Powered by <a href='https://t.me/anizoneflix'>AniZoneFlix</a></b> ✨"

    buttons = []
    nav_row = []

    if page_num > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"help_page_{page_num - 1}", style="primary"))

    nav_row.append(InlineKeyboardButton(f"📜 {page_num}/{TOTAL_PAGES}", callback_data="help_page_noop", style="primary"))

    if page_num < TOTAL_PAGES:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"help_page_{page_num + 1}", style="primary"))

    buttons.append(nav_row)
    buttons.append([
        InlineKeyboardButton("📢 Updates Channel", url="https://t.me/anizoneflix", style="primary"),
        InlineKeyboardButton("💬 Support", url="https://t.me/anizoneflix", style="primary")
    ])
    buttons.append([
        InlineKeyboardButton("✖️ Close", callback_data="help_close", style="danger")
    ])

    return text, InlineKeyboardMarkup(buttons)


@Bot.on_message(filters.command("help") & filters.private)
async def help_command(client: Client, message: Message):
    text, reply_markup = get_help_page_content(1)
    await message.reply_photo(
        photo=get_next_image(message.chat.id),
        caption=text,
        reply_markup=reply_markup,
        has_spoiler=True,
        parse_mode=ParseMode.HTML
    )


@Bot.on_callback_query(filters.regex(r"^help_page_(\d+)$"))
async def help_page_callback(client: Client, callback_query: CallbackQuery):
    page_num = int(callback_query.matches[0].group(1))
    text, reply_markup = get_help_page_content(page_num)
    await callback_query.answer()
    if callback_query.message.photo or callback_query.message.document or callback_query.message.video or callback_query.message.animation:
        try:
            await callback_query.message.edit_caption(
                caption=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
        except Exception:
            try:
                await callback_query.message.edit_text(
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
            except Exception:
                pass
    else:
        try:
            await callback_query.message.edit_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception:
            try:
                await callback_query.message.edit_caption(
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                pass


@Bot.on_callback_query(filters.regex(r"^help_page_noop$"))
async def help_noop_callback(client: Client, callback_query: CallbackQuery):
    await callback_query.answer(text="✨ You are currently viewing this page!", show_alert=False)


@Bot.on_callback_query(filters.regex(r"^help_close$"))
async def help_close_callback(client: Client, callback_query: CallbackQuery):
    await callback_query.answer()
    try:
        await callback_query.message.delete()
    except Exception:
        pass
