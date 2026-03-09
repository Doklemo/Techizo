"""
scraper.py
----------
Custom HTML web scraper for domains that do not natively expose XML RSS feeds.
Parses the DOM using BeautifulSoup4 and normalises payloads into the standard Article schema.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from fetcher.classifier import classify, generate_id

logger = logging.getLogger(__name__)

# Common browser headers to bypass basic anti-bot blocks
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}

IMPORTANT_KEYWORDS = [
    "model", "claude", "gpt", "release", "update", "announce", "api", 
    "breakthrough", "opus", "sonnet", "o1", "o3", "sora", "gemini", 
    "research", "training", "compute", "alignment"
]


def _clean_text(text: str | None) -> str:
    if not text:
        return ""
    # Strip excessive whitespace and newlines
    return " ".join(text.split()).strip()


def _is_important_ai_news(title: str) -> bool:
    """
    Heuristic filter checking if an article title contains high-signal AI keywords.
    Forces the scraper to drop trivial or corporate news.
    """
    title_lower = title.lower()
    return any(re.search(r'\b' + kw + r'\b', title_lower) for kw in IMPORTANT_KEYWORDS)


def _extract_date(raw_text: str) -> str | None:
    """
    Extracts explicit US-formatted publication dates (e.g. 'Feb 25, 2026') 
    from raw DOM text and normalises to ISO 8601 UTC string for sorting integration.
    """
    import re
    from datetime import datetime
    
    match = re.search(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}, \d{4}', raw_text, re.IGNORECASE)
    if not match:
        return None
        
    date_str = match.group(0)
    try:
        # Standardize strings like 'February 4, 2026' or 'Feb 4, 2026'
        dt = datetime.strptime(date_str[:3] + date_str[date_str.find(" "):], "%b %d, %Y")
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except Exception as exc:
        logger.debug(f"Regex Date extraction failed conversion for '{date_str}': {exc}")
        return None


async def _fetch_meta_details(client: httpx.AsyncClient, url: str) -> tuple[str, str | None]:
    """
    Fires a secondary concurrent request into the target article URL explicitly
    to rip the author's <meta name="description"> and <meta property="og:image">.
    """
    try:
        resp = await client.get(url, headers=HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Rip Description
        summary = ""
        meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
        if meta_desc and meta_desc.get("content"):
            summary = _clean_text(meta_desc["content"])
            
        # Rip Image
        image_url = None
        meta_img = soup.find("meta", attrs={"property": "og:image"})
        if meta_img and meta_img.get("content"):
            image_url = meta_img["content"]
            
        return summary, image_url
    except Exception as exc:
        logger.warning(f"Could not fetch metadata for {url}: {exc}")
        return "", None


async def _scrape_anthropic(client: httpx.AsyncClient) -> list[dict]:
    """Scrapes https://www.anthropic.com/news"""
    url = "https://www.anthropic.com/news"
    articles: list[dict] = []
    try:
        resp = await client.get(url, headers=HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Anthropic lists their news in <a> tags starting with /news/
        links = soup.find_all("a", href=True)
        seen_urls = set()

        for a in links:
            href = a["href"]
            if href.startswith("/news/") and len(href) > 7:
                full_url = f"https://www.anthropic.com{href}"
                if full_url in seen_urls:
                    continue

                title_element = a.find(lambda t: t.name in ['h1','h2','h3','h4','h5','h6'] or (t.has_attr('class') and any('title' in c.lower() for c in t['class'])))
                if title_element:
                    title = _clean_text(title_element.get_text(separator=" "))
                else:
                    title = _clean_text(a.get_text(separator=" "))
                    
                if len(title) < 10:
                    continue
                    
                seen_urls.add(full_url)
                
                # Active Signal Filter
                if not _is_important_ai_news(title):
                    logger.debug(f"Filter DROPPED typical news: {title}")
                    continue

                # Pass 2: Deep Link Crawl
                summary, image_url = await _fetch_meta_details(client, full_url)
                
                category = classify(title, summary)
                if category == "technology":
                    category = "ai"  # Fallback override for Anthropic
                
                raw_text = a.get_text(separator=" ")
                published_time = _extract_date(raw_text)
                if not published_time:
                    published_time = datetime.now(timezone.utc).isoformat()

                articles.append({
                    "id": generate_id(full_url),
                    "title": title,
                    "summary": summary,
                    "source": "Anthropic",
                    "url": full_url,
                    "category": category,
                    "publishedAt": published_time,
                    "imageUrl": image_url
                })
                
                # Only take the 5 most recent profound models to prevent long scraper hangs
                if len(articles) >= 5:
                    break
        
        logger.info("Scraper 'Anthropic' evaluated and returned %d high-signal articles.", len(articles))
    except Exception as exc:
        logger.error("Scraper failed for %s: %s", url, exc)
        
    return articles


async def _scrape_openai(client: httpx.AsyncClient) -> list[dict]:
    """Scrapes https://openai.com/news"""
    url = "https://openai.com/news"
    articles: list[dict] = []
    try:
        resp = await client.get(url, headers=HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        links = soup.find_all("a", href=True)
        seen_urls = set()

        for a in links:
            href = a["href"]
            if (href.startswith("/news/") or href.startswith("/research/")) and len(href) > 10:
                full_url = f"https://openai.com{href}"
                if full_url in seen_urls:
                    continue

                title_element = a.find(lambda t: t.name in ['h1','h2','h3','h4','h5','h6'] or (t.has_attr('class') and any('title' in c.lower() for c in t['class'])))
                if title_element:
                    title = _clean_text(title_element.get_text(separator=" "))
                else:
                    title = _clean_text(a.get_text(separator=" "))
                    
                if len(title) < 10:
                    continue

                seen_urls.add(full_url)
                
                # Active Signal Filter
                if not _is_important_ai_news(title):
                    logger.debug(f"Filter DROPPED typical news: {title}")
                    continue

                # Pass 2: Deep Link Crawl
                summary, image_url = await _fetch_meta_details(client, full_url)
                
                category = classify(title, summary)
                if category == "technology":
                    category = "ai"
                
                raw_text = a.get_text(separator=" ")
                published_time = _extract_date(raw_text)
                if not published_time:
                    published_time = datetime.now(timezone.utc).isoformat()

                articles.append({
                    "id": generate_id(full_url),
                    "title": title,
                    "summary": summary,
                    "source": "OpenAI",
                    "url": full_url,
                    "category": category,
                    "publishedAt": published_time,
                    "imageUrl": image_url
                })
                
                if len(articles) >= 5:
                    break
        
        logger.info("Scraper 'OpenAI' evaluated and returned %d high-signal articles.", len(articles))
    except Exception as exc:
        logger.error("Scraper failed for %s: %s", url, exc)
        
    return articles


async def fetch_scraped() -> list[dict]:
    """
    Executes all configured HTML scrapers concurrently.
    Returns a unified, deduped list of article objects.
    """
    logger.info("Initiating concurrent HTML scrapes (OpenAI, Anthropic)…")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            results = await asyncio.gather(
                _scrape_openai(client),
                _scrape_anthropic(client),
                return_exceptions=True
            )
            
        seen = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error("Scraper gathered exception: %s", result)
                continue
            for article in result:
                seen[article["id"]] = article
                
        merged = list(seen.values())
        logger.info("Scraper total: %d distinct scraped high-signal articles.", len(merged))
        return merged
        
    except Exception as exc:
        logger.error("fetch_scraped() failed entirely: %s", exc)
        return []
