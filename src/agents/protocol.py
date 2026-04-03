"""
Inter-Agent Communication Protocol

Pure functions for creating, validating, and extracting agent messages.
No I/O, no side effects -- suitable for use in any execution context.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


# ── Message dataclass ────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentMessage:
    """Standard message format for inter-agent communication."""

    sender: str  # agent ID
    receiver: str  # agent ID or "broadcast"
    payload: dict  # message content
    timestamp: str  # ISO format
    schema_version: str = "1.0"
    message_type: str = "result"  # "result", "error", "request"


# ── Factory functions ────────────────────────────────────────────────


def create_message(
    sender: str,
    receiver: str,
    payload: dict,
    message_type: str = "result",
) -> AgentMessage:
    """Create a new agent message with current UTC timestamp.

    Args:
        sender: The agent ID that produced this message.
        receiver: Target agent ID, or "broadcast" for all agents.
        payload: Arbitrary dict of message content.
        message_type: One of "result", "error", "request".

    Returns:
        A frozen AgentMessage instance.
    """
    return AgentMessage(
        sender=sender,
        receiver=receiver,
        payload=payload,
        timestamp=datetime.now(timezone.utc).isoformat(),
        message_type=message_type,
    )


def wrap_error(
    agent_id: str,
    error: Exception,
    context: str = "",
) -> AgentMessage:
    """Wrap an exception into an error AgentMessage.

    The payload includes the exception class, message, and optional
    context string. A truncated traceback is included for diagnostics.

    Args:
        agent_id: The agent that encountered the error.
        error: The exception instance.
        context: Optional description of what was happening.

    Returns:
        An AgentMessage with message_type="error".
    """
    tb = traceback.format_exception(type(error), error, error.__traceback__)
    tb_str = "".join(tb[-3:])  # last 3 frames to keep payload compact

    payload = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "context": context,
        "traceback": tb_str,
    }
    return create_message(
        sender=agent_id,
        receiver="broadcast",
        payload=payload,
        message_type="error",
    )


# ── Validation functions ─────────────────────────────────────────────


def validate_payload(
    payload: dict,
    required_fields: list[str],
) -> tuple[bool, list[str]]:
    """Validate that payload contains required fields.

    Args:
        payload: The dict to validate.
        required_fields: List of keys that must be present.

    Returns:
        Tuple of (is_valid, list_of_missing_fields).
        If all fields present, returns (True, []).
    """
    missing = [f for f in required_fields if f not in payload]
    return (len(missing) == 0, missing)


def validate_agent_output(
    agent_id: str,
    output: Any,
    expected_schema: dict[str, type] | None = None,
) -> tuple[bool, str]:
    """Validate agent output against expected schema.

    If expected_schema is None: accept anything (output must not be None).
    If expected_schema provided: check each key exists and isinstance
    matches.

    Args:
        agent_id: The agent whose output is being validated.
        output: The output value to validate.
        expected_schema: Optional mapping of field names to expected
            Python types (e.g. {"score": float, "label": str}).

    Returns:
        Tuple of (is_valid, error_message_or_"ok").
    """
    if output is None:
        return (False, f"Agent '{agent_id}' returned None output")

    if expected_schema is None:
        return (True, "ok")

    if not isinstance(output, dict):
        return (
            False,
            f"Agent '{agent_id}' output must be dict, got {type(output).__name__}",
        )

    errors: list[str] = []
    for key, expected_type in expected_schema.items():
        if key not in output:
            errors.append(f"missing key '{key}'")
        elif not isinstance(output[key], expected_type):
            actual = type(output[key]).__name__
            errors.append(
                f"key '{key}': expected {expected_type.__name__}, got {actual}"
            )

    if errors:
        return (False, f"Agent '{agent_id}': " + "; ".join(errors))

    return (True, "ok")


# ── Extraction functions ─────────────────────────────────────────────


def extract_results(
    messages: list[AgentMessage],
    agent_id: str | None = None,
    message_type: str | None = None,
) -> list[dict]:
    """Extract payloads from messages, optionally filtered.

    Args:
        messages: List of AgentMessage instances to search.
        agent_id: If provided, only include messages from this sender.
        message_type: If provided, only include messages of this type.

    Returns:
        List of payload dicts from matching messages, in order.
    """
    results: list[dict] = []
    for msg in messages:
        if agent_id is not None and msg.sender != agent_id:
            continue
        if message_type is not None and msg.message_type != message_type:
            continue
        results.append(msg.payload)
    return results
