#!/usr/bin/env python3
"""Hook entry point for UserPromptSubmit events.

Logs user prompts to SQLite. Neo4j sync happens on SessionEnd.
"""

import json
import sys
from pathlib import Path

# Add hooks root to path for imports
HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from core.config import is_sqlite_available
from sqlite.writer import CLISqliteWriter


def main():
    """Process UserPromptSubmit event."""
    try:
        data = json.load(sys.stdin)
        session_id = data.get('session_id') or data.get('sessionId', 'unknown')

        # Log to SQLite
        if is_sqlite_available():
            with CLISqliteWriter() as writer:
                writer.log_event(session_id, 'UserPromptSubmit', data)

    except json.JSONDecodeError as e:
        print(f"[CLI Hook] JSON decode error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[CLI Hook] Prompt hook error: {e}", file=sys.stderr)

    # Always exit 0 to not block CLI
    sys.exit(0)


if __name__ == "__main__":
    main()
