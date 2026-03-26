"""Unit tests for src.publishers.telegram — message formatting, send, error handling."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.publishers.telegram import format_signal, send_telegram


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_signal(**overrides) -> dict:
    """Return a complete signal dict with sensible defaults."""
    base = {
        "instrument": "ES",
        "name": "S&P 500 E-mini",
        "direction": "bull",
        "timeframe_bias": "SWING",
        "grade": "A",
        "score": 9,
        "vix_regime": "LOW",
        "pos_size": "FULL",
        "entry_price": 5200.0,
        "stop_loss": 5150.0,
        "sl_type": "ATR",
        "target_1": 5300.0,
        "target_2": 5400.0,
        "rr_t1": 2.0,
        "rr_t2": 4.0,
    }
    base.update(overrides)
    return base


# ===== format_signal =======================================================

class TestFormatSignal:
    """Verify Telegram message formatting matches v1 layout."""

    def test_bull_direction_shows_long_and_up_arrow(self):
        msg = format_signal(_make_signal(direction="bull"))
        assert "LONG" in msg
        assert "\u25b2" in msg  # up-arrow

    def test_bear_direction_shows_short_and_down_arrow(self):
        msg = format_signal(_make_signal(direction="bear"))
        assert "SHORT" in msg
        assert "\u25bc" in msg  # down-arrow

    def test_name_and_timeframe_in_header(self):
        msg = format_signal(_make_signal(name="Gold", timeframe_bias="MAKRO"))
        lines = msg.split("\n")
        assert "<b>Gold</b> [MAKRO]" == lines[0]

    def test_grade_score_vix_in_second_line(self):
        msg = format_signal(_make_signal(grade="B", score=7, vix_regime="HIGH", pos_size="HALF"))
        lines = msg.split("\n")
        assert "B(7/12)" in lines[1]
        assert "VIX:HIGH" in lines[1]
        assert "HALF" in lines[1]

    def test_entry_and_stop_loss_lines(self):
        msg = format_signal(_make_signal(entry_price=100.5, stop_loss=98.0, sl_type="fixed"))
        assert "Entry: 100.5" in msg
        assert "SL:    98.0  (fixed)" in msg

    def test_targets_included(self):
        msg = format_signal(_make_signal(target_1=110, target_2=120, rr_t1=2.5, rr_t2=5.0))
        assert "T1:    110  R:R 2.5" in msg
        assert "T2:    120  R:R 5.0" in msg

    def test_missing_optional_fields_omitted(self):
        sig = _make_signal()
        del sig["entry_price"]
        del sig["stop_loss"]
        del sig["target_1"]
        del sig["target_2"]
        msg = format_signal(sig)
        assert "Entry" not in msg
        assert "SL:" not in msg
        assert "T1:" not in msg
        assert "T2:" not in msg

    def test_fallback_key_when_no_instrument(self):
        sig = {"key": "NQ", "direction": "bull", "grade": "B", "score": 6}
        msg = format_signal(sig)
        assert "<b>NQ</b>" in msg


# ===== send_telegram =======================================================

class TestSendTelegram:
    """Network calls are mocked; tests verify payload construction and error paths."""

    @patch("src.publishers.telegram.urllib.request.urlopen")
    def test_success_returns_true(self, mock_urlopen):
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=MagicMock(status=200))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        result = send_telegram("hello", token="tok123", chat_id="456")
        assert result is True

    @patch("src.publishers.telegram.urllib.request.urlopen")
    def test_payload_contains_html_parse_mode(self, mock_urlopen):
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=MagicMock(status=200))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        send_telegram("test msg", token="tok", chat_id="42")
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        body = json.loads(req.data.decode())
        assert body["parse_mode"] == "HTML"
        assert body["chat_id"] == "42"
        assert body["text"] == "test msg"

    @patch("src.publishers.telegram.urllib.request.urlopen")
    def test_url_contains_bot_token(self, mock_urlopen):
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=MagicMock(status=200))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        send_telegram("x", token="SECRET", chat_id="1")
        req = mock_urlopen.call_args[0][0]
        assert "botSECRET/sendMessage" in req.full_url

    def test_missing_token_returns_false(self):
        with patch.dict("os.environ", {}, clear=True):
            assert send_telegram("hi", token="", chat_id="1") is False

    def test_missing_chat_id_returns_false(self):
        with patch.dict("os.environ", {}, clear=True):
            assert send_telegram("hi", token="tok", chat_id="") is False

    @patch("src.publishers.telegram.urllib.request.urlopen")
    def test_env_fallback_used(self, mock_urlopen):
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=MagicMock(status=200))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        with patch.dict("os.environ", {"TELEGRAM_TOKEN": "envtok", "TELEGRAM_CHAT_ID": "envid"}):
            result = send_telegram("msg")
        assert result is True
        req = mock_urlopen.call_args[0][0]
        assert "botenvtok/" in req.full_url
        body = json.loads(req.data.decode())
        assert body["chat_id"] == "envid"

    @patch("src.publishers.telegram.urllib.request.urlopen")
    def test_url_error_returns_false(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("timeout")
        result = send_telegram("fail", token="t", chat_id="c")
        assert result is False
