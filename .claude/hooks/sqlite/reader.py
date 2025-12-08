"""SQLite reader for retrieving session data to sync to Neo4j."""

import sqlite3
from typing import List, Optional

import sys
from pathlib import Path

# Add hooks root to path for imports
HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from core.config import get_db_path


class CLISqliteReader:
    """Reads session data from SQLite for Neo4j sync."""

    def __init__(self):
        self.db_path = get_db_path()
        self.conn = None

    def __enter__(self):
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        return self

    def __exit__(self, *args):
        if self.conn:
            self.conn.close()

    def get_session_events(self, session_id: str) -> List[dict]:
        """Get all events for a session, ordered by timestamp.

        Args:
            session_id: The session identifier

        Returns:
            List of event dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM events
            WHERE session_id = ?
            ORDER BY timestamp ASC
        """, (session_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_session_start_event(self, session_id: str) -> Optional[dict]:
        """Get SessionStart event for a session.

        Args:
            session_id: The session identifier

        Returns:
            Event dictionary or None
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM events
            WHERE session_id = ? AND event_type = 'SessionStart'
            LIMIT 1
        """, (session_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_session_end_event(self, session_id: str) -> Optional[dict]:
        """Get SessionEnd event for a session.

        Args:
            session_id: The session identifier

        Returns:
            Event dictionary or None
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM events
            WHERE session_id = ? AND event_type = 'SessionEnd'
            LIMIT 1
        """, (session_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_prompts(self, session_id: str) -> List[dict]:
        """Get all prompts for a session.

        Args:
            session_id: The session identifier

        Returns:
            List of prompt event dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM events
            WHERE session_id = ? AND event_type = 'UserPromptSubmit'
            ORDER BY timestamp ASC
        """, (session_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_tool_calls(self, session_id: str) -> List[dict]:
        """Get all PostToolUse events for a session.

        Args:
            session_id: The session identifier

        Returns:
            List of tool call event dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM events
            WHERE session_id = ? AND event_type = 'PostToolUse'
            ORDER BY timestamp ASC
        """, (session_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_session_summary(self, session_id: str) -> dict:
        """Get aggregated statistics for a session.

        Args:
            session_id: The session identifier

        Returns:
            Dictionary with prompt_count, tool_count, tool_usage, error_count
        """
        cursor = self.conn.cursor()

        # Count prompts
        cursor.execute("""
            SELECT COUNT(*) as prompt_count
            FROM events WHERE session_id = ? AND event_type = 'UserPromptSubmit'
        """, (session_id,))
        prompt_count = cursor.fetchone()[0]

        # Count and aggregate tool calls
        cursor.execute("""
            SELECT
                COUNT(*) as tool_count,
                tool_name,
                AVG(duration_ms) as avg_duration,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count
            FROM events
            WHERE session_id = ? AND event_type = 'PostToolUse'
            GROUP BY tool_name
        """, (session_id,))

        tool_usage = {}
        total_tool_count = 0
        total_errors = 0

        for row in cursor.fetchall():
            tool_name = row[1]
            count = row[0]
            tool_usage[tool_name] = count
            total_tool_count += count
            total_errors += row[3] or 0

        return {
            'prompt_count': prompt_count,
            'tool_count': total_tool_count,
            'tool_usage': tool_usage,
            'error_count': total_errors
        }

    def get_unsynced_sessions(self) -> List[str]:
        """Get list of session IDs that haven't been synced to Neo4j.

        Returns:
            List of session IDs with unsynced events
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT DISTINCT session_id
            FROM events
            WHERE synced_to_neo4j = 0
            ORDER BY timestamp ASC
        """)
        return [row[0] for row in cursor.fetchall()]

    def is_session_complete(self, session_id: str) -> bool:
        """Check if a session has a SessionEnd event.

        Args:
            session_id: The session identifier

        Returns:
            True if session has ended, False otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM events
            WHERE session_id = ? AND event_type = 'SessionEnd'
        """, (session_id,))
        return cursor.fetchone()[0] > 0

    def mark_session_synced(self, session_id: str):
        """Mark all events for a session as synced to Neo4j.

        Args:
            session_id: The session identifier
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE events SET synced_to_neo4j = 1
            WHERE session_id = ?
        """, (session_id,))
        self.conn.commit()

    def get_session_ids_by_date_range(self, start_date: str, end_date: str) -> List[str]:
        """Get session IDs within a date range.

        Args:
            start_date: ISO format start date
            end_date: ISO format end date

        Returns:
            List of session IDs
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT DISTINCT session_id
            FROM events
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
        """, (start_date, end_date))
        return [row[0] for row in cursor.fetchall()]

    # -------------------------------------------------------------------------
    # Subagent Query Methods
    # -------------------------------------------------------------------------

    def get_subagent_stops(self, session_id: str) -> List[dict]:
        """Get all SubagentStop events for a session.

        Args:
            session_id: The parent session identifier

        Returns:
            List of SubagentStop event dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM events
            WHERE session_id = ? AND event_type = 'SubagentStop'
            ORDER BY timestamp ASC
        """, (session_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_subagent_tool_calls(self, agent_id: str) -> List[dict]:
        """Get all tool calls made by a specific subagent.

        Args:
            agent_id: The subagent's session ID

        Returns:
            List of SubagentToolCall event dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM events
            WHERE agent_id = ? AND event_type = 'SubagentToolCall'
            ORDER BY timestamp ASC
        """, (agent_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_subagent_tool_calls_by_parent(self, parent_session_id: str) -> List[dict]:
        """Get all subagent tool calls for a parent session.

        Args:
            parent_session_id: The parent session identifier

        Returns:
            List of SubagentToolCall event dictionaries from all subagents
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM events
            WHERE parent_session_id = ? AND event_type = 'SubagentToolCall'
            ORDER BY timestamp ASC
        """, (parent_session_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_distinct_agent_ids(self, parent_session_id: str) -> List[str]:
        """Get distinct subagent IDs for a parent session.

        Args:
            parent_session_id: The parent session identifier

        Returns:
            List of unique agent_id values
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT DISTINCT agent_id FROM events
            WHERE parent_session_id = ? AND agent_id IS NOT NULL
        """, (parent_session_id,))
        return [row[0] for row in cursor.fetchall()]

    def get_subagent_summary(self, parent_session_id: str) -> dict:
        """Get aggregated statistics for subagent activity in a session.

        Args:
            parent_session_id: The parent session identifier

        Returns:
            Dictionary with subagent_count, total_tool_calls, tool_usage
        """
        cursor = self.conn.cursor()

        # Count distinct subagents
        cursor.execute("""
            SELECT COUNT(DISTINCT agent_id) as subagent_count
            FROM events
            WHERE parent_session_id = ? AND is_subagent_event = 1
        """, (parent_session_id,))
        subagent_count = cursor.fetchone()[0]

        # Count and aggregate subagent tool calls
        cursor.execute("""
            SELECT
                COUNT(*) as tool_count,
                tool_name,
                subagent_type,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count
            FROM events
            WHERE parent_session_id = ? AND event_type = 'SubagentToolCall'
            GROUP BY tool_name
        """, (parent_session_id,))

        tool_usage = {}
        total_tool_count = 0
        total_errors = 0

        for row in cursor.fetchall():
            tool_name = row[1]
            count = row[0]
            tool_usage[tool_name] = count
            total_tool_count += count
            total_errors += row[3] or 0

        return {
            'subagent_count': subagent_count,
            'total_tool_calls': total_tool_count,
            'tool_usage': tool_usage,
            'error_count': total_errors
        }

    # -------------------------------------------------------------------------
    # File Access Query Methods (v7)
    # -------------------------------------------------------------------------

    def get_file_accesses(self, session_id: str) -> List[dict]:
        """Get all file access events for a session.

        Args:
            session_id: The session identifier

        Returns:
            List of file access dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM file_access_log
            WHERE session_id = ?
            ORDER BY timestamp ASC
        """, (session_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_unsynced_file_accesses(self) -> List[dict]:
        """Get file accesses not yet synced to Neo4j.

        Returns:
            List of unsynced file access dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM file_access_log
            WHERE synced_to_neo4j = 0
            ORDER BY timestamp ASC
        """)
        return [dict(row) for row in cursor.fetchall()]

    def get_session_files(self, session_id: str) -> List[str]:
        """Get unique file paths accessed in a session.

        Args:
            session_id: The session identifier

        Returns:
            List of unique normalized file paths
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT DISTINCT normalized_path FROM file_access_log
            WHERE session_id = ?
            ORDER BY normalized_path
        """, (session_id,))
        return [row[0] for row in cursor.fetchall()]

    def get_file_access_summary(self, session_id: str) -> dict:
        """Get file access statistics for a session.

        Args:
            session_id: The session identifier

        Returns:
            Dictionary with access counts by mode, project_root, etc.
        """
        cursor = self.conn.cursor()

        # Total file accesses
        cursor.execute("""
            SELECT COUNT(*) as total_accesses,
                   COUNT(DISTINCT normalized_path) as unique_files
            FROM file_access_log
            WHERE session_id = ?
        """, (session_id,))
        row = cursor.fetchone()
        total_accesses = row[0]
        unique_files = row[1]

        # Access counts by mode
        cursor.execute("""
            SELECT access_mode, COUNT(*) as count
            FROM file_access_log
            WHERE session_id = ?
            GROUP BY access_mode
        """, (session_id,))
        by_mode = {row[0]: row[1] for row in cursor.fetchall()}

        # Project roots accessed
        cursor.execute("""
            SELECT DISTINCT project_root
            FROM file_access_log
            WHERE session_id = ? AND project_root IS NOT NULL
        """, (session_id,))
        project_roots = [row[0] for row in cursor.fetchall()]

        return {
            'total_accesses': total_accesses,
            'unique_files': unique_files,
            'by_mode': by_mode,
            'project_roots': project_roots
        }

    def get_co_accessed_files(self, file_path: str, min_count: int = 2) -> List[dict]:
        """Find files frequently accessed together with given file.

        Args:
            file_path: The normalized file path to find co-accesses for
            min_count: Minimum co-access count threshold

        Returns:
            List of dicts with file_path and co_access_count
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT f2.normalized_path, COUNT(DISTINCT f2.session_id) as co_access_count
            FROM file_access_log f1
            JOIN file_access_log f2 ON f1.session_id = f2.session_id
            WHERE f1.normalized_path = ?
              AND f2.normalized_path != ?
            GROUP BY f2.normalized_path
            HAVING co_access_count >= ?
            ORDER BY co_access_count DESC
        """, (file_path, file_path, min_count))
        return [{'file_path': row[0], 'co_access_count': row[1]} for row in cursor.fetchall()]

    def get_files_by_project(self, project_root: str) -> List[dict]:
        """Get all files accessed within a project.

        Args:
            project_root: The project root directory

        Returns:
            List of dicts with normalized_path, access_count, access_modes
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                normalized_path,
                COUNT(*) as access_count,
                GROUP_CONCAT(DISTINCT access_mode) as access_modes,
                COUNT(DISTINCT session_id) as session_count
            FROM file_access_log
            WHERE project_root = ?
            GROUP BY normalized_path
            ORDER BY access_count DESC
        """, (project_root,))
        return [{
            'normalized_path': row[0],
            'access_count': row[1],
            'access_modes': row[2].split(',') if row[2] else [],
            'session_count': row[3]
        } for row in cursor.fetchall()]

    def mark_file_accesses_synced(self, session_id: str):
        """Mark all file access events for a session as synced.

        Args:
            session_id: The session identifier
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE file_access_log SET synced_to_neo4j = 1
            WHERE session_id = ?
        """, (session_id,))
        self.conn.commit()

    def get_glob_expansions(self, session_id: str) -> List[dict]:
        """Get all glob expansion results for a session.

        Args:
            session_id: The session identifier

        Returns:
            List of file accesses that came from glob expansion
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM file_access_log
            WHERE session_id = ? AND is_glob_expansion = 1
            ORDER BY timestamp ASC
        """, (session_id,))
        return [dict(row) for row in cursor.fetchall()]
