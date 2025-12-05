#!/usr/bin/env python3
"""Hook entry point for PreToolUse and PostToolUse events.

Logs tool calls to SQLite. Neo4j sync happens on SessionEnd.
"""

import json
import sys
from pathlib import Path

# Add hooks root to path for imports
HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from core.config import is_sqlite_available
from sqlite.writer import CLISqliteWriter


def determine_event_type(data: dict) -> str:
    """Determine if this is PreToolUse or PostToolUse.

    Args:
        data: Hook event data

    Returns:
        Event type string
    """
    # Check for explicit event type
    if 'event' in data:
        return data['event']

    # Presence of tool_response/toolOutput indicates PostToolUse
    if 'tool_response' in data or 'toolOutput' in data:
        return 'PostToolUse'

    return 'PreToolUse'


def main():
    """Process PreToolUse or PostToolUse event."""
    try:
        data = json.load(sys.stdin)
        session_id = data.get('session_id') or data.get('sessionId', 'unknown')
        event_type = determine_event_type(data)

        # Log to SQLite
        if is_sqlite_available():
            with CLISqliteWriter() as writer:
                writer.log_event(session_id, event_type, data)

    except json.JSONDecodeError as e:
        print(f"[CLI Hook] JSON decode error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[CLI Hook] Tool hook error: {e}", file=sys.stderr)

    # Always exit 0 to not block CLI
    sys.exit(0)


if __name__ == "__main__":
    main()
