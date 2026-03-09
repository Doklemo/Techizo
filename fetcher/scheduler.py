"""
scheduler.py
-------------
Background scheduler that periodically fetches articles from all sources,
deduplicates them, and writes the result to feed_cache.json.

Runs an initial fetch on startup, then repeats every FETCH_INTERVAL_MINUTES.
Uses APScheduler's AsyncIOScheduler with an interval trigger.
"""

import json
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import FETCH_INTERVAL_MINUTES, FEED_CACHE_PATH, DATA_DIR

logger = logging.getLogger(__name__)

# Module-level scheduler instance
_scheduler: AsyncIOScheduler | None = None


def _dispatch_push_notifications(new_articles: list[dict]) -> None:
    """Detects new top-stories by category and dispatches pywebpush JSON payloads independently to secure subscribers."""
    if not new_articles:
        return
    try:
        from config import SUBSCRIPTIONS_FILE, VAPID_PRIVATE_KEY_PATH, VAPID_CLAIMS
        import pywebpush

        if not SUBSCRIPTIONS_FILE.exists():
            return
            
        subs = json.loads(SUBSCRIPTIONS_FILE.read_text(encoding="utf-8"))
        if not subs:
            return

        # Isolate the definitive top breaking story for each category
        top_by_cat = {}
        for a in new_articles:
            cat = a.get("category", "breaking")
            if cat not in top_by_cat:
                top_by_cat[cat] = a

        for cat, article in top_by_cat.items():
            payload = json.dumps({
                "title": f"Techizo — {cat.capitalize()}",
                "body": article.get("title", "New updates are available"),
                "icon": "/static/icons/icon-192.png",
                "url": "/"
            })
            for sub in subs:
                try:
                    pywebpush.webpush(
                        subscription_info=sub,
                        data=payload,
                        vapid_private_key=str(VAPID_PRIVATE_KEY_PATH),
                        vapid_claims=VAPID_CLAIMS
                    )
                except pywebpush.WebPushException as ex:
                    logger.debug("WebPush exception for %s: %s", sub.get("endpoint"), ex)
                except Exception as ex:
                    logger.error("WebPush dispatch exception: %s", ex)
    except Exception as exc:
        logger.error("Critical failure sequencing push notifications: %s", exc)


async def refresh_feeds() -> None:
    """
    Fetch articles from NewsAPI + RSS, merge, deduplicate by id,
    sort by date, persist to feed_cache.json, and log a summary.
    """
    from fetcher.newsapi import fetch_newsapi
    from fetcher.rss import fetch_rss
    from fetcher.scraper import fetch_scraped
    from fetcher.summariser import summarise_batch

    logger.info("═" * 60)
    logger.info("Starting feed refresh…")

    # Capture preexisting DB arrays to diff new articles
    existing_ids = set()
    try:
        if FEED_CACHE_PATH.exists():
            old_data = json.loads(FEED_CACHE_PATH.read_text(encoding="utf-8"))
            existing_ids = {a["id"] for a in old_data if "id" in a}
    except Exception:
        pass

    newsapi_count = 0
    rss_count = 0
    scraped_count = 0

    try:
        newsapi_articles = await fetch_newsapi()
        rss_articles = await fetch_rss()
        scraped_articles = await fetch_scraped()

        newsapi_count = len(newsapi_articles)
        rss_count = len(rss_articles)
        scraped_count = len(scraped_articles)

        # Merge and deduplicate by article id
        all_articles: dict[str, dict] = {}
        for article in newsapi_articles + rss_articles + scraped_articles:
            all_articles[article["id"]] = article

        # Sort by publishedAt descending (newest first)
        sorted_articles = sorted(
            all_articles.values(),
            key=lambda a: a.get("publishedAt", ""),
            reverse=True,
        )

        # ── Summarise (AI or passthrough) ────────────────────────
        sorted_articles = await summarise_batch(list(sorted_articles))

        # Ensure data directory exists
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Write cache
        FEED_CACHE_PATH.write_text(
            json.dumps(sorted_articles, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # ── Summary log ──────────────────────────────────────────
        new_articles = [a for a in sorted_articles if a["id"] not in existing_ids]

        # Dispatch async Web Push Events out to clients
        if new_articles:
            _dispatch_push_notifications(new_articles)

        total = len(sorted_articles)
        logger.info("Feed refresh complete:")
        logger.info("  NewsAPI : %d articles", newsapi_count)
        logger.info("  RSS     : %d articles", rss_count)
        logger.info("  Scraped : %d articles", scraped_count)
        logger.info("  Merged  : %d unique articles (deduped by URL hash)", total)

        # Log the first 4 articles for quick verification
        for i, article in enumerate(sorted_articles[:4], start=1):
            logger.info(
                "  #%d  [%s] %s — %s",
                i,
                article["category"].upper(),
                article["title"][:80],
                article["source"],
            )

        logger.info("═" * 60)

    except Exception as exc:
        logger.error("Feed refresh failed: %s", exc)
        logger.info("  NewsAPI: %d, RSS: %d, Scraped: %d", newsapi_count, rss_count, scraped_count)


def start_scheduler() -> None:
    """
    Start the background scheduler.

    Schedules ``refresh_feeds`` to run:
      1. Immediately on startup (via ``next_run_time`` trick)
      2. Then every ``FETCH_INTERVAL_MINUTES`` minutes
    """
    global _scheduler
    _scheduler = AsyncIOScheduler()

    # Adding with next_run_time=None first, then modifying, is the
    # cleanest APScheduler pattern for "run now + interval".
    # Instead we use a simpler approach: jitter=0 + misfire_grace.
    from datetime import datetime as _dt

    _scheduler.add_job(
        refresh_feeds,
        trigger=IntervalTrigger(minutes=FETCH_INTERVAL_MINUTES),
        id="feed_refresh",
        name="Refresh news feeds",
        replace_existing=True,
        next_run_time=_dt.now(),  # fire immediately on startup
        misfire_grace_time=60,
    )
    _scheduler.start()
    logger.info(
        "Scheduler started — first fetch NOW, then every %d minutes.",
        FETCH_INTERVAL_MINUTES,
    )


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
