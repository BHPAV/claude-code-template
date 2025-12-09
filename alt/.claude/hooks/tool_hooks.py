#!/usr/bin/env python3
"""
Claude Code PreToolUse/PostToolUse hook handler.

Logs tool calls to Neo4j.

Usage (configured in .claude/settings.local.json):
    python claude_code_hooks/tool_hooks.py < hook_data.json
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# Import from same directory (all hook files are in .claude/hooks/)
from models import CLIToolCallEvent, CLIToolResultEvent
from neo4j_writer import CLINeo4jWriter
from config import is_neo4j_available

# In-memory call tracking
CALL_CACHE_FILE = Path(__file__).parent / ".tool_call_cache.json"


def load_call_cache():
    """Load tool call start times."""
    if CALL_CACHE_FILE.exists():
        try:
            return json.loads(CALL_CACHE_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_call_cache(data):
    """Save tool call start times."""
    try:
        CALL_CACHE_FILE.write_text(json.dumps(data, indent=2))
    except IOError:
        pass  # Fail silently


def handle_pre_tool_use(hook_data: dict):
    """Handle PreToolUse event (just track timing)."""
    session_id = hook_data.get("sessionId", "unknown")
    tool_name = hook_data.get("toolName", "unknown")
    tool_input = hook_data.get("toolInput", {})
    now = datetime.now()
    call_id = f"{session_id}:{tool_name}:{now.isoformat()}"

    # Save start time for duration calculation
    call_cache = load_call_cache()
    call_cache[call_id] = {
        "session_id": session_id,
        "tool_name": tool_name,
        "start_time": now.isoformat(),
        "tool_input": tool_input,
    }
    save_call_cache(call_cache)


def handle_post_tool_use(hook_data: dict):
    """Handle PostToolUse event (write to Neo4j)."""
    session_id = hook_data.get("sessionId", "unknown")
    tool_name = hook_data.get("toolName", "unknown")
    tool_input = hook_data.get("toolInput", {})
    tool_output = hook_data.get("toolOutput", "")

    # Find matching PreToolUse call
    call_cache = load_call_cache()
    matching_call = None
    call_id_to_remove = None

    # Look for most recent matching call
    for call_id in sorted(call_cache.keys(), reverse=True):
        call_data = call_cache[call_id]
        if (
            call_data["session_id"] == session_id
            and call_data["tool_name"] == tool_name
        ):
            matching_call = call_data
            call_id_to_remove = call_id
            break

    if not matching_call:
        # No matching PreToolUse, create one with current time
        now = datetime.now()
        matching_call = {
            "session_id": session_id,
            "tool_name": tool_name,
            "start_time": now.isoformat(),
            "tool_input": tool_input,
        }
        call_id_to_remove = None

    # Calculate duration
    start_time = datetime.fromisoformat(matching_call["start_time"])
    end_time = datetime.now()
    duration_ms = (end_time - start_time).total_seconds() * 1000

    # Determine success (basic heuristic)
    success = True
    error = None
    output_str = str(tool_output)
    if (
        "error" in output_str.lower()
        or "failed" in output_str.lower()
        or "exception" in output_str.lower()
    ):
        success = False
        error = output_str[:500]

    event = CLIToolResultEvent(
        session_id=session_id,
        tool_name=tool_name,
        tool_input=matching_call["tool_input"],
        tool_output=output_str,
        timestamp=end_time,
        call_id=call_id_to_remove or f"{session_id}:{tool_name}:{end_time.isoformat()}",
        duration_ms=duration_ms,
        success=success,
        error=error,
    )

    # Write to Neo4j
    if is_neo4j_available():
        try:
            with CLINeo4jWriter() as writer:
                writer.create_tool_call_node(event)
        except Exception as e:
            print(f"[CLI Hook] Failed to log tool call: {e}", file=sys.stderr)

    # Cleanup cache
    if call_id_to_remove and call_id_to_remove in call_cache:
        del call_cache[call_id_to_remove]
        save_call_cache(call_cache)


def main():
    """Main entry point for hook script."""
    try:
        hook_data = json.load(sys.stdin)
        event_type = hook_data.get("event")

        if event_type == "PreToolUse":
            handle_pre_tool_use(hook_data)
        elif event_type == "PostToolUse":
            handle_post_tool_use(hook_data)

    except Exception as e:
        print(f"[CLI Hook] Error: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
