#!/usr/bin/env python3
"""
Claude Code SessionStart/SessionEnd hook handler.

Logs session lifecycle to Neo4j.

Usage (configured in .claude/settings.local.json):
    python claude_code_hooks/session_hooks.py < hook_data.json
"""

import sys
import json
import os
from datetime import datetime
from pathlib import Path

# Import from same directory (all hook files are in .claude/hooks/)
from models import CLISessionStartEvent, CLISessionEndEvent
from neo4j_writer import CLINeo4jWriter
from config import is_neo4j_available

# In-memory session tracking (simple file-based)
SESSION_FILE = Path(__file__).parent / ".session_cache.json"


def load_session_data():
    """Load session start data from cache."""
    if SESSION_FILE.exists():
        try:
            return json.loads(SESSION_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_session_data(data):
    """Save session start data to cache."""
    try:
        SESSION_FILE.write_text(json.dumps(data, indent=2))
    except IOError:
        pass  # Fail silently


def handle_session_start(hook_data: dict):
    """Handle SessionStart event."""
    session_id = hook_data.get("sessionId", "unknown")
    working_dir = os.getcwd()

    event = CLISessionStartEvent(
        session_id=session_id,
        timestamp=datetime.now(),
        working_dir=working_dir,
        metadata={"platform": sys.platform},
    )

    # Save to cache for SessionEnd
    session_cache = load_session_data()
    session_cache[session_id] = {
        "start_time": event.timestamp.isoformat(),
        "working_dir": working_dir,
    }
    save_session_data(session_cache)

    # Write to Neo4j
    if is_neo4j_available():
        try:
            with CLINeo4jWriter() as writer:
                writer.create_session_node(event)
        except Exception as e:
            print(f"[CLI Hook] Failed to log SessionStart: {e}", file=sys.stderr)


def handle_session_end(hook_data: dict):
    """Handle SessionEnd event."""
    session_id = hook_data.get("sessionId", "unknown")

    # Load start time from cache
    session_cache = load_session_data()
    session_data = session_cache.get(session_id, {})
    start_time_str = session_data.get("start_time")

    if not start_time_str:
        return  # Can't calculate duration

    start_time = datetime.fromisoformat(start_time_str)
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    event = CLISessionEndEvent(
        session_id=session_id,
        timestamp=end_time,
        duration_seconds=duration,
        tool_count=0,  # Will be set from graph
        prompt_count=0,  # Will be set from graph
    )

    # Write to Neo4j
    if is_neo4j_available():
        try:
            with CLINeo4jWriter() as writer:
                writer.complete_session_node(event)
                writer.create_metrics_summary(session_id)
        except Exception as e:
            print(f"[CLI Hook] Failed to log SessionEnd: {e}", file=sys.stderr)

    # Cleanup cache
    if session_id in session_cache:
        del session_cache[session_id]
        save_session_data(session_cache)


def main():
    """Main entry point for hook script."""
    try:
        # Read hook data from stdin
        hook_data = json.load(sys.stdin)
        event_type = hook_data.get("event")

        if event_type == "SessionStart":
            handle_session_start(hook_data)
        elif event_type == "SessionEnd":
            handle_session_end(hook_data)

    except Exception as e:
        print(f"[CLI Hook] Error: {e}", file=sys.stderr)
        sys.exit(0)  # Don't fail the CLI command


if __name__ == "__main__":
    main()
