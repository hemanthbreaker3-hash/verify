# AniZoneFlix FileStore

Telegram-powered file sharing bot with a Flask verification website, configurable shorteners, and an optional Vercel-to-Render website proxy.

## Features

- Telegram bot for file links, batch links, access management, force-subscription, and admin tools.
- Flask verification pages stored in `web/templates/`.
- Shortlink callback verification performed by the backend.
- Session, flow-expiry, and browser-tab binding checks before access is granted.
- Optional Referer enforcement per configured shortener. When disabled for a shortener, the Referer check is skipped; the remaining backend checks still apply.
- Security response headers and a Content Security Policy nonce for the verification page's inline scripts.
- Optional Vercel frontend/proxy under `vercel/`.

## Project layout

```text
.
├── main.py                 # Flask verification app and bot process entry point
├── bot.py                  # Telegram bot client
├── config.py               # Environment configuration
├── database/
│   └── database.py         # MongoDB access layer
├── plugins/                # Telegram bot command handlers
├── web/
│   └── templates/          # HTML templates for verification states
├── universal_bypass.js     # Frontend utility used by the project
├── requirements.txt
├── Dockerfile
├── Procfile
└── vercel/                 # Optional Vercel frontend/proxy
```

## Required environment variables

Set these in your hosting provider's environment settings. Never commit real credentials or `.env` files.

| Variable | Required | Description |
|---|---:|---|
| `TG_BOT_TOKEN` | Yes | Telegram bot token from BotFather |
| `APP_ID` | Yes | Telegram API ID |
| `API_HASH` | Yes | Telegram API hash |
| `DATABASE_URL` | Yes | MongoDB connection URI |
| `CHANNEL_ID` | Recommended | Telegram channel ID used to store/retrieve files |
| `OWNER_ID` | Recommended | Numeric Telegram owner ID |
| `SESSION_SECRET_KEY` | Yes for stable production sessions | Long random secret used to sign Flask sessions; keep stable across deploys and instances |
| `PORT` | No | Web server port; defaults to `8080` |
| `DB_NAME` | No | MongoDB database name; defaults to `Filestore` |
| `SESSION_COOKIE_SECURE` | No | Defaults to `true`; set to `false` only for local HTTP development |
| `LOG_LEVEL` | No | Python logging level, e.g. `INFO` or `DEBUG` |

Generate a session secret locally:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set the resulting value as `SESSION_SECRET_KEY` in the host dashboard. Do not paste the secret into source code or commit it. If the secret changes, existing browser sessions will be invalidated.

Other optional bot settings are read from environment variables in `config.py`, including `TG_BOT_WORKERS`, `FSUB_LINK_EXPIRY`, `START_PIC`, `FORCE_PIC`, `PROTECT_CONTENT`, and custom message values.

## Deploy on Render

1. Create a Render **Web Service** from this repository.
2. Use the repository's Dockerfile, or set the build command to `pip install -r requirements.txt` and the start command to `python main.py`.
3. Add the required environment variables above.
4. Deploy and wait for the bot and web service to start.
5. Open the service URL and confirm the home page responds.
6. In the bot's admin/panel commands, set the public `BASE_URL` to the Render service URL. Use the exact HTTPS origin, without a trailing path.
7. Configure shortener API domains and keys in the bot panel, then test a fresh verification link end-to-end.

The bot and Flask app share a process in the default deployment. Use one process/worker unless the application is refactored to share its event loop and database lifecycle across workers.

## Optional Vercel frontend

The `vercel/` directory provides a small landing page and path-preserving proxy. Configure these Vercel environment variables:

- `RENDER_BACKEND_URL`: the HTTPS URL of the Render backend.
- `TELEGRAM_BOT_USERNAME`: bot username without the leading `@`.
- `SITE_NAME`: optional website title.

If the Vercel domain is used for user-facing links, ensure the backend's `BASE_URL` and the generated callback URLs consistently use the intended public domain. Do not mix Render and Vercel origins in the same flow unless the proxy forwards cookies and callback paths correctly.

## Per-shortener Referer ON/OFF settings

1. Open `/panel` as an admin and choose **🧭 Referer Settings**, or open **🔗 Shorteners**.
2. Each configured shortener has its own **Enable/Disable** Referer button. Settings are stored on that shortener record in MongoDB and persist across restarts.
3. **ON** checks that the verification callback's `Referer` hostname matches the selected shortener's configured hostname. **OFF** skips only that Referer check; the normal signed-token, browser session, tab, and expiry validation still runs.
4. Newly added shorteners default to **OFF** because some providers and browser privacy settings suppress Referer headers. Enable it per provider only after testing the complete flow.

## Verification flow

1. User opens the frontend verification page.
2. The page navigates to the configured shortlink.
3. The shortener returns the browser to the backend callback.
4. The backend validates the token, session, expiry, browser-tab binding, and (only if enabled for that shortener) the Referer.
5. The backend grants access and redirects to the Telegram bot only if all required checks pass. Any failed check denies access.

The frontend is for presentation and navigation; backend code is the authorization authority. A browser tab identifier and Referer are supplementary signals, not cryptographic proof of a human or a specific physical tab. Do not treat them as substitutes for server-side sessions, short-lived tokens, expiry, rate limiting, and one-time token consumption.

## Local development

Use Python 3.10 or newer. Install dependencies in a virtual environment:

```bash
python -m venv .venv
# Linux/macOS
. .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Set the required environment variables, then run:

```bash
python main.py
```

For local HTTP only, set `SESSION_COOKIE_SECURE=false`; restore it to `true` in HTTPS production. MongoDB and valid Telegram credentials are needed to exercise the full app. The browser verification flow cannot be fully tested by Python syntax checks alone.

## Troubleshooting

- **Sessions restart unexpectedly:** set a persistent `SESSION_SECRET_KEY`; do not generate a new value at every start.
- **Browser does not keep the session locally:** local HTTP development needs `SESSION_COOKIE_SECURE=false`. Production should use HTTPS and leave it enabled.
- **Verification says the session was not started:** reopen the original link in the same browser tab and complete the shortlink without switching browsers. Confirm the public callback URL points to this backend.
- **No shortener can generate a link:** check the configured shortener domain/API key and inspect application logs. The backend intentionally refuses to grant access when no shortener succeeds.
- **Database unavailable:** verify `DATABASE_URL`, database network access, and provider allowlists.
- **Bot starts but cannot retrieve files:** verify `CHANNEL_ID` and that the bot is an administrator in the storage channel.
- **Imports fail during deployment:** use the supported Python version and install all packages from `requirements.txt`; check the first missing/incompatible package in build logs.

## Security notes

- Keep `SESSION_SECRET_KEY`, Telegram credentials, and MongoDB credentials private.
- Keep the service on HTTPS in production.
- Review logs before enabling verbose logging in a public deployment; do not log tokens or session cookies.
- A successful syntax check is not equivalent to a full production security audit. Test the actual browser → shortener → callback → Telegram flow after each deployment.


## External Telegram bot verification API (full FileStore verification flow)

An integrating bot should call `POST /api/request` before sending the returned deep link. Set `CLIENT_API_KEY` on the FileStore service and send it in `X-API-Key` when you want to protect request registration. The user opens the returned `https://t.me/<bot>?start=token_<client_bot_username>` link. FileStore checks that a request for that Telegram user and client bot was registered in the previous 30 minutes. It then sends the same browser session + shortener flow used by FileStore itself. The browser callback grants timed verification only after the existing flow validates the token/session/tab/shortener callback.

- `POST /api/request` JSON: `{"user_id": 123456789, "bot_username": "Naya_Leech_Bot"}`; optional header `X-API-Key`.
- `GET /api/<user_id>` returns `verified`, `status`, `verified_until`, and `expires_in`.
- `GET /api/request-status/<user_id>?bot_username=Naya_Leech_Bot` checks request registration and status.
- `POST /admin/set-status` can set or revoke access with JSON `{"user_id":123456789,"verified":true,"admin_key":"..."}`; configure `ADMIN_API_KEY`.
- `VERIFY_API_DB_PATH` optionally selects the SQLite path for request tracking; use persistent storage in deployment.

Example (Python):
```python
import requests
API = "https://your-filestore.onrender.com"
response = requests.post(
    API + "/api/request",
    json={"user_id": user_id, "bot_username": "Naya_Leech_Bot"},
    headers={"X-API-Key": "YOUR_CLIENT_API_KEY"}, timeout=10,
)
response.raise_for_status()
verify_link = response.json()["start_link"]
# Send verify_link to the user as an inline keyboard URL button.

status = requests.get(f"{API}/api/{user_id}", timeout=10).json()
if status.get("verified"):
    # Allow access; do not show the verification button while unexpired.
    pass
```


This package includes the same full verification flow as the FileStore build: browser session binding, shortener URL generation, validated callback, timed access grant, and Telegram return deep link. The external bot API is integrated in `main.py` and request validation is handled in `plugins/start.py`.
