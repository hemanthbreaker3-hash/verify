"""Small Flask website and safe path-preserving proxy to the Render bot service."""
from __future__ import annotations
import os
import html
import re
from urllib.parse import urlsplit, urlencode
import requests
from flask import Flask, Response, jsonify, request

from config import RENDER_BACKEND_URL, SITE_NAME, TELEGRAM_BOT_USERNAME, VERCEL_BASE_URL

app = Flask(__name__)
TIMEOUT = (5, 25)
HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te",
              "trailers", "transfer-encoding", "upgrade", "content-encoding", "content-length"}


def _valid_backend(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return parsed.scheme == "https" and bool(parsed.hostname) and parsed.username is None and parsed.password is None
    except Exception:
        return False


@app.get("/")
def home():
    bot_username = TELEGRAM_BOT_USERNAME.strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", bot_username):
        bot_username = ""
    bot_url = f"https://t.me/{bot_username}" if bot_username else "#bot"
    site_name = html.escape(SITE_NAME)
    safe_bot_url = html.escape(bot_url, quote=True)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#080d1d"><title>{site_name}</title><style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}body{{margin:0;font:16px/1.6 system-ui,-apple-system,Segoe UI,sans-serif;background:radial-gradient(ellipse at 15% 5%,#142b67 0,transparent 42%),radial-gradient(ellipse at 90% 70%,#32165e 0,transparent 35%),#080d1d;color:#f5f7ff;min-height:100vh;display:grid;place-items:center;padding:24px}}main{{width:min(900px,100%);border:1px solid #34466e;background:#0b1326dd;border-radius:28px;padding:clamp(28px,6vw,64px);box-shadow:0 24px 80px #0008}}.tag{{color:#7cebd3;font-weight:700;letter-spacing:.12em;text-transform:uppercase;font-size:.8rem}}h1{{font-size:clamp(2.4rem,7vw,5rem);line-height:1.04;margin:16px 0}}p{{color:#c6d0e9;max-width:650px}}.chips{{display:flex;flex-wrap:wrap;gap:10px;margin:26px 0}}.chips span{{border:1px solid #35476b;background:#111f3b;border-radius:999px;padding:8px 13px}}a{{display:inline-block;background:linear-gradient(100deg,#08a9ee,#5865f2);padding:13px 20px;border-radius:13px;color:white;text-decoration:none;font-weight:700}}footer{{margin-top:35px;color:#8494b8;font-size:.85rem}}</style></head><body><main><div class="tag">✨ File sharing made simple</div><h1>Welcome to<br>{site_name}</h1><p>Share files, create links, and manage access through our Telegram bot. Verification links are securely handled by the connected backend.</p><div class="chips"><span>⚡ Fast</span><span>🔒 Access verification</span><span>📁 File sharing</span><span>🤖 Telegram powered</span></div><a href="{safe_bot_url}" rel="noopener noreferrer">Open Telegram Bot ↗</a><footer>Website hosted on Vercel · Bot service hosted on Render</footer></main></body></html>'''


@app.get("/healthz")
def healthz():
    return jsonify(ok=True, service="vercel-site", backend_configured=bool(RENDER_BACKEND_URL), base_url=VERCEL_BASE_URL or None)


@app.route("/api/proxy", defaults={"path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
@app.route("/api/proxy/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
def proxy(path: str):
    # Rewrites preserve the original path in the `path` query parameter.
    original_path = request.args.get("path", path).lstrip("/")
    if original_path in {"", "index.html"}:
        return home()
    if original_path == "healthz":
        return healthz()
    original_query = request.args.get("query", "")
    if not original_query:
        forwarded_args = [(key, value) for key in request.args for value in request.args.getlist(key) if key not in {"path", "query"}]
        original_query = urlencode(forwarded_args, doseq=True)
    if not RENDER_BACKEND_URL:
        return jsonify(error="Backend is not configured. Set RENDER_BACKEND_URL in Vercel Environment Variables."), 503
    if not _valid_backend(RENDER_BACKEND_URL):
        return jsonify(error="RENDER_BACKEND_URL must be a valid HTTPS URL."), 500
    # Prevent proxying to arbitrary hosts; only the configured Render host is used.
    target = f"{RENDER_BACKEND_URL}/{original_path}"
    query_string = original_query
    if query_string:
        target += "?" + query_string
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP and k.lower() not in {"host", "content-length", "accept-encoding"}}
    # Ask the Render backend for an uncompressed body. If Vercel's incoming
    # Accept-Encoding (for example br/zstd) is forwarded, requests may not
    # decode that encoding but this proxy strips Content-Encoding; the browser
    # then displays compressed bytes as replacement characters. Identity avoids
    # that mismatch and keeps HTML/JSON verification responses readable.
    headers["Accept-Encoding"] = "identity"
    try:
        upstream = requests.request(method=request.method, url=target, params=None,
                                    data=request.get_data(), headers=headers,
                                    cookies=request.cookies, timeout=TIMEOUT, allow_redirects=False)
    except requests.RequestException:
        app.logger.exception("Render backend request failed")
        return jsonify(error="Backend temporarily unavailable. Please try again shortly."), 502
    response_headers = [(k, v) for k, v in upstream.headers.items() if k.lower() not in HOP_BY_HOP]
    # Preserve redirects, cookies, and HTML/JSON returned by the backend.
    return Response(upstream.content, status=upstream.status_code, headers=response_headers)
