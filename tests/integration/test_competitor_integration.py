"""Integration tests for the competitor analysis pipeline.

Tests the full flow: scrape competitor signals (mocked HTML/RSS) ->
log signals -> evaluate outcomes -> compute accuracy stats.
All external HTTP calls are mocked.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.competitor.analyzer import (
    check_signal_outcome,
    compute_accuracy,
    log_signal,
)
from src.competitor.scrapers.myfxbook import fetch_myfxbook_outlook
from src.competitor.scrapers.tradingview import fetch_tv_ideas_rss

# ---------------------------------------------------------------------------
# Mock HTML / RSS payloads
# ---------------------------------------------------------------------------

MYFXBOOK_HTML = """
<html><body><table class="outlook">
<tr><td><a href="/sym/EURUSD">EURUSD</a></td>
<td>65.2%</td><td>34.8%</td></tr>
<tr><td><a href="/sym/USDJPY">USDJPY</a></td>
<td>48.5%</td><td>51.5%</td></tr>
<tr><td><a href="/sym/GBPUSD">GBPUSD</a></td>
<td>72.0%</td><td>28.0%</td></tr>
</table></body></html>
"""

TRADINGVIEW_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<item>
    <title>EURUSD - Long Setup: Bullish Breakout</title>
    <link>https://www.tradingview.com/chart/EURUSD/abc/</link>
    <category>FX:EURUSD</category>
</item>
<item>
    <title>Gold Bearish Breakdown Below Support</title>
    <link>https://www.tradingview.com/chart/XAUUSD/def/</link>
    <category>OANDA:XAUUSD</category>
</item>
<item>
    <title>SPX Analysis - Neutral Range Bound</title>
    <link>https://www.tradingview.com/chart/SPX/ghi/</link>
    <category>SP:SPX</category>
</item>
</channel>
</rss>"""


def _mock_http_response(content: str | bytes):
    """Return a mock urlopen context manager returning given content."""
    if isinstance(content, str):
        content = content.encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = content
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ===========================================================================
# Myfxbook scraper integration
# ===========================================================================


class TestMyfxbookPipeline:
    """Myfxbook HTML scraping and sentiment extraction."""

    @patch("src.competitor.scrapers.myfxbook.urllib.request.urlopen")
    def test_parses_multiple_pairs(self, mock_urlopen):
        """Extracts long/short percentages for all pairs in the HTML."""
        mock_urlopen.return_value = _mock_http_response(MYFXBOOK_HTML)

        result = fetch_myfxbook_outlook()

        assert len(result) >= 2
        assert "EURUSD" in result
        assert result["EURUSD"]["long_pct"] == 65.2
        assert result["EURUSD"]["short_pct"] == 34.8
        assert "USDJPY" in result
        assert result["USDJPY"]["short_pct"] == 51.5

    @patch("src.competitor.scrapers.myfxbook.urllib.request.urlopen")
    def test_sentiment_interpretation(self, mock_urlopen):
        """Majority long_pct > 50 implies retail is long (contrarian bearish)."""
        mock_urlopen.return_value = _mock_http_response(MYFXBOOK_HTML)

        result = fetch_myfxbook_outlook()

        # EURUSD: 65.2% long => retail crowded long
        assert result["EURUSD"]["long_pct"] > 50
        # USDJPY: 48.5% long => retail slightly short-biased
        assert result["USDJPY"]["long_pct"] < 50

    @patch("src.competitor.scrapers.myfxbook.urllib.request.urlopen", side_effect=Exception("network error"))
    def test_graceful_failure(self, mock_urlopen):
        """Network failure returns empty dict, no exception raised."""
        result = fetch_myfxbook_outlook()
        assert result == {}

    @patch("src.competitor.scrapers.myfxbook.urllib.request.urlopen")
    def test_empty_html_returns_empty(self, mock_urlopen):
        """Empty or malformed HTML returns empty dict."""
        mock_urlopen.return_value = _mock_http_response("<html></html>")
        result = fetch_myfxbook_outlook()
        assert result == {}


# ===========================================================================
# TradingView RSS integration
# ===========================================================================


class TestTradingViewPipeline:
    """TradingView RSS parsing and idea extraction."""

    @patch("src.competitor.scrapers.tradingview.urllib.request.urlopen")
    def test_parses_ideas_from_rss(self, mock_urlopen):
        """Extracts symbol, direction, and title from RSS items."""
        mock_urlopen.return_value = _mock_http_response(TRADINGVIEW_RSS)

        ideas = fetch_tv_ideas_rss()

        assert len(ideas) == 3
        assert ideas[0]["symbol"] == "EURUSD"
        assert ideas[0]["direction"] == "bull"
        assert ideas[1]["symbol"] == "Gold"
        assert ideas[1]["direction"] == "bear"
        assert ideas[2]["symbol"] == "SPX"

    @patch("src.competitor.scrapers.tradingview.urllib.request.urlopen")
    def test_direction_guessing_accuracy(self, mock_urlopen):
        """Verify direction is correctly inferred from title keywords."""
        mock_urlopen.return_value = _mock_http_response(TRADINGVIEW_RSS)

        ideas = fetch_tv_ideas_rss()

        # "Long Setup: Bullish Breakout" => bull
        assert ideas[0]["direction"] == "bull"
        # "Bearish Breakdown Below Support" => bear
        assert ideas[1]["direction"] == "bear"
        # "Neutral Range Bound" => neutral (no strong keywords)
        assert ideas[2]["direction"] == "neutral"

    @patch("src.competitor.scrapers.tradingview.urllib.request.urlopen", side_effect=Exception("DNS failure"))
    def test_rss_failure_returns_empty(self, mock_urlopen):
        """RSS fetch failure returns empty list."""
        assert fetch_tv_ideas_rss() == []


# ===========================================================================
# Signal logging + outcome pipeline
# ===========================================================================


class TestSignalLogPipeline:
    """Full pipeline: log signal -> check outcome -> compute accuracy."""

    @pytest.fixture(autouse=True)
    def _mock_log_dir(self, tmp_path, monkeypatch):
        """Redirect signal log to a temporary directory."""
        import src.competitor.analyzer as mod

        self._log_file = tmp_path / "signal_log.json"
        monkeypatch.setattr(mod, "_LOG_DIR", tmp_path)
        monkeypatch.setattr(mod, "_LOG_FILE", self._log_file)

    def test_log_and_check_bull_t1_hit(self):
        """Log a bullish signal, check outcome with favorable bars."""
        sig = {
            "instrument": "EURUSD",
            "direction": "bull",
            "entry_price": 1.0800,
            "stop_loss": 1.0750,
            "target_1": 1.0900,
        }
        log_signal(sig, timestamp="2026-03-25T10:00:00Z")

        # Verify it was logged
        data = json.loads(self._log_file.read_text())
        assert len(data) == 1
        assert data[0]["outcome"] == "pending"

        # Check outcome
        bars = [(1.085, 1.078, 1.082), (1.095, 1.083, 1.091)]
        outcome = check_signal_outcome(sig, bars)
        assert outcome == "t1_hit"

    def test_log_and_check_bear_stopped_out(self):
        """Log a bearish signal that gets stopped out."""
        sig = {
            "instrument": "GOLD",
            "direction": "bear",
            "entry_price": 2000.0,
            "stop_loss": 2050.0,
            "target_1": 1950.0,
        }
        log_signal(sig, timestamp="2026-03-25T11:00:00Z")

        bars = [(2060.0, 1990.0, 2020.0)]  # high hits SL
        outcome = check_signal_outcome(sig, bars)
        assert outcome == "stopped_out"

    def test_full_accuracy_computation(self):
        """Log multiple signals with known outcomes, compute accuracy."""
        signals_and_outcomes = [
            (
                {
                    "instrument": "EURUSD",
                    "direction": "bull",
                    "entry_price": 1.08,
                    "stop_loss": 1.07,
                    "target_1": 1.10,
                    "rr_t1": 2.0,
                },
                "t1_hit",
            ),
            (
                {
                    "instrument": "GOLD",
                    "direction": "bull",
                    "entry_price": 2000,
                    "stop_loss": 1950,
                    "target_1": 2100,
                    "rr_t1": 2.0,
                },
                "t1_hit",
            ),
            (
                {"instrument": "USDJPY", "direction": "bear", "entry_price": 150, "stop_loss": 152, "target_1": 148},
                "stopped_out",
            ),
            (
                {"instrument": "GBPUSD", "direction": "bull", "entry_price": 1.26, "stop_loss": 1.25, "target_1": 1.28},
                "expired",
            ),
        ]

        # Log all signals
        for sig, _ in signals_and_outcomes:
            log_signal(sig, timestamp="2026-03-25T12:00:00Z")

        # Manually update outcomes in the log file
        data = json.loads(self._log_file.read_text())
        for i, (_, outcome) in enumerate(signals_and_outcomes):
            data[i]["outcome"] = outcome
        self._log_file.write_text(json.dumps(data))

        result = compute_accuracy(days=90)

        assert result["total"] == 4
        assert result["wins"] == 2
        assert result["losses"] == 1
        assert result["expired"] == 1
        # win_rate = 2 / (2+1) * 100 = 66.7
        assert result["win_rate"] == 66.7
        # avg_rr = (2.0+2.0)/2 = 2.0
        assert result["avg_rr"] == 2.0

    def test_multiple_log_entries_accumulate(self):
        """Multiple log_signal calls accumulate entries in the file."""
        for i in range(5):
            log_signal(
                {
                    "instrument": f"INST{i}",
                    "direction": "bull",
                    "entry_price": 100 + i,
                    "stop_loss": 95 + i,
                    "target_1": 110 + i,
                },
                timestamp=f"2026-03-25T{10 + i:02d}:00:00Z",
            )

        data = json.loads(self._log_file.read_text())
        assert len(data) == 5
        instruments = [e["instrument"] for e in data]
        assert instruments == [f"INST{i}" for i in range(5)]


# ===========================================================================
# Combined scrape + log + evaluate pipeline
# ===========================================================================


class TestEndToEndCompetitorPipeline:
    """Scrape competitor ideas, log as signals, evaluate outcomes."""

    @pytest.fixture(autouse=True)
    def _mock_log_dir(self, tmp_path, monkeypatch):
        import src.competitor.analyzer as mod

        self._log_file = tmp_path / "signal_log.json"
        monkeypatch.setattr(mod, "_LOG_DIR", tmp_path)
        monkeypatch.setattr(mod, "_LOG_FILE", self._log_file)

    @patch("src.competitor.scrapers.tradingview.urllib.request.urlopen")
    def test_scrape_log_evaluate(self, mock_urlopen):
        """Scrape TV ideas -> convert to signals -> log -> evaluate outcomes."""
        mock_urlopen.return_value = _mock_http_response(TRADINGVIEW_RSS)

        ideas = fetch_tv_ideas_rss()
        assert len(ideas) >= 2

        # Convert the first idea to a signal and log it
        idea = ideas[0]  # EURUSD bull
        sig = {
            "instrument": idea["symbol"],
            "direction": idea["direction"],
            "entry_price": 1.0850,
            "stop_loss": 1.0800,
            "target_1": 1.0950,
        }
        log_signal(sig, timestamp="2026-03-25T14:00:00Z")

        # Simulate price bars after the signal
        bars = [(1.090, 1.083, 1.088), (1.098, 1.087, 1.096)]
        outcome = check_signal_outcome(sig, bars)

        assert outcome == "t1_hit"
        assert sig["instrument"] == "EURUSD"
