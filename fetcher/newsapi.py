"""
newsapi.py
----------
Fetch articles from NewsAPI /v2/everything endpoint.
Fires all keyword queries in parallel with httpx, maps each result
to the Pulse article schema, and auto-classifies the category.
"""

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from config import NEWS_API_KEY
from fetcher.classifier import classify, generate_id

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────
_NEWSAPI_URL = "https://newsapi.org/v2/everything"

# Each query is fired as a separate parallel request for broader coverage
_QUERIES: list[str] = [
    "artificial intelligence",
    "machine learning",
    "robotics automation",
    "openai anthropic",
    "tech startup",
]


async def _fetch_query(
    client: httpx.AsyncClient, query: str
) -> list[dict]:
    """
    Execute a single NewsAPI query and return mapped articles.

    Args:
        client: Shared httpx async client.
        query: Search keyword string.

    Returns:
        List of article dicts. Empty list on failure.
    """
    try:
        params = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 20,
            "apiKey": NEWS_API_KEY,
        }

        resp = await client.get(_NEWSAPI_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

        articles: list[dict] = []
        for item in data.get("articles", []):
            url = item.get("url", "")
            if not url:
                continue

            title = item.get("title") or ""
            description = item.get("description") or ""

            # Skip "[Removed]" placeholder articles from NewsAPI
            if title == "[Removed]" or url == "https://removed.com":
                continue

            articles.append(
                {
                    "id": generate_id(url),
                    "title": title,
                    "summary": description[:300],
                    "source": (item.get("source") or {}).get("name", "Unknown"),
                    "url": url,
                    "category": classify(title, description),
                    "publishedAt": item.get("publishedAt")
                    or datetime.now(timezone.utc).isoformat(),
                    "imageUrl": item.get("urlToImage"),
                }
            )

        logger.info(
            "NewsAPI query '%s' returned %d articles.", query, len(articles)
        )
        return articles

    except Exception as exc:
        logger.error("NewsAPI query '%s' failed: %s", query, exc)
        return []


async def fetch_newsapi() -> list[dict]:
    """
    Fetch articles from NewsAPI for all queries **in parallel**.

    Each query in ``_QUERIES`` is dispatched concurrently via
    ``asyncio.gather``. Results are merged and deduplicated by URL hash.

    Returns:
        Deduplicated list of article dicts. Never raises.
    """
    if not NEWS_API_KEY:
        logger.warning("NEWS_API_KEY not set — skipping NewsAPI fetch.")
        return []

    logger.info("Fetching NewsAPI articles across %d queries…", len(_QUERIES))

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            # Fire all queries in parallel
            results = await asyncio.gather(
                *[_fetch_query(client, q) for q in _QUERIES],
                return_exceptions=True,
            )

        # Merge + deduplicate by article id
        seen: dict[str, dict] = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error("Parallel query returned exception: %s", result)
                continue
            for article in result:
                seen[article["id"]] = article

        articles = list(seen.values())
        logger.info("NewsAPI total: %d unique articles.", len(articles))
        return articles

    except Exception as exc:
        logger.error("NewsAPI fetch_newsapi() failed: %s", exc)
        return []
