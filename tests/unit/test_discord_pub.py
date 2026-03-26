"""Unit tests for src.publishers.discord — webhook payload, code block wrapping, errors."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.publishers.discord import send_discord


# ===== send_discord ========================================================

class TestSendDiscordSuccess:
    """Verify successful sends build the right payload."""

    @patch("src.publishers.discord.urllib.request.urlopen")
    def test_success_returns_true(self, mock_urlopen):
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=MagicMock(status=204))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        result = send_discord("hello", webhook_url="https://discord.com/api/webhooks/test")
        assert result is True

    @patch("src.publishers.discord.urllib.request.urlopen")
    def test_payload_wraps_in_code_block(self, mock_urlopen):
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=MagicMock(status=204))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        send_discord("signal text", webhook_url="https://example.com/hook")
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode())
        assert body["content"] == "```\nsignal text\n```"

    @patch("src.publishers.discord.urllib.request.urlopen")
    def test_content_type_is_json(self, mock_urlopen):
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=MagicMock(status=204))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        send_discord("x", webhook_url="https://example.com/hook")
        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Content-type") == "application/json"

    @patch("src.publishers.discord.urllib.request.urlopen")
    def test_request_url_matches_webhook(self, mock_urlopen):
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=MagicMock(status=200))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        url = "https://discord.com/api/webhooks/123/abc"
        send_discord("msg", webhook_url=url)
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == url


class TestSendDiscordConfig:
    """Test configuration / env-var fallback paths."""

    def test_missing_webhook_returns_false(self):
        with patch.dict("os.environ", {}, clear=True):
            assert send_discord("hi", webhook_url="") is False

    def test_none_webhook_no_env_returns_false(self):
        with patch.dict("os.environ", {}, clear=True):
            assert send_discord("hi") is False

    @patch("src.publishers.discord.urllib.request.urlopen")
    def test_env_fallback_webhook(self, mock_urlopen):
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=MagicMock(status=204))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        with patch.dict("os.environ", {"DISCORD_WEBHOOK": "https://env-hook.com/wh"}):
            result = send_discord("msg")
        assert result is True
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "https://env-hook.com/wh"


class TestSendDiscordErrors:
    """Test error handling for network failures."""

    @patch("src.publishers.discord.urllib.request.urlopen")
    def test_url_error_returns_false(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        result = send_discord("fail", webhook_url="https://bad.url/hook")
        assert result is False

    @patch("src.publishers.discord.urllib.request.urlopen")
    def test_multiline_message_preserved(self, mock_urlopen):
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=MagicMock(status=204))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        msg = "line1\nline2\nline3"
        send_discord(msg, webhook_url="https://example.com/hook")
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode())
        assert body["content"] == f"```\n{msg}\n```"
        assert body["content"].count("\n") == 4  # ``` + 3 lines content + ```
