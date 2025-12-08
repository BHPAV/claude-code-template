"""Sync session data from SQLite to Neo4j."""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add hooks root to path for imports
HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

# Add domo directory to path for machine detection
DOMO_DIR = HOOKS_DIR.parent.parent / "domo"
if DOMO_DIR.exists():
    sys.path.insert(0, str(DOMO_DIR))

from core.config import is_neo4j_available
from core.models import (
    CLISessionStartEvent,
    CLISessionEndEvent,
    CLIToolResultEvent,
    CLIPromptEvent,
    FileAccessEvent,
)
from sqlite.reader import CLISqliteReader
from graph.writer import CLINeo4jWriter


def _detect_machine_id() -> str:
    """Detect current machine ID using DomoEnv if available."""
    try:
        from domo_env import DomoEnv
        env = DomoEnv()
        return env.machine_id
    except ImportError:
        pass
    except Exception:
        pass
    return None


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
        # Detect machine_id for session linking
        machine_id = _detect_machine_id()

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
                writer.create_session_node(session_start, machine_id=machine_id)
            else:
                # Create a minimal session node if no start event exists
                session_start = CLISessionStartEvent(
                    session_id=session_id,
                    timestamp=datetime.now(),
                    working_dir='',
                    metadata={}
                )
                writer.create_session_node(session_start, machine_id=machine_id)

            # 2. Create prompt nodes
            prompts = reader.get_prompts(session_id)
            for prompt_row in prompts:
                prompt_event = CLIPromptEvent(
                    session_id=session_id,
                    prompt_text=prompt_row.get('prompt_text') or '',
                    timestamp=_parse_timestamp(prompt_row['timestamp']),
                    intent_type=prompt_row.get('intent_type'),
                    sequence_index=prompt_row.get('sequence_index') or 0,
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
                    error=tool_row.get('error_message'),
                    # Extract enriched fields from SQLite columns
                    tool_category=tool_row.get('tool_category'),
                    subagent_type=tool_row.get('subagent_type'),
                    command=tool_row.get('command'),
                    pattern=tool_row.get('pattern'),
                    url=tool_row.get('url'),
                    file_path=tool_row.get('file_path'),
                    output_size_bytes=tool_row.get('output_size_bytes'),
                    has_stderr=bool(tool_row.get('has_stderr', 0)),
                    sequence_index=tool_row.get('sequence_index') or 0,
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

            # 5. Sync file accesses and build co-access relationships
            _sync_file_accesses(session_id, reader, writer)

            # 6. Sync subagent data
            _sync_subagent_data(session_id, reader, writer)

            # 7. Create metrics summary
            writer.create_metrics_summary(session_id)

            # 8. Mark session as synced in SQLite
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


def _sync_subagent_data(session_id: str, reader: CLISqliteReader,
                        writer: CLINeo4jWriter):
    """
    Sync subagent sessions and their tool calls to Neo4j.

    Args:
        session_id: Parent session identifier
        reader: SQLite reader instance
        writer: Neo4j writer instance
    """
    # Get distinct subagent IDs for this session
    agent_ids = reader.get_distinct_agent_ids(session_id)

    if not agent_ids:
        return

    for agent_id in agent_ids:
        # Get all tool calls for this subagent
        tool_calls = reader.get_subagent_tool_calls(agent_id)

        if not tool_calls:
            continue

        # Determine subagent_type from first tool call (if available)
        subagent_type = None
        transcript_path = None
        for tc in tool_calls:
            if tc.get('subagent_type'):
                subagent_type = tc['subagent_type']
                break

        # Get timestamp from last tool call
        last_timestamp = _parse_timestamp(tool_calls[-1].get('timestamp', ''))

        # Create SubagentSession node
        writer.create_subagent_session(
            parent_session_id=session_id,
            agent_id=agent_id,
            subagent_type=subagent_type or 'unknown',
            transcript_path=transcript_path or '',
            tool_count=len(tool_calls),
            timestamp=last_timestamp,
        )

        # Create tool call nodes for each subagent tool
        for tool_row in tool_calls:
            # Parse raw_json if available
            raw_data = {}
            if tool_row.get('raw_json'):
                try:
                    raw_data = json.loads(tool_row['raw_json'])
                except json.JSONDecodeError:
                    pass

            tool_data = {
                'tool_name': tool_row.get('tool_name'),
                'tool_input': raw_data.get('tool_input') or {},
                'tool_use_id': tool_row.get('tool_use_id'),
                'timestamp': tool_row.get('timestamp'),
                'tool_result': raw_data.get('tool_result'),
                'success': bool(tool_row.get('success', 1)),
            }

            writer.create_subagent_tool_call(
                parent_session_id=session_id,
                agent_id=agent_id,
                tool_data=tool_data,
                subagent_type=subagent_type,
            )


def _sync_file_accesses(session_id: str, reader: CLISqliteReader,
                        writer: CLINeo4jWriter):
    """
    Sync file access data to Neo4j and build co-access relationships.

    Creates UnifiedFile nodes for all accessed files, links them to tool calls,
    and establishes CO_ACCESSED_WITH relationships between files accessed in
    the same session.

    Args:
        session_id: Session identifier
        reader: SQLite reader instance
        writer: Neo4j writer instance
    """
    # Get all file accesses for this session
    file_accesses = reader.get_file_accesses(session_id)

    if not file_accesses:
        return

    # Collect unique file paths for co-access relationship building
    unique_file_paths = set()

    for access_row in file_accesses:
        # Create FileAccessEvent from the row data
        file_event = FileAccessEvent(
            session_id=session_id,
            file_path=access_row.get('file_path') or '',
            normalized_path=access_row.get('normalized_path') or '',
            access_mode=access_row.get('access_mode') or 'read',
            timestamp=_parse_timestamp(access_row.get('timestamp', '')),
            tool_name=access_row.get('tool_name') or 'unknown',
            event_id=access_row.get('event_id'),
            project_root=access_row.get('project_root'),
            is_primary_target=bool(access_row.get('is_primary_target', 1)),
            is_glob_expansion=bool(access_row.get('is_glob_expansion', 0)),
        )

        # Parse line_numbers if present (stored as JSON)
        line_numbers_str = access_row.get('line_numbers')
        if line_numbers_str:
            try:
                file_event.line_numbers = json.loads(line_numbers_str)
            except (json.JSONDecodeError, TypeError):
                file_event.line_numbers = []

        # Skip if no valid path
        if not file_event.normalized_path:
            continue

        # Track unique paths for co-access
        unique_file_paths.add(file_event.normalized_path)

        # Merge/create UnifiedFile node
        writer.merge_unified_file(
            file_path=file_event.normalized_path,
            access_mode=file_event.access_mode,
            project_root=file_event.project_root,
        )

        # Create session-level access relationship
        writer.create_session_file_access(
            session_id=session_id,
            file_path=file_event.normalized_path,
            access_mode=file_event.access_mode,
            timestamp=file_event.timestamp.isoformat(),
        )

    # Build co-access relationships between files in this session
    if len(unique_file_paths) > 1:
        writer.update_co_access_relationships(session_id, list(unique_file_paths))

    # Mark file accesses as synced
    reader.mark_file_accesses_synced(session_id)


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


def run_unified_file_migration() -> dict:
    """
    Run the one-time migration to convert File nodes to UnifiedFile nodes.

    This migrates existing File nodes and links them to any matching FileNode
    nodes by path. Should be run once after upgrading to the unified file model.

    Returns:
        Dictionary with migration statistics
    """
    if not is_neo4j_available():
        print("[Hook] Neo4j not available, cannot run migration", file=sys.stderr)
        return {'success': False, 'error': 'Neo4j not available'}

    try:
        with CLINeo4jWriter() as writer:
            stats = writer.migrate_file_to_unified()
            return stats

    except Exception as e:
        print(f"[Hook] Migration failed: {e}", file=sys.stderr)
        return {'success': False, 'error': str(e)}


def sync_unsynced_file_accesses() -> int:
    """
    Sync all unsynced file accesses from SQLite to Neo4j.

    This is useful for catching up file access data that may have been
    logged before Neo4j was available.

    Returns:
        Number of file accesses synced
    """
    if not is_neo4j_available():
        print("[Hook] Neo4j not available, skipping file access sync", file=sys.stderr)
        return 0

    synced_count = 0

    try:
        with CLISqliteReader() as reader, CLINeo4jWriter() as writer:
            unsynced = reader.get_unsynced_file_accesses()

            for access_row in unsynced:
                normalized_path = access_row.get('normalized_path')
                if not normalized_path:
                    continue

                metadata = {
                    'access_mode': access_row.get('access_mode') or 'read',
                    'project_root': access_row.get('project_root'),
                    'tool_name': access_row.get('tool_name'),
                }

                writer.merge_unified_file(normalized_path, metadata)
                synced_count += 1

            # Mark all as synced by session
            session_ids = set(a.get('session_id') for a in unsynced if a.get('session_id'))
            for session_id in session_ids:
                reader.mark_file_accesses_synced(session_id)

    except Exception as e:
        print(f"[Hook] File access sync failed: {e}", file=sys.stderr)

    return synced_count


if __name__ == "__main__":
    # CLI for manual sync
    import argparse

    parser = argparse.ArgumentParser(description="Sync sessions from SQLite to Neo4j")
    parser.add_argument("--session", "-s", help="Specific session ID to sync")
    parser.add_argument("--all", "-a", action="store_true", help="Sync all unsynced sessions")
    parser.add_argument("--migrate", "-m", action="store_true",
                        help="Run UnifiedFile migration (one-time)")
    parser.add_argument("--files", "-f", action="store_true",
                        help="Sync unsynced file accesses")

    args = parser.parse_args()

    if args.session:
        success = sync_session_to_neo4j(args.session)
        print(f"Session {args.session}: {'synced' if success else 'failed'}")
    elif args.all:
        count = sync_all_unsynced_sessions()
        print(f"Synced {count} sessions")
    elif args.migrate:
        stats = run_unified_file_migration()
        print(f"Migration result: {stats}")
    elif args.files:
        count = sync_unsynced_file_accesses()
        print(f"Synced {count} file accesses")
    else:
        parser.print_help()
