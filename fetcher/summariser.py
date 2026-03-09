"""
summariser.py
-------------
Generate concise article summaries using Anthropic Claude.

When ``SUMMARISE_WITH_AI`` is **True**, each article's title + description
is sent to Claude for a 2-3 sentence rewrite. A semaphore-based rate
limiter caps concurrency at 5 simultaneous Claude requests.

When ``SUMMARISE_WITH_AI`` is **False** (default), the article's original
source description is preserved untouched.
"""

import asyncio
import logging

import anthropic

from config import ANTHROPIC_API_KEY, SUMMARISE_WITH_AI

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────
_MODEL = "claude-sonnet-4-20250514"
_MAX_TOKENS = 120
_MAX_CONCURRENT = 5  # max parallel Claude requests (rate limiter)

_SYSTEM_PROMPT = (
    "You summarise tech news for a busy professional. "
    "Write exactly 2-3 sentences. Be factual, clear, and jargon-free. "
    "Do not start with 'The article' or 'This article'."
)


async def _summarise_one(
    client: anthropic.AsyncAnthropic,
    semaphore: asyncio.Semaphore,
    article: dict,
) -> dict:
    """
    Summarise a single article via Claude, respecting the rate limiter.

    On success the article's ``summary`` field is replaced with the AI
    summary. On failure the original description is kept and the error
    is logged.

    Args:
        client: Shared async Anthropic client.
        semaphore: Concurrency limiter.
        article: Mutable article dict (modified in-place).

    Returns:
        The same article dict (mutated).
    """
    title = article.get("title", "")
    description = article.get("summary", "")

    async with semaphore:
        try:
            message = await client.messages.create(
                model=_MODEL,
                max_tokens=_MAX_TOKENS,
                system=_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Summarise this news story: {title}\n\n"
                            f"{description}"
                        ),
                    }
                ],
            )

            ai_summary = message.content[0].text.strip()
            if ai_summary:
                article["summary"] = ai_summary
                logger.info(
                    "✓ Summarised: %s (%d chars)",
                    title[:60],
                    len(ai_summary),
                )
            else:
                logger.warning(
                    "⚠ Empty summary from Claude for: %s — keeping original.",
                    title[:60],
                )

        except Exception as exc:
            # Fallback: keep the original source description
            logger.error(
                "✗ Claude failed for '%s': %s — keeping original summary.",
                title[:60],
                exc,
            )

    return article


async def summarise_batch(articles: list[dict]) -> list[dict]:
    """
    Summarise a batch of articles.

    If ``SUMMARISE_WITH_AI`` is False or the API key is missing, articles
    are returned immediately with their original summaries.

    Otherwise, all articles are summarised concurrently (capped at
    ``_MAX_CONCURRENT`` parallel requests).

    Args:
        articles: List of article dicts. Each must have at least
                  ``title`` and ``summary`` keys.

    Returns:
        The same list with ``summary`` fields potentially updated.
    """
    if not SUMMARISE_WITH_AI:
        logger.info("SUMMARISE_WITH_AI=false — using original descriptions.")
        return articles

    if not ANTHROPIC_API_KEY:
        logger.warning(
            "SUMMARISE_WITH_AI=true but ANTHROPIC_API_KEY not set — "
            "falling back to original descriptions."
        )
        return articles

    logger.info(
        "Summarising %d articles with Claude (max %d concurrent)…",
        len(articles),
        _MAX_CONCURRENT,
    )

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT)

    try:
        await asyncio.gather(
            *[_summarise_one(client, semaphore, a) for a in articles],
            return_exceptions=True,
        )
    except Exception as exc:
        logger.error("summarise_batch() failed: %s", exc)

    # Count successes/failures for the log
    logger.info("Summarisation complete for %d articles.", len(articles))
    return articles
