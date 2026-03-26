"""Integration tests for signal publishing pipeline.

Tests the full dispatch flow: format signal -> send to Telegram, Discord,
and JSON file. All external HTTP calls are mocked.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.publishers.discord import send_discord
from src.publishers.json_file import publish_static_json
from src.publishers.telegram import format_signal, send_telegram


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signal(**overrides) -> dict:
    """Return a complete signal dict with sensible defaults."""
    base = {
        "instrument": "EURUSD",
        "name": "EUR/USD",
        "direction": "bull",
        "timeframe_bias": "SWING",
        "grade": "A",
        "score": 10,
        "vix_regime": "LOW",
        "pos_size": "FULL",
        "entry_price": 1.0850,
        "stop_loss": 1.0800,
        "sl_type": "ATR",
        "target_1": 1.0950,
        "target_2": 1.1050,
        "rr_t1": 2.0,
        "rr_t2": 4.0,
    }
    base.update(overrides)
    return base


def _mock_urlopen_success():
    """Return a mock urlopen context manager that simulates HTTP 200."""
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=MagicMock(status=200))
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


# ===========================================================================
# Telegram integration
# ===========================================================================


class TestTelegramIntegration:
    """Format + send to Telegram in one flow."""

    @patch("src.publishers.telegram.urllib.request.urlopen")
    def test_format_and_send_bull_signal(self, mock_urlopen):
        """Format a bullish signal and send it via Telegram."""
        mock_urlopen.return_value = _mock_urlopen_success()

        sig = _make_signal(direction="bull")
        message = format_signal(sig)
        result = send_telegram(message, token="test-token", chat_id="12345")

        assert result is True
        assert "LONG" in message
        assert "EUR/USD" in message

        # Verify the HTTP payload
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode())
        assert body["parse_mode"] == "HTML"
        assert body["chat_id"] == "12345"
        assert "LONG" in body["text"]

    @patch("src.publishers.telegram.urllib.request.urlopen")
    def test_format_and_send_bear_signal(self, mock_urlopen):
        """Format a bearish signal and send it via Telegram."""
        mock_urlopen.return_value = _mock_urlopen_success()

        sig = _make_signal(direction="bear")
        message = format_signal(sig)
        result = send_telegram(message, token="tok", chat_id="99")

        assert result is True
        assert "SHORT" in message

    def test_missing_credentials_returns_false(self):
        """If token or chat_id is missing, send returns False without HTTP call."""
        with patch.dict("os.environ", {}, clear=True):
            assert send_telegram("msg", token="", chat_id="") is False
            assert send_telegram("msg", token="tok", chat_id="") is False
            assert send_telegram("msg", token="", chat_id="id") is False

    @patch("src.publishers.telegram.urllib.request.urlopen")
    def test_network_error_returns_false(self, mock_urlopen):
        """URLError during send returns False."""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")

        result = send_telegram("test", token="tok", chat_id="123")
        assert result is False


# ===========================================================================
# Discord integration
# ===========================================================================


class TestDiscordIntegration:
    """Format + send to Discord webhook in one flow."""

    @patch("src.publishers.discord.urllib.request.urlopen")
    def test_format_and_send_to_discord(self, mock_urlopen):
        """Format a signal and send it to Discord."""
        mock_urlopen.return_value = _mock_urlopen_success()

        sig = _make_signal()
        message = format_signal(sig)
        result = send_discord(message, webhook_url="https://discord.com/api/webhooks/test")

        assert result is True

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode())
        assert "content" in body
        # Discord wraps in code block
        assert "```" in body["content"]
        assert "LONG" in body["content"]

    def test_missing_webhook_returns_false(self):
        """If no webhook URL, send returns False without HTTP call."""
        with patch.dict("os.environ", {}, clear=True):
            assert send_discord("msg", webhook_url="") is False

    @patch("src.publishers.discord.urllib.request.urlopen")
    def test_discord_env_fallback(self, mock_urlopen):
        """Discord reads DISCORD_WEBHOOK from env when no arg is given."""
        mock_urlopen.return_value = _mock_urlopen_success()

        with patch.dict("os.environ", {"DISCORD_WEBHOOK": "https://hooks.discord.com/test"}):
            result = send_discord("hello")

        assert result is True


# ===========================================================================
# JSON file publishing
# ===========================================================================


class TestJsonFilePublishing:
    """Publish macro data to a static JSON file on disk."""

    def test_publish_creates_latest_json(self, tmp_path):
        """publish_static_json writes latest.json in the output directory."""
        macro = {"date": "2025-01-01", "vix_regime": "LOW", "prices": {}}
        result_path = publish_static_json(macro, output_dir=tmp_path)

        assert result_path.exists()
        assert result_path.name == "latest.json"
        with open(result_path) as f:
            data = json.load(f)
        assert data["date"] == "2025-01-01"
        assert data["vix_regime"] == "LOW"

    def test_publish_overwrites_existing(self, tmp_path):
        """Calling publish twice overwrites the previous file."""
        publish_static_json({"version": 1}, output_dir=tmp_path)
        publish_static_json({"version": 2}, output_dir=tmp_path)

        with open(tmp_path / "latest.json") as f:
            data = json.load(f)
        assert data["version"] == 2

    def test_publish_creates_directory_if_missing(self, tmp_path):
        """Output directory is created if it does not exist."""
        nested = tmp_path / "deep" / "nested" / "dir"
        publish_static_json({"ok": True}, output_dir=nested)

        assert (nested / "latest.json").exists()


# ===========================================================================
# Multi-channel dispatch integration
# ===========================================================================


class TestMultiChannelDispatch:
    """Verify that a signal can be sent to all channels in one flow."""

    @patch("urllib.request.urlopen")
    def test_send_to_telegram_and_discord(self, mock_urlopen):
        """A single signal is formatted once and dispatched to both channels."""
        mock_urlopen.return_value = _mock_urlopen_success()

        sig = _make_signal()
        message = format_signal(sig)

        tg_ok = send_telegram(message, token="tok", chat_id="123")
        dc_ok = send_discord(message, webhook_url="https://hooks.discord.com/test")

        assert tg_ok is True
        assert dc_ok is True
        assert mock_urlopen.call_count == 2

    @patch("urllib.request.urlopen")
    def test_telegram_fails_discord_uses_separate_call(self, mock_urlopen):
        """Both channels attempt delivery independently via urlopen."""
        import urllib.error

        call_count = 0
        def side_effect_fn(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise urllib.error.URLError("tg down")
            return _mock_urlopen_success()

        mock_urlopen.side_effect = side_effect_fn

        sig = _make_signal()
        message = format_signal(sig)

        tg_ok = send_telegram(message, token="tok", chat_id="123")
        dc_ok = send_discord(message, webhook_url="https://hooks.discord.com/test")

        assert tg_ok is False
        assert dc_ok is True

    @patch("urllib.request.urlopen")
    def test_full_pipeline_format_send_and_persist(self, mock_urlopen, tmp_path):
        """Complete pipeline: format -> send TG + DC -> persist JSON."""
        mock_urlopen.return_value = _mock_urlopen_success()

        sig = _make_signal(instrument="GOLD", name="Gold", score=11)
        message = format_signal(sig)

        tg_ok = send_telegram(message, token="tok", chat_id="1")
        dc_ok = send_discord(message, webhook_url="https://hooks.discord.com/x")

        # Also persist as JSON
        macro_data = {"date": "2025-03-26", "signals": [sig]}
        path = publish_static_json(macro_data, output_dir=tmp_path)

        assert tg_ok is True
        assert dc_ok is True
        assert path.exists()
        with open(path) as f:
            persisted = json.load(f)
        assert persisted["signals"][0]["instrument"] == "GOLD"
