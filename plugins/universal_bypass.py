import asyncio
import json
import re
import urllib.parse
import requests
from pyrogram import Client, filters
from pyrogram.types import Message
from bot import Bot

MAX_REDIRECTS = 10
MAX_TELEGRAM_URL_LENGTH = 4096

# Supported target parameter names
TARGET_KEYS = [
    'nicktrick',
    'url',
    'target',
    'link',
    'dest',
    'destination',
    'go',
    'to',
    'out'
]

BYPASS_REGEX = re.compile(r"^[^\s=]+=[^\s=]+$", re.IGNORECASE)

def extract_raw_input_text(message: Message) -> str:
    """
    Extract target string/URL from message text, caption, or message entities (hyperlinks).
    Handles text_link entities where the URL is hidden behind hyperlink text.
    """
    raw_text = (message.text or message.caption or "").strip()
    if raw_text and not raw_text.startswith("/"):
        if is_valid_bypass_string(raw_text):
            return raw_text

    entities = message.entities or message.caption_entities
    if entities:
        for entity in entities:
            if entity.type.name == "TEXT_LINK" and entity.url:
                url_val = entity.url.strip()
                if is_valid_bypass_string(url_val):
                    return url_val
            elif entity.type.name == "URL":
                full_str = message.text or message.caption or ""
                url_val = full_str[entity.offset : entity.offset + entity.length].strip()
                if is_valid_bypass_string(url_val):
                    return url_val

    return ""

def is_valid_bypass_string(text: str) -> bool:
    if not text or text.startswith("/"):
        return False
    clean_text = text.strip()
    if " " in clean_text:
        return False
    if BYPASS_REGEX.match(clean_text):
        return True
    if "=" in clean_text:
        return True
    for key in TARGET_KEYS:
        if f"{key}=" in clean_text.lower():
            return True
    return False

def is_bypass_message(_, __, message: Message) -> bool:
    return bool(extract_raw_input_text(message))

bypass_filter = filters.create(is_bypass_message)

def extract_target_and_referer(input_url: str):
    """
    Extract target URL and referer URL from input string.
    Supports any domain/shortener (e.g. short4cash.com, short4cast.com, etc.),
    handling domainurl=targeturl formats and query parameter formats.
    """
    target_url = None
    referer_url = None

    # Handle domain.com=target.com or https://domain.com=https://target.com
    equal_index = input_url.find('=')
    if equal_index != -1 and '?' not in input_url[:equal_index]:
        referer_part = input_url[:equal_index].strip()
        target_part = input_url[equal_index + 1:].strip()

        if referer_part:
            if not referer_part.startswith(('http://', 'https://')):
                referer_url = 'https://' + referer_part
            else:
                referer_url = referer_part

        if target_part:
            if not target_part.startswith(('http://', 'https://')):
                target_url = 'https://' + target_part
            else:
                target_url = target_part

        return target_url, referer_url

    # Handle query parameter or wrapper URL formats
    normalized_input = input_url if input_url.startswith(('http://', 'https://')) else f'https://{input_url}'
    try:
        parsed = urllib.parse.urlparse(normalized_input)
        referer_url = f'{parsed.scheme}://{parsed.netloc}/'
        query_params = urllib.parse.parse_qs(parsed.query)

        for key in TARGET_KEYS:
            if key in query_params:
                val = query_params[key][0]
                if not val.startswith(('http://', 'https://')):
                    val = 'https://' + val
                target_url = val
                break

        if not target_url:
            match = re.search(r'=(https?://[^\s&]+)', normalized_input, re.IGNORECASE)
            if match:
                target_url = urllib.parse.unquote(match.group(1))
            else:
                match_raw = re.search(r'=([^\s&]+)', normalized_input, re.IGNORECASE)
                if match_raw:
                    raw_val = urllib.parse.unquote(match_raw.group(1))
                    if not raw_val.startswith(('http://', 'https://')):
                        raw_val = 'https://' + raw_val
                    target_url = raw_val
    except Exception:
        pass

    final_target = target_url or normalized_input
    final_referer = referer_url or normalized_input
    return final_target, final_referer

def upload_to_spacebin(content: str) -> str:
    """
    Upload long URL content to Spacebin.
    """
    try:
        resp = requests.post(
            "https://spaceb.in/api/v1/documents",
            json={"content": content, "extension": "txt"},
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            if data and isinstance(data, dict) and data.get("payload") and data["payload"].get("id"):
                return f"https://spaceb.in/{data['payload']['id']}"
    except Exception:
        pass
    return None

def resolve_universal(start_url: str, referer: str, depth: int = 0) -> str:
    """
    Follow HTTP/HTTPS redirects manually using requests in Python.
    """
    if depth > MAX_REDIRECTS:
        return None

    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36',
        'Referer': referer,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9'
    }

    try:
        resp = requests.get(
            start_url,
            headers=headers,
            allow_redirects=False,
            timeout=20
        )
    except Exception as e:
        return None

    redirect_codes = [301, 302, 303, 307, 308]
    if resp.status_code in redirect_codes and 'location' in resp.headers:
        redirect_url = urllib.parse.urljoin(start_url, resp.headers['location'])
        return resolve_universal(redirect_url, start_url, depth + 1)

    return start_url

async def run_universal_bypass(input_url: str, custom_referer: str = None):
    """
    Run universal bypass resolver in pure Python.
    """
    def _bypass_sync():
        target_url, referer_url = extract_target_and_referer(input_url)
        final_referer = custom_referer or referer_url
        final_url = resolve_universal(target_url, final_referer)
        return final_url

    final_url = await asyncio.to_thread(_bypass_sync)
    return final_url

@Bot.on_message(filters.private & bypass_filter)
async def universal_bypass_handler(client: Client, message: Message):
    input_text = extract_raw_input_text(message)
    if not input_text:
        return

    status_msg = await message.reply_text("<b>⏳ Resolving URL, please wait...</b>", quote=True)

    try:
        final_url = await run_universal_bypass(input_text)

        if not final_url:
            await status_msg.edit("<b>❌ Bypass failed or maximum redirect limit reached.</b>")
            return

        if len(final_url) > MAX_TELEGRAM_URL_LENGTH:
            spacebin_link = await asyncio.to_thread(upload_to_spacebin, final_url)
            if spacebin_link:
                response_text = (
                    "<b>✅ Universal Bypass Success!</b>\n\n"
                    f"<b>Spacebin Link:</b>\n{spacebin_link}"
                )
            else:
                response_text = (
                    "<b>✅ Universal Bypass Success!</b>\n\n"
                    f"<b>Final URL (Spacebin upload failed):</b>\n<code>{final_url}</code>"
                )
        else:
            response_text = (
                "<b>✅ Universal Bypass Success!</b>\n\n"
                f"<b>Final URL:</b>\n<code>{final_url}</code>"
            )

        await status_msg.edit(response_text, disable_web_page_preview=True)

    except Exception as e:
        await status_msg.edit(f"<b>❌ An error occurred:</b> <code>{e}</code>")
