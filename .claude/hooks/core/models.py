"""
Data models for Claude Code CLI hook events.
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
    sequence_index: int = 0


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
    # Enriched fields for sync
    tool_category: str | None = None
    subagent_type: str | None = None
    command: str | None = None
    pattern: str | None = None
    url: str | None = None
    file_path: str | None = None  # Primary file path (backward compat)
    output_size_bytes: int | None = None
    has_stderr: bool = False
    sequence_index: int = 0
    # Enhanced file tracking (Phase 1 Unified File Model)
    file_paths: list[str] = field(default_factory=list)  # All extracted paths
    access_mode: str | None = None  # read, write, modify, search, execute
    project_root: str | None = None  # Detected project root
    glob_matches: list[str] = field(default_factory=list)  # Glob expansion results
    grep_matches: list[dict] = field(default_factory=list)  # Grep file matches


@dataclass
class CLIPromptEvent:
    """UserPromptSubmit hook event data."""

    session_id: str
    prompt_text: str
    timestamp: datetime
    intent_type: str | None = None
    sequence_index: int = 0


@dataclass
class FileAccessEvent:
    """Individual file access event for the file_access_log table.

    Represents a single file access during a tool call, supporting
    multiple files per tool and enhanced tracking metadata.
    """

    session_id: str
    file_path: str  # Original path from tool
    normalized_path: str  # Unix-style normalized path
    access_mode: str  # read, write, modify, search, execute
    timestamp: datetime
    tool_name: str
    event_id: int | None = None  # Reference to events table
    project_root: str | None = None
    line_numbers: list[int] = field(default_factory=list)  # For grep matches
    is_primary_target: bool = True  # Primary file vs related (glob/grep results)
    is_glob_expansion: bool = False  # From glob result expansion
    synced_to_neo4j: bool = False
