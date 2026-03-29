"""Unit tests for src.trading.scrapers.intel_feed — Google News RSS scraper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.trading.scrapers.intel_feed import (
    CATEGORIES,
    CATEGORY_COLORS,
    _fetch_category,
    fetch,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rss_xml(items: list[dict]) -> bytes:
    """Build a minimal RSS XML response."""
    items_xml = ""
    for item in items:
        source_tag = ""
        if item.get("source"):
            source_tag = f"<source>{item['source']}</source>"
        items_xml += f"""<item>
            <title>{item.get('title', '')}</title>
            <link>{item.get('link', '')}</link>
            <pubDate>{item.get('pubDate', '')}</pubDate>
            {source_tag}
        </item>"""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <title>Test Feed</title>
            {items_xml}
        </channel>
    </rss>""".encode()


# ===== _fetch_category =====================================================


class TestFetchCategory:
    """RSS XML parsing for a single category."""

    @patch("src.trading.scrapers.intel_feed.urllib.request.urlopen")
    def test_parses_rss_items(self, mock_urlopen):
        """Parses title, link, pubDate, source from RSS items."""
        xml = _make_rss_xml([
            {"title": "Gold hits record high", "link": "https://example.com/1",
             "pubDate": "Mon, 27 Mar 2026 10:00:00 GMT", "source": "Reuters"},
            {"title": "Silver supply shrinks", "link": "https://example.com/2",
             "pubDate": "Mon, 27 Mar 2026 09:00:00 GMT", "source": "Bloomberg"},
        ])
        ctx = MagicMock()
        ctx.__enter__ = lambda s: MagicMock(read=lambda: xml)
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        articles = _fetch_category("gold", "gold+price")
        assert len(articles) == 2
        assert articles[0]["title"] == "Gold hits record high"
        assert articles[0]["url"] == "https://example.com/1"
        assert articles[0]["source"] == "Reuters"
        assert articles[0]["category"] == "gold"
        assert articles[0]["color"] == CATEGORY_COLORS["gold"]

    @patch("src.trading.scrapers.intel_feed.urllib.request.urlopen")
    def test_empty_rss_returns_empty_list(self, mock_urlopen):
        """RSS with no items returns empty list."""
        xml = _make_rss_xml([])
        ctx = MagicMock()
        ctx.__enter__ = lambda s: MagicMock(read=lambda: xml)
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        articles = _fetch_category("silver", "silver+price")
        assert articles == []

    @patch("src.trading.scrapers.intel_feed.urllib.request.urlopen")
    def test_malformed_xml_returns_empty_list(self, mock_urlopen):
        """Malformed XML does not raise; returns empty list."""
        ctx = MagicMock()
        ctx.__enter__ = lambda s: MagicMock(read=lambda: b"<not valid xml")
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        articles = _fetch_category("copper", "copper+supply")
        assert articles == []

    @patch("src.trading.scrapers.intel_feed.urllib.request.urlopen")
    def test_network_error_returns_empty_list(self, mock_urlopen):
        """Network error returns empty list without raising."""
        mock_urlopen.side_effect = ConnectionError("timeout")

        articles = _fetch_category("gold", "gold+price")
        assert articles == []

    @patch("src.trading.scrapers.intel_feed.urllib.request.urlopen")
    def test_missing_source_defaults_to_unknown(self, mock_urlopen):
        """Missing <source> element defaults to 'Unknown'."""
        xml = _make_rss_xml([
            {"title": "Test Article", "link": "https://example.com/3", "pubDate": ""},
        ])
        ctx = MagicMock()
        ctx.__enter__ = lambda s: MagicMock(read=lambda: xml)
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        articles = _fetch_category("geopolitical", "sanctions")
        assert len(articles) == 1
        assert articles[0]["source"] == "Unknown"
        assert articles[0]["category"] == "geopolitical"


# ===== fetch() =============================================================


class TestFetch:
    """Full fetch across all categories."""

    @patch("src.trading.scrapers.intel_feed._fetch_category")
    @patch("src.trading.scrapers.intel_feed.time.sleep")
    def test_fetches_all_categories(self, mock_sleep, mock_fetch_cat):
        """Calls _fetch_category for each category and concatenates results."""
        mock_fetch_cat.return_value = [
            {"title": "T1", "url": "u1", "source": "S", "time": "", "category": "gold", "color": "#FFD700"},
        ]

        articles = fetch(max_per_category=10)
        assert mock_fetch_cat.call_count == len(CATEGORIES)
        assert len(articles) == len(CATEGORIES)  # 1 per category

    @patch("src.trading.scrapers.intel_feed._fetch_category")
    @patch("src.trading.scrapers.intel_feed.time.sleep")
    def test_respects_max_per_category(self, mock_sleep, mock_fetch_cat):
        """Only max_per_category articles per category are included."""
        mock_fetch_cat.return_value = [
            {"title": f"Art{i}", "url": "", "source": "", "time": "", "category": "gold", "color": ""}
            for i in range(20)
        ]

        articles = fetch(max_per_category=5)
        # 4 categories * 5 max = 20
        assert len(articles) == 4 * 5

    @patch("src.trading.scrapers.intel_feed._fetch_category")
    @patch("src.trading.scrapers.intel_feed.time.sleep")
    def test_rate_limiting_sleeps_between_categories(self, mock_sleep, mock_fetch_cat):
        """Rate-limits by sleeping between category fetches (not before first)."""
        mock_fetch_cat.return_value = []

        fetch()
        # Sleep is called between categories (not before the first one)
        assert mock_sleep.call_count == len(CATEGORIES) - 1
