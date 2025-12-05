"""Sync session data from SQLite to Neo4j."""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add hooks root to path for imports
HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from core.config import is_neo4j_available
from core.models import (
    CLISessionStartEvent,
    CLISessionEndEvent,
    CLIToolResultEvent,
    CLIPromptEvent,
)
from sqlite.reader import CLISqliteReader
from graph.writer import CLINeo4jWriter


def sync_session_to_neo4j(session_id: str) -> bool:
    """
    Sync a complete session from SQLite to Neo4j.

    Called on SessionEnd event. Reads all session data from SQLite
    and creates corresponding nodes and relationships in Neo4j.

    Args:
        session_id: The session identifier to sync

    Returns:
        True if sync was successful, False otherwise
    """
    if not is_neo4j_available():
        print(f"[Hook] Neo4j not available, skipping sync for {session_id}", file=sys.stderr)
        return False

    try:
        with CLISqliteReader() as reader, CLINeo4jWriter() as writer:
            # 1. Get session start event and create session node
            start_event = reader.get_session_start_event(session_id)
            if start_event:
                session_start = CLISessionStartEvent(
                    session_id=session_id,
                    timestamp=_parse_timestamp(start_event['timestamp']),
                    working_dir=start_event.get('cwd') or '',
                    metadata={
                        'platform': start_event.get('platform'),
                        'git_branch': start_event.get('git_branch'),
                        'python_version': start_event.get('python_version')
                    }
                )
                writer.create_session_node(session_start)
            else:
                # Create a minimal session node if no start event exists
                session_start = CLISessionStartEvent(
                    session_id=session_id,
                    timestamp=datetime.now(),
                    working_dir='',
                    metadata={}
                )
                writer.create_session_node(session_start)

            # 2. Create prompt nodes
            prompts = reader.get_prompts(session_id)
            for prompt_row in prompts:
                prompt_event = CLIPromptEvent(
                    session_id=session_id,
                    prompt_text=prompt_row.get('prompt_text') or '',
                    timestamp=_parse_timestamp(prompt_row['timestamp'])
                )
                writer.create_prompt_node(prompt_event)

            # 3. Create tool call nodes
            tool_calls = reader.get_tool_calls(session_id)
            for tool_row in tool_calls:
                # Parse raw_json to get original tool_input
                raw_data = {}
                if tool_row.get('raw_json'):
                    try:
                        raw_data = json.loads(tool_row['raw_json'])
                    except json.JSONDecodeError:
                        pass

                tool_input = raw_data.get('tool_input') or raw_data.get('toolInput') or {}
                tool_output = raw_data.get('tool_response') or raw_data.get('toolOutput') or ''

                tool_event = CLIToolResultEvent(
                    session_id=session_id,
                    tool_name=tool_row.get('tool_name') or 'unknown',
                    tool_input=tool_input,
                    tool_output=str(tool_output),
                    timestamp=_parse_timestamp(tool_row['timestamp']),
                    call_id=tool_row.get('tool_use_id') or '',
                    duration_ms=tool_row.get('duration_ms'),
                    success=bool(tool_row.get('success', 1)),
                    error=tool_row.get('error_message')
                )
                writer.create_tool_call_node(tool_event)

            # 4. Complete session with end data
            end_event = reader.get_session_end_event(session_id)
            if end_event:
                duration_ms = end_event.get('duration_ms') or 0
                duration_seconds = duration_ms / 1000.0

                session_end = CLISessionEndEvent(
                    session_id=session_id,
                    timestamp=_parse_timestamp(end_event['timestamp']),
                    duration_seconds=duration_seconds,
                    tool_count=len(tool_calls),
                    prompt_count=len(prompts)
                )
                writer.complete_session_node(session_end)

            # 5. Create metrics summary
            writer.create_metrics_summary(session_id)

            # 6. Mark session as synced in SQLite
            reader.mark_session_synced(session_id)

            return True

    except Exception as e:
        print(f"[Hook] Neo4j sync failed for {session_id}: {e}", file=sys.stderr)
        return False


def sync_all_unsynced_sessions() -> int:
    """
    Sync all unsynced completed sessions from SQLite to Neo4j.

    Returns:
        Number of sessions successfully synced
    """
    if not is_neo4j_available():
        print("[Hook] Neo4j not available, skipping batch sync", file=sys.stderr)
        return 0

    synced_count = 0

    try:
        with CLISqliteReader() as reader:
            unsynced = reader.get_unsynced_sessions()

            for session_id in unsynced:
                # Only sync completed sessions
                if reader.is_session_complete(session_id):
                    if sync_session_to_neo4j(session_id):
                        synced_count += 1

    except Exception as e:
        print(f"[Hook] Batch sync failed: {e}", file=sys.stderr)

    return synced_count


def _parse_timestamp(timestamp_str: str) -> datetime:
    """Parse ISO format timestamp string to datetime.

    Args:
        timestamp_str: ISO format timestamp

    Returns:
        datetime object
    """
    if not timestamp_str:
        return datetime.now()

    try:
        # Handle various ISO formats
        ts = timestamp_str.replace('Z', '+00:00')
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return datetime.now()


if __name__ == "__main__":
    # CLI for manual sync
    import argparse

    parser = argparse.ArgumentParser(description="Sync sessions from SQLite to Neo4j")
    parser.add_argument("--session", "-s", help="Specific session ID to sync")
    parser.add_argument("--all", "-a", action="store_true", help="Sync all unsynced sessions")

    args = parser.parse_args()

    if args.session:
        success = sync_session_to_neo4j(args.session)
        print(f"Session {args.session}: {'synced' if success else 'failed'}")
    elif args.all:
        count = sync_all_unsynced_sessions()
        print(f"Synced {count} sessions")
    else:
        parser.print_help()
