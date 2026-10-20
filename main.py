import asyncio
import concurrent.futures
import json
import sqlite3
import os
import random
import re
import sys
import time
import traceback
import urllib.parse
import secrets
import hmac
import hashlib
from threading import Thread

import hydrogram
import hydrogram.enums
import hydrogram.errors
import hydrogram.filters
import hydrogram.handlers
import hydrogram.raw
import hydrogram.raw.base
import hydrogram.raw.types
import hydrogram.types
import pyrogram.utils
import requests
from flask import Flask, g, jsonify, redirect, render_template, request, session
from hydrogram.parser.html import Parser
from hydrogram.raw import types as raw_types

MAIN_LOOP = None

def run_async(coro):
    """
    Executes async coroutine on main bot event loop if running, or isolated loop otherwise.
    """
    global MAIN_LOOP
    if not MAIN_LOOP or not MAIN_LOOP.is_running():
        if hasattr(coro, "close"):
            coro.close()
        raise RuntimeError("Bot event loop is not ready; retry the request shortly.")
    future = asyncio.run_coroutine_threadsafe(coro, MAIN_LOOP)
    return future.result(timeout=20)

# Pyrogram module compatibility mapping
sys.modules["pyrogram"] = hydrogram
for name, module in list(sys.modules.items()):
    if name == "hydrogram" or name.startswith("hydrogram."):
        pyrogram_name = name.replace("hydrogram", "pyrogram", 1)
        sys.modules[pyrogram_name] = module

# Patch InlineKeyboardButton for style attributes
original_init = hydrogram.types.InlineKeyboardButton.__init__

def patched_init(self, *args, style=None, **kwargs):
    original_init(self, *args, **kwargs)
    self.style = style

hydrogram.types.InlineKeyboardButton.__init__ = patched_init

original_write = hydrogram.types.InlineKeyboardButton.write

async def patched_write(self, client):
    style_type = getattr(self, "style", None)
    text = self.text
    if text and "#" in text:
        for keyword, s_type in [("#primary", "primary"), ("#danger", "danger"), ("#success", "success"), ("#succes", "success")]:
            if keyword in text.lower():
                style_type = s_type
                self.text = text.replace(keyword, "").replace(keyword.upper(), "").strip()
                break

    res_btn = await original_write(self, client)

    if style_type and hasattr(res_btn, "style"):
        bg_primary = style_type == "primary"
        bg_danger = style_type == "danger"
        bg_success = style_type == "success"
        res_btn.style = raw_types.KeyboardButtonStyle(
            bg_primary=bg_primary or None,
            bg_danger=bg_danger or None,
            bg_success=bg_success or None
        )
    return res_btn

hydrogram.types.InlineKeyboardButton.write = patched_write

# Patch HTML Parser for blockquote expandable
original_handle_starttag = Parser.handle_starttag

def patched_handle_starttag(self, tag, attrs):
    original_handle_starttag(self, tag, attrs)
    if tag == "blockquote" and "expandable" in dict(attrs):
        if tag in self.tag_entities and self.tag_entities[tag]:
            self.tag_entities[tag][-1].collapsed = True

Parser.handle_starttag = patched_handle_starttag

# Patch message effect support
from hydrogram.types import Message

# Make this monkey-patch idempotent. If main is imported/reloaded, never wrap
# our own patched function as the original (which creates recursive invoke calls).
if not hasattr(hydrogram.Client, "_filestore_original_invoke"):
    hydrogram.Client._filestore_original_invoke = hydrogram.Client.invoke
original_invoke = hydrogram.Client._filestore_original_invoke

async def patched_invoke(self, query, *args, **kwargs):
    effect_id = getattr(self, "_current_message_effect_id", None)
    if effect_id is not None and hasattr(query, "effect"):
        query.effect = int(effect_id)
    return await original_invoke(self, query, *args, **kwargs)

hydrogram.Client.invoke = patched_invoke

original_send_photo = hydrogram.Client.send_photo
async def patched_send_photo(self, *args, **kwargs):
    effect_id = kwargs.pop("message_effect_id", None)
    if effect_id is not None:
        self._current_message_effect_id = effect_id
    try:
        return await original_send_photo(self, *args, **kwargs)
    finally:
        self._current_message_effect_id = None

hydrogram.Client.send_photo = patched_send_photo

original_send_message = hydrogram.Client.send_message
async def patched_send_message(self, *args, **kwargs):
    effect_id = kwargs.pop("message_effect_id", None)
    if effect_id is not None:
        self._current_message_effect_id = effect_id
    try:
        return await original_send_message(self, *args, **kwargs)
    finally:
        self._current_message_effect_id = None

hydrogram.Client.send_message = patched_send_message

from bot import Bot
from config import OWNER_ID, TG_BOT_TOKEN
from database.database import db
from pyrogram.errors import FloodWait

pyrogram.utils.MIN_CHANNEL_ID = -1009147483647

app = Flask(__name__, template_folder="web/templates")
# Configure a stable, deployment-provided signing secret. Never use a public/default key.
app.secret_key = os.environ.get("SESSION_SECRET_KEY", "").strip()
if not app.secret_key:
    app.secret_key = secrets.token_urlsafe(48)
    app.logger.warning("SESSION_SECRET_KEY is unset; sessions will reset when this process restarts.")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    # Secure cookies are required in production HTTPS. Set SESSION_COOKIE_SECURE=false
    # only for local HTTP development.
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "true").strip().lower() not in {"0", "false", "no", "off"},
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=1800,
    MAX_CONTENT_LENGTH=1024 * 1024,
)

def is_supported_chrome_browser(user_agent: str) -> bool:
    """
    Check if the user-agent belongs to a legitimate user web browser.
    Allows Chrome, Safari, Firefox, Edge, Opera, Samsung Internet, Mobile Safari/Chrome, etc.
    Blocks automated scrapers, headless tools, bots, crawlers, or missing User-Agents.
    """
    if not user_agent:
        return False
    ua = user_agent.lower()

    bot_keywords = [
        "python", "curl", "wget", "puppeteer", "selenium", "headless",
        "phantomjs", "bot", "crawler", "spider", "scrapy", "httpclient",
        "requests", "axios", "postman", "go-http-client", "java/",
        "libwww-perl", "golang", "aiohttp", "urllib", "httpx", "playwright"
    ]
    for b in bot_keywords:
        if b in ua:
            return False

    valid_tokens = [
        "mozilla/", "chrome/", "crios", "safari/", "firefox/", "fxios",
        "edg/", "edge/", "opr/", "opera/", "samsungbrowser/", "duckduckgo",
        "applewebkit/", "gecko/", "trident/"
    ]
    return any(token in ua for token in valid_tokens)

def is_chrome_only(user_agent: str) -> bool:
    """Require actual Chrome for the interactive verification page.

    Edge/Opera may include Chromium tokens, so exclude them explicitly.
    User-Agent checks are a compatibility gate, not a security proof.
    """
    ua = (user_agent or "").lower()
    if not ua or any(x in ua for x in ("edg/", "edga/", "edgios/", "opr/", "opera", "samsungbrowser", "firefox", "fxios", "crios")):
        return False
    return "chrome/" in ua and "chromium/" not in ua and "headlesschrome" not in ua

def is_legitimate_browser(user_agent: str) -> bool:
    return is_supported_chrome_browser(user_agent)

def is_explicit_bot_or_scraper(user_agent: str) -> bool:
    # Verification is intentionally Chrome-only; this is a compatibility check,
    # not proof of identity because User-Agent headers can be spoofed.
    return not is_chrome_only(user_agent)

def _signed_session_marker(token_key: str, session_id: str) -> str:
    """Opaque HMAC marker binds a verification attempt to its browser session."""
    payload = f"{token_key}:{session_id}".encode("utf-8")
    return hmac.new(app.secret_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _bypass_response(reason: str, token_key: str = "", target: str = ""):
    # Target is displayed only as escaped text by Jinja; never redirect to it.
    sid = str(session.get("verification_session") or "")
    if not sid:
        sid = secrets.token_urlsafe(32)
        session["verification_session"] = sid
    marker = _signed_session_marker(target[:500], sid) if target else ""
    base = request.url_root.rstrip("/")
    detected_url = (base + "/bypass-detected?" + urllib.parse.urlencode({
        "target": target[:500], "hash": marker, "session": sid[:100]
    })) if marker else ""
    return render_template("bypass_detected.html", reason=reason,
                           detected_url=detected_url, target=target[:500]), 403


def _looks_like_bookmarklet_or_script() -> bool:
    """Reject obvious bookmarklet/script probes on verification endpoints."""
    ua = (request.headers.get("User-Agent") or "").lower()
    if "javascript:" in request.url.lower() or "data:text/html" in request.url.lower():
        return True
    if request.headers.get("Sec-Fetch-Mode", "").lower() == "navigate" and "javascript:" in request.args.get("url", "").lower():
        return True
    return any(x in ua for x in ("headlesschrome", "phantomjs", "selenium", "playwright", "puppeteer"))


@app.get("/bypass-detected")
def bypass_detected():
    token_key = (request.args.get("target") or "")[:500]
    sid = (request.args.get("session") or "")[:100]
    supplied = (request.args.get("hash") or "")[:128]
    expected = _signed_session_marker(token_key, sid) if token_key and sid else ""
    if not expected or not hmac.compare_digest(supplied, expected):
        return "Invalid security event URL.", 403
    return render_template("bypass_detected.html",
                           reason="A verification bypass attempt was detected. Access was not granted.",
                           detected_url="", target=token_key), 403


@app.route('/')
def hello_world():
    return 'AniZoneFlix'


def _verification_api_db():
    """Small persistent store for third-party bot request tracking."""
    path = os.environ.get("VERIFY_API_DB_PATH", str(os.path.join(os.path.dirname(__file__), "verify_api.sqlite3")))
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("CREATE TABLE IF NOT EXISTS verification_requests (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, bot_username TEXT NOT NULL, created_at INTEGER NOT NULL)")
    connection.commit()
    return connection


def _verification_api_key_ok():
    expected = (os.environ.get("CLIENT_API_KEY") or "").strip()
    supplied = (request.headers.get("X-API-Key") or "").strip()
    return not expected or hmac.compare_digest(expected, supplied)


@app.route('/api/request', methods=['POST'])
def api_create_verification_request():
    """Register the requesting client bot before it sends a Telegram deep link."""
    if not _verification_api_key_ok():
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    try:
        user_id = int(body.get("user_id", 0))
    except (TypeError, ValueError):
        user_id = 0
    bot_name = str(body.get("bot_username") or "").strip().lstrip("@").lower()
    if user_id <= 0 or not re.fullmatch(r"[a-z0-9_]{5,32}", bot_name):
        return jsonify({"ok": False, "error": "user_id and valid bot_username are required"}), 400
    now = int(time.time())
    con = _verification_api_db()
    con.execute("INSERT INTO verification_requests(user_id, bot_username, created_at) VALUES(?,?,?)", (user_id, bot_name, now))
    con.commit(); con.close()
    cfg = run_async(db.get_config()) or {}
    bot_username = str(cfg.get("BOT_USERNAME") or os.environ.get("VERIFY_BOT_USERNAME") or "").strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", bot_username):
        bot_username = ""
    start_link = f"https://t.me/{bot_username}?start=token_{bot_name}" if bot_username else None
    return jsonify({"ok": True, "user_id": user_id, "bot_username": bot_name, "start_link": start_link, "expires_in": 1800})


@app.route('/api/<int:user_id>', methods=['GET'])
def api_verification_status(user_id):
    if user_id <= 0:
        return jsonify({"error": "user_id must be positive"}), 400
    try:
        is_verified = bool(run_async(db.is_user_verified(user_id)))
        doc = run_async(db.get_verified_user(user_id)) if is_verified else None
        expire_at = (doc or {}).get("expire_at")
        if expire_at and getattr(expire_at, "tzinfo", None) is not None:
            expire_at = expire_at.replace(tzinfo=None)
        until = int(expire_at.timestamp()) if expire_at else None
        now = int(time.time())
        return jsonify({"user_id": user_id, "verified": is_verified, "is_verified": is_verified,
                        "status": "verified" if is_verified else "not_verified",
                        "verified_until": until, "expires_in": max(0, until-now) if until else 0})
    except Exception:
        app.logger.exception("Verification status API failed")
        return jsonify({"error": "verification service temporarily unavailable"}), 503


@app.route('/api/request-status/<int:user_id>', methods=['GET'])
def api_verification_request_status(user_id):
    bot_name = str(request.args.get("bot_username") or "").strip().lstrip("@").lower()
    if user_id <= 0 or not re.fullmatch(r"[a-z0-9_]{5,32}", bot_name):
        return jsonify({"error": "positive user_id and bot_username are required"}), 400
    now = int(time.time())
    con = _verification_api_db()
    row = con.execute("SELECT created_at FROM verification_requests WHERE user_id=? AND bot_username=? AND created_at>=? ORDER BY created_at DESC LIMIT 1", (user_id, bot_name, now-1800)).fetchone()
    con.close()
    try:
        is_verified = bool(run_async(db.is_user_verified(user_id)))
        doc = run_async(db.get_verified_user(user_id)) if is_verified else None
        expire_at = (doc or {}).get("expire_at")
        if expire_at and getattr(expire_at, "tzinfo", None) is not None: expire_at = expire_at.replace(tzinfo=None)
        until = int(expire_at.timestamp()) if expire_at else None
    except Exception:
        is_verified, until = False, None
    return jsonify({"user_id": user_id, "bot_username": bot_name, "requested": bool(row),
                    "request_expires_in": max(0, int(row["created_at"])+1800-now) if row else 0,
                    "verified": is_verified, "is_verified": is_verified,
                    "status": "verified" if is_verified else "not_verified", "verified_until": until})


@app.route('/admin/set-status', methods=['POST'])
def api_admin_set_verification_status():
    expected = (os.environ.get("ADMIN_API_KEY") or "").strip()
    body = request.get_json(silent=True) or {}
    if not expected or not hmac.compare_digest(str(body.get("admin_key") or ""), expected):
        return jsonify({"error": "unauthorized"}), 401
    try: user_id = int(body.get("user_id", 0))
    except (TypeError, ValueError): user_id = 0
    verified = bool(body.get("verified", True))
    if user_id <= 0: return jsonify({"error": "invalid user_id"}), 400
    if verified:
        duration = int(run_async(db.get_config_val("VERIFY_EXPIRE_SECONDS", 86400)) or 86400)
        run_async(db.set_user_verified(user_id, duration_seconds=duration))
    else:
        awaitable = db.database['verified_users'].delete_one({'_id': user_id})
        run_async(awaitable)
    return jsonify({"user_id": user_id, "verified": verified, "status": "verified" if verified else "not_verified"})

@app.route('/v/<path:full_token>')
@app.route('/verify')
@app.route('/link/<path:subpath>')
def verify_frontend(full_token=None, subpath=None):
    token_key = full_token or subpath or request.args.get('token', '')
    if not token_key and subpath:
        parts = subpath.strip('/').split('/')
        token_key = "/".join(parts)

    if not token_key:
        return 'Invalid or missing verification token.', 400

    try:
        token_doc = run_async(db.get_verify_token(token_key))
    except Exception as err:
        app.logger.exception("Verification frontend could not access the bot/database event loop")
        return ('Verification service is starting or temporarily unavailable. '
                'Please wait a few seconds and reopen this link.'), 503
    if not token_doc:
        return 'Verification link expired or invalid.', 403

    user_agent = request.headers.get("User-Agent", "")
    if not is_chrome_only(user_agent):
        # Browsers cannot be forced to launch another app; provide a user-initiated
        # Chrome intent on Android and clear instructions elsewhere.
        current_url = request.url
        parsed = urllib.parse.urlsplit(current_url)
        android_intent = "intent://" + parsed.netloc + parsed.path
        if parsed.query:
            android_intent += "?" + parsed.query
        android_intent += "#Intent;scheme=" + (parsed.scheme or "https") + ";package=com.android.chrome;end"
        return render_template("chrome_required.html", current_url=current_url,
                               android_intent=android_intent), 200

    short_st = request.args.get('st', '')
    # Bind the flow to this browser session; the signed Flask cookie is HttpOnly.
    if session.get("verification_token") != token_key or not session.get("verification_session"):
        session.clear()
        session["verification_token"] = token_key
        session["verification_session"] = secrets.token_urlsafe(32)
        session.permanent = True

    # Initialize the flow only. Authorization is decided by the backend callback.
    session['verification_flow_started_at'] = int(time.time())
    session.permanent = True
    session.modified = True
    return render_template('verify.html', token=token_key, short_st=short_st)

@app.route('/go_shortener')
def go_shortener():
    token_key = request.args.get('token', '')
    if not token_key:
        return 'Missing verification token.', 400

    try:
        token_doc = run_async(db.get_verify_token(token_key))
    except Exception:
        app.logger.exception("Shortener redirect could not access the bot/database event loop")
        return ('Verification service is starting or temporarily unavailable. '
                'Please wait a few seconds and retry.'), 503
    if not token_doc:
        return 'Verification link expired or invalid.', 403

    short_st = request.args.get('st', '') or token_key
    tab_id = (request.args.get('tab_id') or '').strip()
    # Carry tab metadata to the shortlink; authorization is checked after callback.

    # Keep this status page intentionally static: no spinner, no animated dots,
    # and no repeated/continuous animation. The API pre-generates/caches the link.
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Redirecting</title><style>body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#090a0f;color:#fff;font:16px Arial,sans-serif}}main{{text-align:center;padding:28px;border-radius:16px;background:#191a24}}p{{color:#c4c4cc}}</style></head><body><main><h2>Redirecting, please wait</h2><p>Preparing your verification link.</p></main><script nonce="{g.csp_nonce}">fetch('/api/get_shortener_url?'+new URLSearchParams({{token:{json.dumps(token_key)},st:{json.dumps(short_st)},tab_id:{json.dumps(tab_id)}}})).then(r=>r.json()).then(d=>{{if(d&&d.url)location.replace(d.url);else{{document.querySelector('main p').textContent='Unable to generate a verification link. Please return to Telegram and try again.';}}}}).catch(()=>{{document.querySelector('main p').textContent='Verification service unavailable. Please return to Telegram and try again.';}})</script></body></html>"""

@app.route('/api/get_shortener_url')
def get_shortener_url():
    try:
        token_key = (request.args.get('token') or '').strip()
        short_st = (request.args.get('st') or token_key).strip()
        tab_id = (request.args.get('tab_id') or '').strip()
        if not token_key:
            return jsonify({'error': 'missing token'}), 400
        if not re.fullmatch(r'[A-Za-z0-9_-]{20,100}', tab_id):
            return jsonify({'error': 'invalid tab identifier'}), 400
        base_url = str(run_async(db.get_config_val('BASE_URL', 'https://your-render-service.onrender.com'))).rstrip('/')
        verify_endpoint = base_url + '/api/verify?' + urllib.parse.urlencode({'token': token_key, 'st': short_st, 'tab_id': tab_id})
        if not token_key:
            return jsonify({'error': 'missing token'}), 400
        token_doc = run_async(db.get_verify_token(token_key))
        if not token_doc:
            return jsonify({'error': 'invalid or expired token'}), 403

        # Do not reuse cached shortlinks: each attempt must carry its own tab-bound callback.
        shorteners = run_async(db.get_shorteners()) or []
        active = [item for item in shorteners if item.get('enabled', True) and item.get('domain') and item.get('api_key')]
        # Randomly select one configured active shortener per verification token.
        random.shuffle(active)
        for shortener in active:
            domain = str(shortener.get('domain', '')).strip().rstrip('/')
            api_key = str(shortener.get('api_key', '')).strip()
            if not domain or not api_key:
                continue
            if not domain.startswith(('http://', 'https://')):
                domain = 'https://' + domain
            parsed_domain = urllib.parse.urlsplit(domain)
            if parsed_domain.scheme not in ('http', 'https') or not parsed_domain.hostname:
                continue
            destination = base_url + '/api/verify?' + urllib.parse.urlencode({
                'token': token_key, 'st': short_st, 'sid': str(shortener.get('_id', '')), 'tab_id': tab_id
            })
            encoded_dest = urllib.parse.quote(destination, safe='')
            endpoints = []
            if '?' in domain:
                if 'url=' in domain:
                    endpoints.append(domain)
                elif 'api=' in domain:
                    endpoints.append(f'{domain}&url={encoded_dest}')
                else:
                    endpoints.append(f'{domain}&api={urllib.parse.quote(api_key, safe="")}&url={encoded_dest}')
            elif '/st' in domain or '/api' in domain:
                endpoints.append(f'{domain}?api={urllib.parse.quote(api_key, safe="")}&url={encoded_dest}')
            else:
                endpoints.extend([
                    f'{domain}/st?api={urllib.parse.quote(api_key, safe="")}&url={encoded_dest}',
                    f'{domain}/api?api={urllib.parse.quote(api_key, safe="")}&url={encoded_dest}',
                    f'{domain}?api={urllib.parse.quote(api_key, safe="")}&url={encoded_dest}'
                ])
            for api_url in endpoints:
                try:
                    response = requests.get(api_url, timeout=8, allow_redirects=False)
                    try:
                        data = response.json()
                    except Exception:
                        data = None
                    short_url = None
                    if isinstance(data, dict):
                        nested = data.get('data') if isinstance(data.get('data'), dict) else {}
                        short_url = (data.get('shortenedUrl') or data.get('url') or data.get('shortlink') or data.get('result') or data.get('link') or data.get('short_url') or nested.get('url') or nested.get('shortenedUrl'))
                    elif response.text.strip().startswith(('http://', 'https://')):
                        short_url = response.text.strip()
                    if not short_url:
                        continue
                    parsed_short = urllib.parse.urlsplit(str(short_url).strip().replace('\\/', '/'))
                    if parsed_short.scheme not in ('http', 'https') or not parsed_short.hostname:
                        continue
                    short_url = urllib.parse.urlunsplit(parsed_short)
                    run_async(db.update_verify_token(token_key, {
                        'cached_shortlink': short_url,
                        'selected_shortener_id': str(shortener.get('_id', ''))
                    }))
                    return jsonify({'url': short_url})
                except Exception as exc:
                    print(f'Shortener request failed for {parsed_domain.hostname}: {type(exc).__name__}')
        # If no shortener works, do not pretend a shortener verification succeeded.
        return jsonify({'error': 'No configured shortener could generate a link'}), 502
    except Exception as err:
        print(f'Error in /api/get_shortener_url: {type(err).__name__}: {err}')
        return jsonify({'error': 'verification service temporarily unavailable'}), 503

@app.route('/api/register-tab', methods=['POST'])
def register_verification_tab():
    """Record tab metadata for later backend comparison; this does not verify access."""
    payload = request.get_json(silent=True) or request.form
    token_key = str(payload.get('token') or '').strip()
    tab_id = str(payload.get('tab_id') or '').strip()
    if request.args:
        return jsonify({'ok': False, 'error': 'Unexpected query parameters'}), 400
    if not token_key or session.get('verification_token') != token_key or not session.get('verification_session'):
        return jsonify({'ok': False, 'error': 'Verification flow is not initialized'}), 403
    if not re.fullmatch(r'[A-Za-z0-9_-]{20,100}', tab_id):
        return jsonify({'ok': False, 'error': 'Invalid tab identifier'}), 400
    try:
        token_doc = run_async(db.get_verify_token(token_key))
    except Exception:
        return jsonify({'ok': False, 'error': 'Verification service unavailable'}), 503
    if not token_doc:
        return jsonify({'ok': False, 'error': 'Verification token expired'}), 403
    session['verification_tab_id'] = tab_id
    session['verification_tab_registered_at'] = int(time.time())
    session.permanent = True
    session.modified = True
    return jsonify({'ok': True})


@app.route('/api/verify', methods=['GET', 'POST'])
def verify_backend():
    """Validate shortener return, grant timed access, then send user back to Telegram."""
    token_key = (request.values.get('token') or '').strip()
    short_st = (request.values.get('st') or token_key).strip()
    sid = (request.values.get('sid') or '').strip()
    tab_id = (request.values.get('tab_id') or '').strip()
    allowed_verify_keys = {"token", "st", "sid", "tab_id"}
    unknown_keys = set(request.values.keys()) - allowed_verify_keys
    if unknown_keys:
        return _bypass_response("Unknown query parameters were rejected.", token_key, request.path)
    if not token_key:
        token_key = short_st
    if not token_key:
        return 'Invalid or missing verification token. Please reopen the link from Telegram.', 400
    user_agent = request.headers.get('User-Agent', '')
    try:
        token_doc = run_async(db.get_verify_token(token_key))
        if not token_doc:
            return 'This verification link has expired or is invalid. Please request a new link from Telegram.', 403
        if _looks_like_bookmarklet_or_script():
            return _bypass_response("Bookmarklet, headless browser, or script-like request detected.", token_key, request.path)
        # Both stages must be completed in the same signed browser session.
        browser_token = str(session.get("verification_token") or "")
        browser_sid = str(session.get("verification_session") or "")
        if browser_token != token_key or not browser_sid:
            return _bypass_response("Verification session is missing or does not match. Reopen the original link from Telegram.", token_key, request.path)
        flow_started = int(session.get('verification_flow_started_at') or 0)
        if flow_started <= 0 or int(time.time()) - flow_started > 600:
            return render_template('bypass_detected.html', reason='Verification flow expired. Session not started — reopen the original link.'), 403
        expected_tab_id = str(session.get('verification_tab_id') or '')
        if (not tab_id or not expected_tab_id or not hmac.compare_digest(tab_id, expected_tab_id)):
            return render_template('bypass_detected.html', reason='Browser tab does not match the started verification flow. Access blocked.'), 403
        user_id = int(token_doc.get('user_id') or 0)
        username = token_doc.get('username') or ''
        # Referer enforcement is optional per shortener. When disabled, do not
        # reject callbacks merely because browsers/providers omit Referer.
        selected_id = str(token_doc.get('selected_shortener_id') or sid)
        configured = run_async(db.get_shorteners()) or []
        selected = next((item for item in configured if selected_id and str(item.get('_id')) == selected_id), None)
        if selected and bool(selected.get('referer_enabled', False)):
            referer = request.headers.get('Referer', '')
            referer_host = (urllib.parse.urlsplit(referer).hostname or '').lower()
            configured_domain = str(selected.get('domain', '')).strip()
            if not configured_domain.startswith(('http://', 'https://')):
                configured_domain = 'https://' + configured_domain
            configured_host = (urllib.parse.urlsplit(configured_domain).hostname or '').lower()
            if (not referer_host or not configured_host or
                    (referer_host != configured_host and not referer_host.endswith('.' + configured_host))):
                return render_template('bypass_detected.html', reason='Shortlink referer is missing or does not match this verification flow.'), 403
        if is_explicit_bot_or_scraper(user_agent):
            # Do not grant access in a different browser; start again from the
            # original Telegram link in Chrome so the session cookie is present.
            return render_template('bypass_detected.html', reason='Chrome is required. Open the original verification link in Google Chrome and start again; session not started.'), 403
        bot_config = run_async(db.get_config()) or {}
        bot_username = str(bot_config.get('BOT_USERNAME') or '').lstrip('@')
        if not re.fullmatch(r'[A-Za-z0-9_]{5,32}', bot_username):
            bot_username = ''
        bot_dest = f'https://t.me/{bot_username}?start=verify_{token_key}' if bot_username else 'https://t.me/'
        expire_sec = int(run_async(db.get_config_val('VERIFY_EXPIRE_SECONDS', 86400)) or 86400)
        if user_id <= 0:
            return render_template('bypass_detected.html', reason='User session could not be validated. Session not started.'), 403
        run_async(db.set_user_verified(user_id, duration_seconds=expire_sec))
        run_async(db.update_verify_token(token_key, {'web_verified': True, 'backend_verification_passed': True}))
        session['verification_completed_at'] = int(time.time())
        return render_template('verify_success.html', redirect_url=bot_dest, animation_url='https://files.catbox.moe/5scyd0.gif')
    except Exception as err:
        print(f'Verification backend failed for token {token_key[:8]}…: {type(err).__name__}: {err}')
        return ('Verification could not be completed because the service is temporarily unavailable. '
                'Please return to Telegram and request a new link if this continues.'), 503



@app.before_request
def set_request_security_nonce():
    # A fresh nonce permits only the inline scripts explicitly marked by templates.
    g.csp_nonce = secrets.token_urlsafe(18)


@app.context_processor
def inject_template_security_nonce():
    return {"csp_nonce": getattr(g, "csp_nonce", "")}


@app.after_request
def apply_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{getattr(g, 'csp_nonce', '')}' https:; "
        "style-src 'self' 'unsafe-inline' https:; "
        "img-src 'self' https: data:; font-src 'self' https: data:; "
        "connect-src 'self' https:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    )
    response.headers.setdefault("Cache-Control", "no-store")
    return response


def start_uptime_monitor():
    def _monitor_loop():
        time.sleep(5)
        cached_url = None
        last_fetch = 0
        while True:
            try:
                now = time.time()
                if not cached_url or (now - last_fetch) > 10:
                    cached_url = run_async(db.get_config_val("BASE_URL", "https://your-render-service.onrender.com")).rstrip("/")
                    last_fetch = now

                if cached_url:
                    requests.get(f"{cached_url}/", timeout=4)
            except Exception:
                pass
            time.sleep(1)

    Thread(target=_monitor_loop, daemon=True).start()

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    from config import API_HASH, APP_ID, TG_BOT_TOKEN
    start_uptime_monitor()
    Thread(target=run, daemon=True).start()
    while True:
        if not APP_ID or not API_HASH or not TG_BOT_TOKEN:
            print(
                "ERROR: Required Telegram API credentials are missing! "
                "Please set APP_ID, API_HASH, and TG_BOT_TOKEN environment variables."
            )
            time.sleep(60)
            continue
        try:
            Bot().run()
        except FloodWait as e:
            print(f"FloodWait: {e.x} seconds")
            time.sleep(e.x)
        except Exception as exc:
            if "API key is required" in str(exc) or "API_ID_INVALID" in str(exc):
                print(
                    f"FATAL: Invalid or missing API key credentials: {exc}. "
                    "Please check your APP_ID, API_HASH, and TG_BOT_TOKEN environment variables."
                )
                time.sleep(60)
            else:
                print(f"FATAL: Bot crashed at startup: {exc}")
                traceback.print_exc()
                time.sleep(10)
