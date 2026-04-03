"""Unit tests for src.agents.protocol — inter-agent communication."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.agents.protocol import (
    AgentMessage,
    create_message,
    extract_results,
    validate_agent_output,
    validate_payload,
    wrap_error,
)

# ── create_message ───────────────────────────────────────────────────


class TestCreateMessage:
    """Creating agent messages."""

    def test_basic_creation(self):
        msg = create_message("sender_a", "receiver_b", {"score": 0.85})
        assert msg.sender == "sender_a"
        assert msg.receiver == "receiver_b"
        assert msg.payload == {"score": 0.85}
        assert msg.message_type == "result"
        assert msg.schema_version == "1.0"

    def test_timestamp_is_iso_format(self):
        msg = create_message("a", "b", {})
        # Should parse without error
        parsed = datetime.fromisoformat(msg.timestamp)
        assert parsed.tzinfo is not None  # must be timezone-aware

    def test_custom_message_type(self):
        msg = create_message("a", "b", {}, message_type="request")
        assert msg.message_type == "request"

    def test_broadcast_receiver(self):
        msg = create_message("a", "broadcast", {"alert": True})
        assert msg.receiver == "broadcast"

    def test_message_is_frozen(self):
        msg = create_message("a", "b", {})
        with pytest.raises(AttributeError):
            msg.sender = "c"  # type: ignore[misc]


# ── validate_payload ─────────────────────────────────────────────────


class TestValidatePayload:
    """Validating payload fields."""

    def test_all_fields_present(self):
        payload = {"score": 0.9, "label": "bullish", "confidence": 0.8}
        valid, missing = validate_payload(payload, ["score", "label", "confidence"])
        assert valid is True
        assert missing == []

    def test_missing_one_field(self):
        payload = {"score": 0.9}
        valid, missing = validate_payload(payload, ["score", "label"])
        assert valid is False
        assert missing == ["label"]

    def test_missing_multiple_fields(self):
        valid, missing = validate_payload({}, ["a", "b", "c"])
        assert valid is False
        assert set(missing) == {"a", "b", "c"}

    def test_empty_required_always_valid(self):
        valid, missing = validate_payload({"anything": 1}, [])
        assert valid is True
        assert missing == []

    def test_empty_payload_with_requirements(self):
        valid, missing = validate_payload({}, ["required_key"])
        assert valid is False
        assert missing == ["required_key"]

    def test_extra_fields_ignored(self):
        payload = {"needed": 1, "extra": 2, "bonus": 3}
        valid, _ = validate_payload(payload, ["needed"])
        assert valid is True


# ── validate_agent_output ────────────────────────────────────────────


class TestValidateAgentOutput:
    """Validating agent output against schema."""

    def test_none_output_invalid(self):
        valid, msg = validate_agent_output("agent_x", None)
        assert valid is False
        assert "None" in msg

    def test_no_schema_accepts_anything(self):
        valid, msg = validate_agent_output("agent_x", {"data": 42})
        assert valid is True
        assert msg == "ok"

    def test_no_schema_accepts_string(self):
        valid, msg = validate_agent_output("agent_x", "raw text output")
        assert valid is True
        assert msg == "ok"

    def test_schema_match(self):
        schema = {"score": float, "label": str}
        output = {"score": 0.85, "label": "bullish"}
        valid, msg = validate_agent_output("agent_x", output, schema)
        assert valid is True
        assert msg == "ok"

    def test_schema_wrong_type(self):
        schema = {"score": float}
        output = {"score": "not_a_number"}
        valid, msg = validate_agent_output("agent_x", output, schema)
        assert valid is False
        assert "expected float" in msg

    def test_schema_missing_key(self):
        schema = {"score": float, "label": str}
        output = {"score": 0.9}
        valid, msg = validate_agent_output("agent_x", output, schema)
        assert valid is False
        assert "missing key 'label'" in msg

    def test_non_dict_output_with_schema(self):
        schema = {"score": float}
        valid, msg = validate_agent_output("agent_x", "string_output", schema)
        assert valid is False
        assert "must be dict" in msg

    def test_int_passes_for_int_schema(self):
        schema = {"count": int}
        valid, msg = validate_agent_output("agent_x", {"count": 42}, schema)
        assert valid is True


# ── wrap_error ───────────────────────────────────────────────────────


class TestWrapError:
    """Wrapping exceptions into error messages."""

    def test_basic_wrap(self):
        try:
            raise ValueError("bad input")
        except ValueError as e:
            msg = wrap_error("failing_agent", e, context="during scoring")

        assert msg.sender == "failing_agent"
        assert msg.receiver == "broadcast"
        assert msg.message_type == "error"
        assert msg.payload["error_type"] == "ValueError"
        assert msg.payload["error_message"] == "bad input"
        assert msg.payload["context"] == "during scoring"

    def test_traceback_included(self):
        try:
            raise RuntimeError("crash")
        except RuntimeError as e:
            msg = wrap_error("agent_z", e)

        assert "traceback" in msg.payload
        assert len(msg.payload["traceback"]) > 0

    def test_empty_context_default(self):
        try:
            raise TypeError("type issue")
        except TypeError as e:
            msg = wrap_error("agent_y", e)

        assert msg.payload["context"] == ""


# ── extract_results ──────────────────────────────────────────────────


class TestExtractResults:
    """Extracting payloads from message lists."""

    @pytest.fixture()
    def messages(self) -> list[AgentMessage]:
        return [
            create_message("agent_a", "broadcast", {"score": 0.9}),
            create_message("agent_b", "broadcast", {"score": 0.7}),
            create_message(
                "agent_a", "broadcast", {"alert": True}, message_type="error"
            ),
            create_message("agent_c", "agent_a", {"request": "data"}),
        ]

    def test_extract_all(self, messages):
        results = extract_results(messages)
        assert len(results) == 4

    def test_filter_by_agent_id(self, messages):
        results = extract_results(messages, agent_id="agent_a")
        assert len(results) == 2
        assert results[0] == {"score": 0.9}

    def test_filter_by_message_type(self, messages):
        results = extract_results(messages, message_type="error")
        assert len(results) == 1
        assert results[0]["alert"] is True

    def test_filter_by_both(self, messages):
        results = extract_results(
            messages, agent_id="agent_a", message_type="result"
        )
        assert len(results) == 1
        assert results[0] == {"score": 0.9}

    def test_empty_messages_list(self):
        assert extract_results([]) == []

    def test_no_matches(self, messages):
        results = extract_results(messages, agent_id="nonexistent")
        assert results == []
