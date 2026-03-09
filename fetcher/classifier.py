"""
classifier.py
--------------
Shared category classifier used by both newsapi.py and rss.py.
Checks title text against keyword lists to assign one of:
  'ai', 'robotics', or 'technology' (fallback).
"""

import hashlib
from typing import Literal

# ── Category keyword maps ────────────────────────────────────────────
# Checked in order: first match wins. 'technology' is the default fallback.
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "ai": [
        "ai",
        "artificial intelligence",
        "machine learning",
        "llm",
        "openai",
        "anthropic",
        "deepmind",
        "model",
        "neural",
    ],
    "robotics": [
        "robot",
        "robotics",
        "drone",
        "automation",
        "actuator",
    ],
}

Category = Literal["ai", "robotics", "technology"]


def classify(title: str, description: str = "") -> Category:
    """
    Assign a category by scanning *title* (and optionally *description*)
    for known keywords.

    Args:
        title: Article headline — primary signal.
        description: Optional body/summary text for additional context.

    Returns:
        One of 'ai', 'robotics', or 'technology'.
    """
    text = f"{title} {description}".lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category  # type: ignore[return-value]
    return "technology"


def generate_id(url: str) -> str:
    """Create a deterministic 12-char article ID by hashing its URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:12]
