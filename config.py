"""Configuration for AniZoneFlix FileStore.

Set credentials in the deployment environment (Render → Environment) or in a
local .env file. Do not commit real credentials to GitHub.
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# .env is optional in production; environment variables always remain supported.
if load_dotenv is not None:
    load_dotenv(BASE_DIR / ".env", override=False)

def _getenv(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()

def _getint(name: str, default: int, minimum: int | None = None) -> int:
    raw = _getenv(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        logging.getLogger("config").warning(
            "Invalid integer for %s; using default %s.", name, default
        )
        return default
    if minimum is not None and value < minimum:
        logging.getLogger("config").warning(
            "%s must be >= %s; using default %s.", name, minimum, default
        )
        return default
    return value

# Required credentials: intentionally no hard-coded secrets.
TG_BOT_TOKEN = _getenv("TG_BOT_TOKEN")
APP_ID = _getint("APP_ID", 0, minimum=1)
API_HASH = _getenv("API_HASH")
CHANNEL_ID = _getint("CHANNEL_ID", 0)
OWNER = _getenv("OWNER")
OWNER_ID = _getint("OWNER_ID", 0)
PORT = _getenv("PORT", "8080")
DB_URI = _getenv("DATABASE_URL")
DB_NAME = _getenv("DB_NAME", "Filestore") or "Filestore"

FSUB_LINK_EXPIRY = _getint("FSUB_LINK_EXPIRY", 10, minimum=1)
BAN_SUPPORT = _getenv("BAN_SUPPORT", "https://t.me/anizoneflix")
TG_BOT_WORKERS = _getint("TG_BOT_WORKERS", 16, minimum=1)
START_PIC = _getenv(
    "START_PIC",
    "https://graph.org/file/0591ce5558c3ec8fe7612-263292508134daf3e1.jpg",
)
FORCE_PIC = _getenv(
    "FORCE_PIC",
    "https://graph.org/file/fdc4357abfaba23255e98-24d1bbfa3888cdfcfe.jpg",
)

HELP_TXT = (
    "<b>✨ AniZoneFlix Help Directory</b>\n\n"
    "<blockquote>Manage files, batch links, verification, shorteners, and bot settings "
    "using the available commands.</blockquote>\n\n"
    "<b>📢 Updates:</b> @anizoneflix"
)
ABOUT_TXT = (
    "<b>🤖 AniZoneFlix FileStore</b>\n\n"
    "<blockquote>Share files, create batch links, and manage file access.</blockquote>\n\n"
    '<b>📢 Updates:</b> <a href="https://t.me/anizoneflix">@anizoneflix</a>'
)
START_MSG = _getenv(
    "START_MESSAGE",
    "<b>👋 Hello {first}!</b>\n\n"
    "<blockquote>Welcome to AniZoneFlix FileStore. Send a supported file link "
    "or choose an option below to get started.</blockquote>\n\n"
    "<b>📢 Updates:</b> @anizoneflix",
)
FORCE_MSG = _getenv(
    "FORCE_SUB_MESSAGE",
    "<b>🔒 Subscription required</b>\n\n"
    "<blockquote>Join the required channel(s), then tap <b>Try Again</b> to continue.</blockquote>",
)
CMD_TXT = (
    "<b><blockquote>⚙️ Admin Commands</blockquote></b>\n"
    "<b>/delete</b> — Delete content from the database channel\n"
    "<b>/dlt_time</b> — Set the auto-delete duration\n"
    "<b>/check_dlt_time</b> — View the current auto-delete timer\n"
    "<b>/dbroadcast</b> — Broadcast a document or video\n"
    "<b>/ban</b> / <b>/unban</b> — Manage user access\n"
    "<b>/banlist</b> — List banned users\n"
    "<b>/addchnl</b> / <b>/delchnl</b> — Manage force-subscription channels\n"
    "<b>/listchnl</b> — List force-subscription channels\n"
    "<b>/fsub_mode</b> — Toggle force-subscription mode\n"
    "<b>/pbroadcast</b> — Broadcast a photo\n"
    "<b>/add_admin</b> / <b>/deladmin</b> — Manage admins\n"
    "<b>/admins</b> — List active admins"
)
CUSTOM_CAPTION = _getenv("CUSTOM_CAPTION", "<b>• By @anizoneflix</b>")
CUSTOM_DELETE_ALERT = _getenv(
    "CUSTOM_DELETE_ALERT",
    "<b><blockquote>⚠️ This file was automatically deleted. Request access again using the available options.</blockquote></b>",
)
PROTECT_CONTENT = _getenv("PROTECT_CONTENT", "False").lower() in {"1", "true", "yes", "on"}
DISABLE_CHANNEL_BUTTON = _getenv("DISABLE_CHANNEL_BUTTON", "False").lower() in {"1", "true", "yes", "on"}
BOT_STATS_TEXT = (
    "<b>📊 AniZoneFlix Statistics</b>\n\n"
    "<blockquote>⏱️ Uptime: <code>{uptime}</code>\n"
    "⚙️ CPU: <code>{cpu}%</code>\n"
    "🧠 RAM: <code>{ram}%</code>\n"
    "👥 Users: <code>{users}</code></blockquote>"
)
USER_REPLY_TEXT = "<blockquote>⚠️ Access denied. You do not have permission to use this command.</blockquote>"
USER_ROAST_TEXT = "<blockquote>⚠️ Admin privileges are required to perform this action.</blockquote>"

LOG_FILE_NAME = str(BASE_DIR / "filesharingbot.txt")
logging.basicConfig(
    level=getattr(logging, _getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler(LOG_FILE_NAME, maxBytes=10_000_000, backupCount=3, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("hydrogram").setLevel(logging.WARNING)

def LOGGER(name: str) -> logging.Logger:
    """Return a named application logger."""
    return logging.getLogger(name)

# Clear startup diagnostics without printing credentials.
_required = {
    "TG_BOT_TOKEN": TG_BOT_TOKEN,
    "APP_ID": APP_ID,
    "API_HASH": API_HASH,
    "DATABASE_URL": DB_URI,
}
_missing = [name for name, value in _required.items() if not value]
if _missing:
    logging.getLogger("config").warning(
        "Missing configuration values: %s. Set them in Render Environment before production use.",
        ", ".join(_missing),
    )
