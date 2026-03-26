"""Unit tests for competitor analyzer and scrapers."""

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
from src.competitor.scrapers.tradingview import (
    _guess_direction,
    _normalize_symbol,
    fetch_tv_ideas_rss,
)


# ===========================================================================
# check_signal_outcome
# ===========================================================================


class TestCheckSignalOutcome:
    """Signal outcome evaluation against price bars."""

    def test_pending_when_no_bars(self):
        """Empty price_data returns 'pending'."""
        sig = {"direction": "bull", "entry_price": 1.10, "stop_loss": 1.09, "target_1": 1.12}
        assert check_signal_outcome(sig, []) == "pending"

    def test_bull_t1_hit(self):
        """Bull signal reaches target_1."""
        sig = {"direction": "bull", "entry_price": 1.10, "stop_loss": 1.09, "target_1": 1.12}
        bars = [(1.11, 1.095, 1.105), (1.125, 1.10, 1.12)]
        assert check_signal_outcome(sig, bars) == "t1_hit"

    def test_bull_t2_hit(self):
        """Bull signal reaches target_2 (checked before t1)."""
        sig = {
            "direction": "bull",
            "entry_price": 1.10,
            "stop_loss": 1.09,
            "target_1": 1.12,
            "target_2": 1.15,
        }
        bars = [(1.16, 1.10, 1.15)]
        assert check_signal_outcome(sig, bars) == "t2_hit"

    def test_bull_stopped_out(self):
        """Bull signal hits stop loss."""
        sig = {"direction": "bull", "entry_price": 1.10, "stop_loss": 1.09, "target_1": 1.12}
        bars = [(1.105, 1.085, 1.09)]
        assert check_signal_outcome(sig, bars) == "stopped_out"

    def test_bear_t1_hit(self):
        """Bear signal reaches target_1 (low <= t1)."""
        sig = {"direction": "bear", "entry_price": 1.10, "stop_loss": 1.12, "target_1": 1.08}
        bars = [(1.10, 1.075, 1.08)]
        assert check_signal_outcome(sig, bars) == "t1_hit"

    def test_bear_stopped_out(self):
        """Bear signal hits stop loss (high >= sl)."""
        sig = {"direction": "bear", "entry_price": 1.10, "stop_loss": 1.12, "target_1": 1.08}
        bars = [(1.125, 1.095, 1.11)]
        assert check_signal_outcome(sig, bars) == "stopped_out"

    def test_expired_when_no_target_hit(self):
        """Bars exist but neither SL nor TP is touched."""
        sig = {"direction": "bull", "entry_price": 1.10, "stop_loss": 1.09, "target_1": 1.15}
        bars = [(1.11, 1.095, 1.10), (1.12, 1.10, 1.11)]
        assert check_signal_outcome(sig, bars) == "expired"

    def test_bear_t2_hit(self):
        """Bear signal reaches target_2."""
        sig = {
            "direction": "bear",
            "entry_price": 1.10,
            "stop_loss": 1.12,
            "target_1": 1.08,
            "target_2": 1.05,
        }
        bars = [(1.10, 1.04, 1.06)]
        assert check_signal_outcome(sig, bars) == "t2_hit"


# ===========================================================================
# log_signal + compute_accuracy (file I/O mocked)
# ===========================================================================


class TestLogSignalAndAccuracy:
    """Signal logging and accuracy computation with mocked file I/O."""

    def test_log_signal_appends(self, tmp_path, monkeypatch):
        """log_signal appends to signal_log.json on disk."""
        import src.competitor.analyzer as mod

        log_file = tmp_path / "signal_log.json"
        monkeypatch.setattr(mod, "_LOG_DIR", tmp_path)
        monkeypatch.setattr(mod, "_LOG_FILE", log_file)

        sig = {"instrument": "EURUSD", "direction": "bull", "entry_price": 1.10,
               "stop_loss": 1.09, "target_1": 1.12}
        log_signal(sig, timestamp="2026-01-01T00:00:00Z")

        data = json.loads(log_file.read_text())
        assert len(data) == 1
        assert data[0]["instrument"] == "EURUSD"
        assert data[0]["outcome"] == "pending"
        assert data[0]["timestamp"] == "2026-01-01T00:00:00Z"

    def test_compute_accuracy_basic(self, tmp_path, monkeypatch):
        """compute_accuracy returns correct win_rate and counts."""
        import src.competitor.analyzer as mod

        log_file = tmp_path / "signal_log.json"
        monkeypatch.setattr(mod, "_LOG_DIR", tmp_path)
        monkeypatch.setattr(mod, "_LOG_FILE", log_file)

        entries = [
            {"timestamp": "2026-03-25T00:00:00Z", "outcome": "t1_hit", "rr_t1": 2.0},
            {"timestamp": "2026-03-25T00:00:00Z", "outcome": "t2_hit", "rr_t1": 3.0},
            {"timestamp": "2026-03-25T00:00:00Z", "outcome": "stopped_out"},
            {"timestamp": "2026-03-25T00:00:00Z", "outcome": "pending"},
            {"timestamp": "2026-03-25T00:00:00Z", "outcome": "expired"},
        ]
        log_file.write_text(json.dumps(entries))

        result = compute_accuracy(days=90)
        assert result["total"] == 5
        assert result["wins"] == 2
        assert result["losses"] == 1
        assert result["pending"] == 1
        assert result["expired"] == 1
        # win_rate = 2 / (2+1) * 100 = 66.7
        assert result["win_rate"] == 66.7
        # avg_rr = (2.0+3.0)/2 = 2.5
        assert result["avg_rr"] == 2.5

    def test_compute_accuracy_empty_log(self, tmp_path, monkeypatch):
        """compute_accuracy with no log file returns zeroes."""
        import src.competitor.analyzer as mod

        log_file = tmp_path / "signal_log.json"
        monkeypatch.setattr(mod, "_LOG_DIR", tmp_path)
        monkeypatch.setattr(mod, "_LOG_FILE", log_file)

        result = compute_accuracy(days=90)
        assert result["total"] == 0
        assert result["win_rate"] == 0.0
        assert result["avg_rr"] == 0.0


# ===========================================================================
# Myfxbook scraper
# ===========================================================================


class TestMyfxbookScraper:
    """Myfxbook HTML parsing with mocked HTTP responses."""

    _MOCK_HTML = """
    <html><body><table>
    <tr><td><a href="/symbol/EURUSD">EURUSD</a></td>
    <td>72.3%</td><td>27.7%</td></tr>
    <tr><td><a href="/symbol/USDJPY">USDJPY</a></td>
    <td>55.1%</td><td>44.9%</td></tr>
    </table></body></html>
    """

    @patch("src.competitor.scrapers.myfxbook.urllib.request.urlopen")
    def test_parses_pairs(self, mock_urlopen):
        """Parses long/short percentages from mock HTML."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = self._MOCK_HTML.encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = fetch_myfxbook_outlook()
        assert "EURUSD" in result
        assert result["EURUSD"]["long_pct"] == 72.3
        assert result["EURUSD"]["short_pct"] == 27.7
        assert "USDJPY" in result
        assert result["USDJPY"]["long_pct"] == 55.1

    @patch("src.competitor.scrapers.myfxbook.urllib.request.urlopen", side_effect=Exception("timeout"))
    def test_returns_empty_on_failure(self, mock_urlopen):
        """Returns empty dict on network failure."""
        result = fetch_myfxbook_outlook()
        assert result == {}


# ===========================================================================
# TradingView scraper
# ===========================================================================


class TestTradingViewHelpers:
    """TradingView symbol normalization and direction guessing."""

    @pytest.mark.parametrize("raw,expected", [
        ("FX:EURUSD", "EURUSD"),
        ("OANDA:XAUUSD", "Gold"),
        ("TVC:DXY", "DXY"),
        ("SP:SPX", "SPX"),
    ])
    def test_normalize_known_symbols(self, raw, expected):
        assert _normalize_symbol(raw) == expected

    def test_normalize_unknown_short_ticker(self):
        """Unknown short ticker passes through as-is."""
        assert _normalize_symbol("AAPL") == "AAPL"

    def test_normalize_unknown_long_ticker_returns_none(self):
        """Unknown ticker >8 chars returns None."""
        assert _normalize_symbol("VERYLONGSYMBOL") is None

    @pytest.mark.parametrize("title,expected", [
        ("EURUSD - Long Setup", "bull"),
        ("Gold Bullish Breakout", "bull"),
        ("USDJPY Short Sell Signal", "bear"),
        ("Bearish Breakdown", "bear"),
        ("EURUSD Analysis", "neutral"),
    ])
    def test_guess_direction(self, title, expected):
        assert _guess_direction(title) == expected


class TestTradingViewRSS:
    """TradingView RSS feed parsing with mocked HTTP."""

    _MOCK_RSS = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
    <channel>
    <item>
        <title>EURUSD - Long Setup After Support Bounce</title>
        <link>https://www.tradingview.com/chart/EURUSD/abc123/</link>
        <category>FX:EURUSD</category>
    </item>
    <item>
        <title>Gold Bearish Breakdown Below Key Level</title>
        <link>https://www.tradingview.com/chart/XAUUSD/def456/</link>
        <category>OANDA:XAUUSD</category>
    </item>
    </channel>
    </rss>"""

    @patch("src.competitor.scrapers.tradingview.urllib.request.urlopen")
    def test_parses_rss_items(self, mock_urlopen):
        """Parses symbol, direction, title, url from RSS feed."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = self._MOCK_RSS.encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        ideas = fetch_tv_ideas_rss()
        assert len(ideas) == 2

        assert ideas[0]["symbol"] == "EURUSD"
        assert ideas[0]["direction"] == "bull"
        assert "Long Setup" in ideas[0]["title"]

        assert ideas[1]["symbol"] == "Gold"
        assert ideas[1]["direction"] == "bear"

    @patch("src.competitor.scrapers.tradingview.urllib.request.urlopen", side_effect=Exception("DNS failure"))
    def test_returns_empty_on_failure(self, mock_urlopen):
        """Returns empty list on network failure."""
        assert fetch_tv_ideas_rss() == []
