#!/usr/bin/env python3
"""Hook entry point for SubagentStop events.

Captures tool calls made by subagents by parsing their transcript JSONL files.
Each tool call is logged as a separate event with parent session linkage.
"""

import json
import sys
from pathlib import Path

# Add hooks root to path for imports
HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from core.config import is_sqlite_available
from core.helpers import (
    parse_transcript_tool_calls,
    get_subagent_session_id_from_transcript,
)
from sqlite.writer import CLISqliteWriter


def main():
    """Process SubagentStop event and extract subagent tool calls."""
    try:
        data = json.load(sys.stdin)

        # Get parent session ID (the main agent's session)
        parent_session_id = data.get('session_id') or data.get('sessionId', 'unknown')

        # IMPORTANT: Use agent_transcript_path (subagent's transcript), NOT transcript_path (parent's)
        agent_transcript_path = data.get('agent_transcript_path')

        # Get agent_id directly from payload
        agent_id = data.get('agent_id')

        if not is_sqlite_available():
            sys.exit(0)

        if not agent_transcript_path:
            print("[CLI Hook] SubagentStop: No agent_transcript_path in payload", file=sys.stderr)
            sys.exit(0)

        if not agent_id:
            # Fall back to extracting from transcript path (e.g., "agent-16d62f34.jsonl" -> "16d62f34")
            stem = Path(agent_transcript_path).stem
            agent_id = stem.replace('agent-', '') if stem.startswith('agent-') else stem

        # Try to determine subagent_type from the most recent Task call
        # (This would require looking at the parent session's events,
        # but for now we'll leave it as None and let it be enriched later)
        subagent_type = None

        with CLISqliteWriter() as writer:
            # Log the SubagentStop event itself
            writer.log_event(parent_session_id, 'SubagentStop', data)

            # Parse SUBAGENT transcript and log each tool call
            tool_calls = parse_transcript_tool_calls(agent_transcript_path)

            for tool_call in tool_calls:
                writer.log_subagent_tool_call(
                    parent_session_id=parent_session_id,
                    agent_id=agent_id,
                    tool_call=tool_call,
                    subagent_type=subagent_type,
                )

            if tool_calls:
                print(f"[CLI Hook] SubagentStop: Logged {len(tool_calls)} tool calls from subagent {agent_id}...", file=sys.stderr)

    except json.JSONDecodeError as e:
        print(f"[CLI Hook] SubagentStop JSON decode error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[CLI Hook] SubagentStop error: {e}", file=sys.stderr)

    # Always exit 0 to not block CLI
    sys.exit(0)


if __name__ == "__main__":
    main()
