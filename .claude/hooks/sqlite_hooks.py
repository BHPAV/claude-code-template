#!/usr/bin/env python3
"""SQLite JSON logging hook for Claude Code CLI - Enhanced version.

This hook logs all Claude Code events to a SQLite database with
extracted fields for easy SQL querying.

Handles: UserPromptSubmit, SessionStart, SessionEnd, PreToolUse, PostToolUse,
         Stop, SubagentStop, PreCompact
"""
import json
import sys

from sqlite_config import is_sqlite_available
from sqlite_writer import CLISqliteWriter


# Supported event types
SUPPORTED_EVENTS = {
    'UserPromptSubmit',
    'SessionStart',
    'SessionEnd',
    'PreToolUse',
    'PostToolUse',
    'Stop',
    'SubagentStop',
    'PreCompact',
}


def determine_event_type(data: dict) -> str:
    """Determine event type from hook data.

    Args:
        data: The hook event data dict

    Returns:
        Event type string
    """
    # Check for hook_event_name (most events from Claude Code)
    if 'hook_event_name' in data:
        return data['hook_event_name']

    # Check for event field (alternative format)
    if 'event' in data:
        return data['event']

    # UserPromptSubmit has prompt field
    if 'prompt' in data:
        return 'UserPromptSubmit'

    # Tool events may have tool_name without hook_event_name
    if 'tool_name' in data or 'toolName' in data:
        # Check for tool_response/toolOutput to distinguish Pre from Post
        if 'tool_response' in data or 'toolOutput' in data:
            return 'PostToolUse'
        return 'PreToolUse'

    return 'Unknown'


def main():
    try:
        data = json.load(sys.stdin)
        session_id = data.get('session_id') or data.get('sessionId', 'unknown')
        event_type = determine_event_type(data)

        # Log all events (including Unknown for debugging)
        if is_sqlite_available():
            with CLISqliteWriter() as writer:
                writer.log_event(session_id, event_type, data)

    except json.JSONDecodeError as e:
        print(f"[SQLite Hook] JSON decode error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[SQLite Hook] Error: {e}", file=sys.stderr)

    # Always exit 0 to never block the CLI
    sys.exit(0)


if __name__ == "__main__":
    main()
