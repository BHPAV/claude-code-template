"""
Data models for Claude Code CLI hook events.

Mirrors patterns from self_improving_agent_v3/hooks/monitoring.py
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CLISessionStartEvent:
    """SessionStart hook event data."""

    session_id: str
    timestamp: datetime
    working_dir: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CLISessionEndEvent:
    """SessionEnd hook event data."""

    session_id: str
    timestamp: datetime
    duration_seconds: float
    tool_count: int = 0
    prompt_count: int = 0


@dataclass
class CLIToolCallEvent:
    """PreToolUse hook event data."""

    session_id: str
    tool_name: str
    tool_input: dict[str, Any]
    timestamp: datetime
    call_id: str


@dataclass
class CLIToolResultEvent:
    """PostToolUse hook event data."""

    session_id: str
    tool_name: str
    tool_input: dict[str, Any]
    tool_output: str
    timestamp: datetime
    call_id: str
    duration_ms: float | None = None
    success: bool = True
    error: str | None = None


@dataclass
class CLIPromptEvent:
    """UserPromptSubmit hook event data."""

    session_id: str
    prompt_text: str
    timestamp: datetime


def sanitize_tool_input(tool_input: dict[str, Any]) -> dict[str, Any]:
    """Remove sensitive data from tool inputs."""
    sensitive_keys = ["password", "api_key", "token", "secret", "auth"]
    sanitized = tool_input.copy()

    for key in list(sanitized.keys()):
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            sanitized[key] = "[REDACTED]"

    return sanitized
