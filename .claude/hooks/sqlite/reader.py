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
