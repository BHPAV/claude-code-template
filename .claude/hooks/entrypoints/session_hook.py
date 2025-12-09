#!/usr/bin/env python3
"""Hook entry point for SessionStart and SessionEnd events.

Logs session lifecycle to SQLite. On SessionEnd, triggers Neo4j sync.
"""

import json
import sys
from pathlib import Path

# Add hooks root to path for imports
HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from core.config import is_sqlite_available, is_neo4j_available
from sqlite.writer import CLISqliteWriter
from graph.sync import sync_session_to_neo4j


def main():
    """Process SessionStart or SessionEnd event."""
    try:
        data = json.load(sys.stdin)
        session_id = data.get('session_id') or data.get('sessionId', 'unknown')
        event_type = data.get('event', 'Unknown')

        # Log to SQLite
        if is_sqlite_available():
            with CLISqliteWriter() as writer:
                writer.log_event(session_id, event_type, data)

        # On SessionEnd, sync to Neo4j
        if event_type == 'SessionEnd':
            if is_neo4j_available():
                try:
                    sync_session_to_neo4j(session_id)
                except Exception as e:
                    print(f"[CLI Hook] Neo4j sync failed: {e}", file=sys.stderr)

    except json.JSONDecodeError as e:
        print(f"[CLI Hook] JSON decode error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[CLI Hook] Session hook error: {e}", file=sys.stderr)

    # Always exit 0 to not block CLI
    sys.exit(0)


if __name__ == "__main__":
    main()
