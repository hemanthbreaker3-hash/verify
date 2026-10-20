"""Vercel website configuration. Production values should be set in Vercel env vars."""
from __future__ import annotations
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
except ImportError:
    pass

SITE_NAME = os.getenv("SITE_NAME", "AniZoneFlix FileStore").strip() or "AniZoneFlix FileStore"
RENDER_BACKEND_URL = os.getenv("RENDER_BACKEND_URL", "https://filestore-2-ltvv.onrender.com").strip().rstrip("/")
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
# Vercel's production URL is preferred over a preview deployment URL.
VERCEL_BASE_URL = os.getenv("VERCEL_PROJECT_PRODUCTION_URL", "").strip()
if VERCEL_BASE_URL and not VERCEL_BASE_URL.startswith(("http://", "https://")):
    VERCEL_BASE_URL = "https://" + VERCEL_BASE_URL
if not VERCEL_BASE_URL:
    VERCEL_BASE_URL = os.getenv("VERCEL_URL", "").strip()
    if VERCEL_BASE_URL and not VERCEL_BASE_URL.startswith(("http://", "https://")):
        VERCEL_BASE_URL = "https://" + VERCEL_BASE_URL
