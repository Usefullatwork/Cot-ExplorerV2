#!/usr/bin/env python3
"""
intel_feed.py - Google News RSS scraper for metals and geopolitics.

Fetches news headlines from Google News RSS across four categories
relevant to commodity trading: gold, silver, copper, and geopolitical
disruptions.

No API key required.
Zero external dependencies - stdlib only.
"""

import logging
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Optional

log = logging.getLogger(__name__)

CATEGORIES: dict[str, str] = {
    "gold": "gold+mines+OR+gold+price+OR+gold+production",
    "silver": "silver+mines+OR+silver+COMEX+OR+silver+production",
    "copper": "copper+supply+OR+copper+mines+OR+copper+shortage",
    "geopolitical": "geopolitical+disruption+OR+trade+sanctions+OR+shipping+blockade+OR+mining+strike",
}

# Color codes for frontend rendering
CATEGORY_COLORS: dict[str, str] = {
    "gold": "#FFD700",
    "silver": "#C0C0C0",
    "copper": "#B87333",
    "geopolitical": "#FF4444",
}

BASE_URL = "https://news.google.com/rss/search"
RATE_LIMIT_SECONDS = 2.0


def _fetch_category(category: str, query: str) -> list[dict]:
    """Fetch RSS articles for a single category."""
    url = f"{BASE_URL}?q={query}&hl=en-US&gl=US&ceid=US:en"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0",
            "Accept": "application/rss+xml, application/xml, text/xml",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            xml_data = r.read()
    except Exception as e:
        log.error(f"Intel feed {category} ERROR: {e}")
        return []

    articles: list[dict] = []
    try:
        root = ET.fromstring(xml_data)
        channel = root.find("channel")
        if channel is None:
            return articles

        for item in channel.findall("item"):
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            source_el = item.find("source")
            source = source_el.text if source_el is not None and source_el.text else "Unknown"

            articles.append({
                "title": title,
                "url": link,
                "source": source,
                "time": pub_date,
                "category": category,
                "color": CATEGORY_COLORS.get(category, "#888888"),
            })
    except ET.ParseError as e:
        log.error(f"Intel feed {category} XML parse ERROR: {e}")

    return articles


def fetch(max_per_category: int = 10) -> list[dict]:
    """
    Fetch news articles across all commodity/geopolitical categories.

    Args:
        max_per_category: Maximum articles per category (default 10).

    Returns:
        List of article dicts with: title, url, source, time,
        category, color.  Empty list on error.
    """
    all_articles: list[dict] = []

    for i, (category, query) in enumerate(CATEGORIES.items()):
        if i > 0:
            time.sleep(RATE_LIMIT_SECONDS)

        articles = _fetch_category(category, query)
        all_articles.extend(articles[:max_per_category])
        log.info(f"Intel feed {category}: {len(articles[:max_per_category])} articles")

    log.info(f"Intel feed total: {len(all_articles)} articles")
    return all_articles


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    results = fetch(max_per_category=3)
    for art in results:
        log.info(f"  [{art['category']}] {art['title'][:80]} — {art['source']}")
