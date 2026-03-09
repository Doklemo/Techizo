"""
rss.py
------
Fetch articles from configured RSS feeds using feedparser.
All feeds are fetched concurrently via asyncio.gather.
Uses the shared classifier for category assignment.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone

import feedparser
import httpx

from config import RSS_FEEDS
from fetcher.classifier import classify, generate_id

logger = logging.getLogger(__name__)


def _parse_published(entry: dict) -> str:
    """
    Extract and normalise the published date from a feed entry.
    Falls back to the current UTC time if parsing fails.
    """
    try:
        tp = entry.get("published_parsed") or entry.get("updated_parsed")
        if tp:
            dt = datetime(*tp[:6], tzinfo=timezone.utc)
            return dt.isoformat()
    except Exception:
        pass
    return datetime.now(timezone.utc).isoformat()


def _extract_image(entry: dict) -> str | None:
    """Try to pull an image URL from common RSS attachment fields."""
    # media:thumbnail
    media = entry.get("media_thumbnail")
    if media and isinstance(media, list) and media[0].get("url"):
        return media[0]["url"]

    # media:content
    media_content = entry.get("media_content")
    if media_content and isinstance(media_content, list):
        for mc in media_content:
            if mc.get("url"):
                return mc["url"]

    # enclosure
    links = entry.get("links", [])
    for link in links:
        if link.get("type", "").startswith("image"):
            return link.get("href")

    return None


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    return re.sub(r"<[^>]+>", "", text)


async def _fetch_single_feed(
    client: httpx.AsyncClient, feed_url: str, default_category: str
) -> list[dict]:
    """
    Fetch and parse a single RSS feed.

    Args:
        client: Shared httpx async client.
        feed_url: URL of the RSS feed.
        default_category: Category assigned by config (used as hint,
                          but the classifier may override based on title).

    Returns:
        List of article dicts. Empty list on failure.
    """
    try:
        resp = await client.get(feed_url)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)

        articles: list[dict] = []
        for entry in feed.entries[:15]:
            url = entry.get("link", "")
            if not url:
                continue

            title = entry.get("title", "")
            summary_raw = entry.get("summary") or entry.get("description") or ""
            summary = _strip_html(summary_raw)[:300]

            # Use the shared classifier; fall back to the feed's default
            category = classify(title, summary)
            # If classifier returns the generic 'technology' fallback,
            # prefer the feed-level category which is more specific
            if category == "technology" and default_category != "technology":
                category = default_category

            articles.append(
                {
                    "id": generate_id(url),
                    "title": title,
                    "summary": summary,
                    "source": feed.feed.get("title", "RSS"),
                    "url": url,
                    "category": category,
                    "publishedAt": _parse_published(entry),
                    "imageUrl": _extract_image(entry),
                }
            )

        logger.info(
            "RSS feed '%s' returned %d articles.",
            feed.feed.get("title", feed_url),
            len(articles),
        )
        return articles

    except Exception as exc:
        logger.error("RSS fetch failed for %s: %s", feed_url, exc)
        return []


async def fetch_rss() -> list[dict]:
    """
    Fetch and parse all configured RSS feeds **concurrently**.

    Returns a deduplicated list of article dicts. Never raises.
    """
    logger.info("Fetching %d RSS feeds concurrently…", len(RSS_FEEDS))

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            results = await asyncio.gather(
                *[
                    _fetch_single_feed(client, url, cat)
                    for url, cat in RSS_FEEDS.items()
                ],
                return_exceptions=True,
            )

        # Merge + deduplicate
        seen: dict[str, dict] = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error("RSS feed returned exception: %s", result)
                continue
            for article in result:
                seen[article["id"]] = article

        articles = list(seen.values())
        logger.info("RSS total: %d unique articles.", len(articles))
        return articles

    except Exception as exc:
        logger.error("fetch_rss() failed: %s", exc)
        return []
