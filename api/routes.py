"""
routes.py
---------
API endpoints for the Pulse feed.
All reads are wrapped in try/except — a failed cache read never crashes the server.
"""

import json
import logging
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from config import FEED_CACHE_PATH

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["feed"])


def _read_cache() -> list[dict]:
    """
    Read the feed cache from disk.

    Returns an empty list if the file doesn't exist or is malformed.
    """
    try:
        if FEED_CACHE_PATH.exists():
            data = json.loads(FEED_CACHE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
    except Exception as exc:
        logger.error("Failed to read feed cache: %s", exc)
    return []


@router.get("/feed")
async def get_feed() -> JSONResponse:
    """Return all cached articles as a JSON array."""
    try:
        articles = _read_cache()
        return JSONResponse(content=articles)
    except Exception as exc:
        logger.error("GET /api/feed error: %s", exc)
        return JSONResponse(content=[], status_code=500)


@router.get("/feed/{category}")
async def get_feed_by_category(
    category: Literal["ai", "technology", "robotics"],
) -> JSONResponse:
    """
    Return cached articles filtered by category.

    Path parameter must be one of: ai, technology, robotics.
    """
    try:
        articles = _read_cache()
        filtered = [a for a in articles if a.get("category") == category]
        return JSONResponse(content=filtered)
    except Exception as exc:
        logger.error("GET /api/feed/%s error: %s", category, exc)
        return JSONResponse(content=[], status_code=500)


@router.post("/refresh")
async def refresh_feed(background_tasks: BackgroundTasks) -> JSONResponse:
    """
    Trigger an immediate feed refresh in the background.

    Returns immediately with a status message; the actual fetch
    runs asynchronously so the client isn't blocked.
    """
    try:
        from fetcher.scheduler import refresh_feeds

        background_tasks.add_task(refresh_feeds)
        return JSONResponse(content={"status": "refreshing"})
    except Exception as exc:
        logger.error("POST /api/refresh error: %s", exc)
        raise HTTPException(status_code=500, detail="Refresh failed") from exc

# ── Push Subscriptions ───────────────────────────────────────────────

class PushKeys(BaseModel):
    p256dh: str
    auth: str

class PushSubscription(BaseModel):
    endpoint: str
    expirationTime: Optional[int | float | str] = None
    keys: PushKeys

@router.post("/subscribe")
async def subscribe(sub: PushSubscription) -> JSONResponse:
    """Register a new Service Worker push subscription."""
    try:
        from config import SUBSCRIPTIONS_FILE
        subs = []
        if SUBSCRIPTIONS_FILE.exists():
            subs = json.loads(SUBSCRIPTIONS_FILE.read_text(encoding="utf-8"))
            
        sub_dict = sub.model_dump()
        if not any(s.get("endpoint") == sub_dict["endpoint"] for s in subs):
            subs.append(sub_dict)
            SUBSCRIPTIONS_FILE.write_text(json.dumps(subs), encoding="utf-8")
            
        return JSONResponse(content={"status": "subscribed"})
    except Exception as exc:
        logger.error("POST /api/subscribe error: %s", exc)
        return JSONResponse(content={"error": str(exc)}, status_code=500)
