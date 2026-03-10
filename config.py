"""
config.py
---------
Centralised configuration — reads all settings from a .env file.
Never hardcode API keys; this module is the single source of truth.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (same directory as this file)
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path)

# ── API Keys ─────────────────────────────────────────────────────────
NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# ── Feature Flags ────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
SUMMARISE_WITH_AI: bool = os.getenv("SUMMARISE_WITH_AI", "false").lower() == "true"

# ── Paths ────────────────────────────────────────────────────────────
BASE_DIR: Path = Path(__file__).resolve().parent
DATA_DIR: Path = BASE_DIR / "data"
FEED_CACHE_PATH: Path = DATA_DIR / "feed_cache.json"

# ── Web Push Notification Settings ───────────────────────────────────
VAPID_PRIVATE_KEY_PATH = BASE_DIR / "private_key.pem"
VAPID_CLAIMS = {
    "sub": "mailto:admin@techizo.app"
}
SUBSCRIPTIONS_FILE = DATA_DIR / "subscriptions.json"

# ── Scheduler ────────────────────────────────────────────────────────
FETCH_INTERVAL_MINUTES: int = int(os.getenv("FETCH_INTERVAL_MINUTES", "60"))

# ── Server ───────────────────────────────────────────────────────────
PORT: int = int(os.getenv("PORT", "8000"))

# ── NewsAPI ──────────────────────────────────────────────────────────
NEWSAPI_KEYWORDS: list[str] = [
    "artificial intelligence",
    "machine learning",
    "robotics",
    "openai",
    "google deepmind",
    "tech startup",
    "semiconductor",
]

# ── RSS Feeds (url → category) ───────────────────────────────────────
RSS_FEEDS: dict[str, str] = {
    "https://feeds.arstechnica.com/arstechnica/technology-lab": "technology",
    "https://www.technologyreview.com/feed/": "ai",
    "https://www.therobotreport.com/feed/": "robotics",
    "https://www.theverge.com/rss/index.xml": "technology",
    "https://techcrunch.com/feed/": "technology",
    "https://bensbites.beehiiv.com/feed": "ai",
    "https://rss.beehiiv.com/feeds/2R3C6Bt5wj.xml": "ai",
}
