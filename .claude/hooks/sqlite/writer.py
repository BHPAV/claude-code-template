"""SQLite writer for Claude Code CLI hooks - Enhanced version with field extraction."""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

import sys
from pathlib import Path

# Add hooks root to path for imports
HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from core.config import get_db_path
from core.helpers import (
    classify_tool,
    extract_file_path,
    extract_command,
    extract_pattern,
    extract_url,
    extract_subagent_type,
    compute_prompt_hash,
    count_words,
    detect_success,
    get_output_size,
    get_environment_context,
    sanitize_tool_input,
    normalize_path,
)


class CLISqliteWriter:
    """Context manager for writing hook events to SQLite with field extraction."""

    SCHEMA_VERSION = 4  # Bumped for subagent_type column

    def __init__(self):
        self.db_path = get_db_path()
        self.conn = None

    def __enter__(self):
        self.conn = sqlite3.connect(str(self.db_path))
        self._ensure_schema()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()
        return False

    def _ensure_schema(self):
        """Create/migrate tables and indexes."""
        cursor = self.conn.cursor()

        # Check if events table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
        table_exists = cursor.fetchone() is not None

        if table_exists:
            # Check if migration needed by looking for new columns
            cursor.execute("PRAGMA table_info(events)")
            columns = {row[1] for row in cursor.fetchall()}

            if 'tool_use_id' not in columns:
                self._migrate_schema_v1_to_v2(cursor)
            if 'synced_to_neo4j' not in columns:
                self._migrate_schema_v2_to_v3(cursor)
            if 'subagent_type' not in columns:
                self._migrate_schema_v3_to_v4(cursor)
        else:
            self._create_schema_v4(cursor)

        self.conn.commit()

    def _create_schema_v4(self, cursor):
        """Create the enhanced schema (v4) with subagent_type tracking."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                raw_json TEXT NOT NULL,

                transcript_path TEXT,
                cwd TEXT,
                permission_mode TEXT,

                git_branch TEXT,
                platform TEXT,
                python_version TEXT,

                tool_use_id TEXT,
                tool_name TEXT,
                tool_category TEXT,
                subagent_type TEXT,

                file_path TEXT,
                command TEXT,
                pattern TEXT,
                url TEXT,

                duration_ms REAL,

                success INTEGER,
                error_message TEXT,
                has_stderr INTEGER,
                was_interrupted INTEGER,

                output_size_bytes INTEGER,

                prompt_text TEXT,
                prompt_hash TEXT,
                prompt_length INTEGER,
                prompt_word_count INTEGER,

                synced_to_neo4j INTEGER DEFAULT 0
            )
        """)

        # Cache table for Pre/Post tool matching
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tool_call_cache (
                tool_use_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                start_timestamp TEXT NOT NULL,
                tool_input_json TEXT
            )
        """)

        # Cache table for session duration
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_cache (
                session_id TEXT PRIMARY KEY,
                start_timestamp TEXT NOT NULL,
                cwd TEXT,
                git_branch TEXT,
                platform TEXT,
                python_version TEXT
            )
        """)

        self._create_indexes(cursor)

    def _migrate_schema_v1_to_v2(self, cursor):
        """Migrate from v1 (basic) to v2 (enhanced) schema."""
        new_columns = [
            ('transcript_path', 'TEXT'),
            ('cwd', 'TEXT'),
            ('permission_mode', 'TEXT'),
            ('git_branch', 'TEXT'),
            ('platform', 'TEXT'),
            ('python_version', 'TEXT'),
            ('tool_use_id', 'TEXT'),
            ('tool_name', 'TEXT'),
            ('tool_category', 'TEXT'),
            ('file_path', 'TEXT'),
            ('command', 'TEXT'),
            ('pattern', 'TEXT'),
            ('url', 'TEXT'),
            ('duration_ms', 'REAL'),
            ('success', 'INTEGER'),
            ('error_message', 'TEXT'),
            ('has_stderr', 'INTEGER'),
            ('was_interrupted', 'INTEGER'),
            ('output_size_bytes', 'INTEGER'),
            ('prompt_text', 'TEXT'),
            ('prompt_hash', 'TEXT'),
            ('prompt_length', 'INTEGER'),
            ('prompt_word_count', 'INTEGER'),
        ]

        for col_name, col_type in new_columns:
            try:
                cursor.execute(f"ALTER TABLE events ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass  # Column already exists

        # Create cache tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tool_call_cache (
                tool_use_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                start_timestamp TEXT NOT NULL,
                tool_input_json TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_cache (
                session_id TEXT PRIMARY KEY,
                start_timestamp TEXT NOT NULL,
                cwd TEXT,
                git_branch TEXT,
                platform TEXT,
                python_version TEXT
            )
        """)

        self._create_indexes(cursor)

        # Backfill existing data
        self._backfill_existing_data(cursor)

    def _migrate_schema_v2_to_v3(self, cursor):
        """Migrate from v2 to v3 - add synced_to_neo4j column."""
        try:
            cursor.execute("ALTER TABLE events ADD COLUMN synced_to_neo4j INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Create index for sync queries
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_synced ON events(synced_to_neo4j)")
        except sqlite3.OperationalError:
            pass

    def _migrate_schema_v3_to_v4(self, cursor):
        """Migrate from v3 to v4 - add subagent_type column."""
        try:
            cursor.execute("ALTER TABLE events ADD COLUMN subagent_type TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Create index for subagent_type queries
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_subagent_type ON events(subagent_type)")
        except sqlite3.OperationalError:
            pass

    def _create_indexes(self, cursor):
        """Create all indexes for efficient querying."""
        indexes = [
            ('idx_events_session', 'events(session_id)'),
            ('idx_events_type', 'events(event_type)'),
            ('idx_events_timestamp', 'events(timestamp)'),
            ('idx_events_tool_name', 'events(tool_name)'),
            ('idx_events_tool_category', 'events(tool_category)'),
            ('idx_events_tool_use_id', 'events(tool_use_id)'),
            ('idx_events_file_path', 'events(file_path)'),
            ('idx_events_success', 'events(success)'),
            ('idx_events_prompt_hash', 'events(prompt_hash)'),
            ('idx_events_session_type', 'events(session_id, event_type)'),
            ('idx_events_session_timestamp', 'events(session_id, timestamp)'),
            ('idx_events_synced', 'events(synced_to_neo4j)'),
            ('idx_events_subagent_type', 'events(subagent_type)'),
        ]

        for idx_name, idx_def in indexes:
            try:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_def}")
            except sqlite3.OperationalError:
                pass  # Index already exists

    def _backfill_existing_data(self, cursor):
        """Backfill extracted fields from existing raw_json data."""
        cursor.execute("SELECT id, event_type, raw_json FROM events WHERE tool_name IS NULL AND tool_use_id IS NULL")
        rows = cursor.fetchall()

        for row_id, event_type, raw_json_str in rows:
            try:
                data = json.loads(raw_json_str)
                updates = self._extract_fields_from_data(event_type, data)

                if updates:
                    set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
                    cursor.execute(
                        f"UPDATE events SET {set_clause} WHERE id = ?",
                        list(updates.values()) + [row_id]
                    )
            except (json.JSONDecodeError, Exception):
                pass  # Skip problematic rows

    def _extract_fields_from_data(self, event_type: str, data: dict) -> dict:
        """Extract fields from raw event data for backfill."""
        updates = {}

        # Common fields
        if data.get('transcript_path'):
            updates['transcript_path'] = data['transcript_path']
        if data.get('cwd'):
            updates['cwd'] = data['cwd']
        if data.get('permission_mode'):
            updates['permission_mode'] = data['permission_mode']

        if event_type in ('PreToolUse', 'PostToolUse'):
            tool_name = data.get('tool_name') or data.get('toolName')
            tool_input = data.get('tool_input') or data.get('toolInput') or {}

            updates['tool_use_id'] = data.get('tool_use_id') or data.get('toolUseId')
            updates['tool_name'] = tool_name
            if tool_name:
                updates['tool_category'] = classify_tool(tool_name)
                updates['subagent_type'] = extract_subagent_type(tool_name, tool_input)
                updates['file_path'] = normalize_path(extract_file_path(tool_name, tool_input))
                updates['command'] = extract_command(tool_name, tool_input)
                updates['pattern'] = extract_pattern(tool_name, tool_input)
                updates['url'] = extract_url(tool_name, tool_input)

            if event_type == 'PostToolUse':
                tool_response = data.get('tool_response') or data.get('toolOutput')
                success, error_msg, has_stderr, interrupted = detect_success(tool_response)
                updates['success'] = 1 if success else 0
                updates['error_message'] = error_msg
                updates['has_stderr'] = 1 if has_stderr else 0
                updates['was_interrupted'] = 1 if interrupted else 0
                updates['output_size_bytes'] = get_output_size(tool_response)

        elif event_type == 'UserPromptSubmit':
            prompt = data.get('prompt', '')
            if prompt:
                updates['prompt_text'] = prompt[:1000]
                updates['prompt_hash'] = compute_prompt_hash(prompt)
                updates['prompt_length'] = len(prompt)
                updates['prompt_word_count'] = count_words(prompt)

        # Filter out None values
        return {k: v for k, v in updates.items() if v is not None}

    # -------------------------------------------------------------------------
    # Cache Operations
    # -------------------------------------------------------------------------

    def cache_pre_tool_use(self, tool_use_id: str, session_id: str,
                          tool_name: str, tool_input: dict):
        """Cache PreToolUse event for duration calculation."""
        if not tool_use_id:
            return

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO tool_call_cache
            (tool_use_id, session_id, tool_name, start_timestamp, tool_input_json)
            VALUES (?, ?, ?, ?, ?)
        """, (
            tool_use_id,
            session_id,
            tool_name or 'unknown',
            datetime.now(timezone.utc).isoformat(),
            json.dumps(sanitize_tool_input(tool_input), default=str)
        ))
        self.conn.commit()

    def get_cached_pre_tool_use(self, tool_use_id: str) -> Optional[dict]:
        """Retrieve cached PreToolUse data."""
        if not tool_use_id:
            return None

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT session_id, tool_name, start_timestamp, tool_input_json
            FROM tool_call_cache WHERE tool_use_id = ?
        """, (tool_use_id,))
        row = cursor.fetchone()

        if row:
            return {
                'session_id': row[0],
                'tool_name': row[1],
                'start_timestamp': row[2],
                'tool_input': json.loads(row[3]) if row[3] else {}
            }
        return None

    def remove_cached_pre_tool_use(self, tool_use_id: str):
        """Remove cached PreToolUse entry after processing."""
        if not tool_use_id:
            return

        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM tool_call_cache WHERE tool_use_id = ?", (tool_use_id,))
        self.conn.commit()

    def cache_session_start(self, session_id: str, cwd: str, env_context: dict):
        """Cache session start data for duration calculation."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO session_cache
            (session_id, start_timestamp, cwd, git_branch, platform, python_version)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            datetime.now(timezone.utc).isoformat(),
            cwd,
            env_context.get('git_branch'),
            env_context.get('platform'),
            env_context.get('python_version')
        ))
        self.conn.commit()

    def get_cached_session(self, session_id: str) -> Optional[dict]:
        """Retrieve cached session data."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT start_timestamp, cwd, git_branch, platform, python_version
            FROM session_cache WHERE session_id = ?
        """, (session_id,))
        row = cursor.fetchone()

        if row:
            return {
                'start_timestamp': row[0],
                'cwd': row[1],
                'git_branch': row[2],
                'platform': row[3],
                'python_version': row[4]
            }
        return None

    def remove_cached_session(self, session_id: str):
        """Remove cached session entry."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM session_cache WHERE session_id = ?", (session_id,))
        self.conn.commit()

    # -------------------------------------------------------------------------
    # Event Logging
    # -------------------------------------------------------------------------

    def log_event(self, session_id: str, event_type: str, data: dict):
        """Log event with extracted fields (main entry point)."""
        cursor = self.conn.cursor()

        # Get environment context
        env = get_environment_context()

        # Base fields for all events
        fields = {
            'session_id': session_id,
            'event_type': event_type,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'raw_json': json.dumps(data, default=str),
            'transcript_path': data.get('transcript_path'),
            'cwd': data.get('cwd'),
            'permission_mode': data.get('permission_mode'),
            'git_branch': env.get('git_branch'),
            'platform': env.get('platform'),
            'python_version': env.get('python_version'),
            'synced_to_neo4j': 0,
        }

        # Event-specific extraction
        if event_type == 'PreToolUse':
            fields.update(self._process_pre_tool_use(session_id, data))
        elif event_type == 'PostToolUse':
            fields.update(self._process_post_tool_use(data))
        elif event_type == 'UserPromptSubmit':
            fields.update(self._process_prompt(data))
        elif event_type == 'SessionStart':
            self._handle_session_start(session_id, data, env)
        elif event_type == 'SessionEnd':
            fields.update(self._handle_session_end(session_id))

        # Build INSERT statement
        columns = ', '.join(fields.keys())
        placeholders = ', '.join(['?'] * len(fields))

        cursor.execute(
            f"INSERT INTO events ({columns}) VALUES ({placeholders})",
            list(fields.values())
        )
        self.conn.commit()

    def _process_pre_tool_use(self, session_id: str, data: dict) -> dict:
        """Process PreToolUse event and cache for duration calculation."""
        tool_name = data.get('tool_name') or data.get('toolName')
        tool_input = data.get('tool_input') or data.get('toolInput') or {}
        tool_use_id = data.get('tool_use_id') or data.get('toolUseId')

        # Cache for duration calculation
        if tool_use_id:
            self.cache_pre_tool_use(tool_use_id, session_id, tool_name, tool_input)

        return {
            'tool_use_id': tool_use_id,
            'tool_name': tool_name,
            'tool_category': classify_tool(tool_name) if tool_name else None,
            'subagent_type': extract_subagent_type(tool_name, tool_input) if tool_name else None,
            'file_path': normalize_path(extract_file_path(tool_name, tool_input)) if tool_name else None,
            'command': extract_command(tool_name, tool_input) if tool_name else None,
            'pattern': extract_pattern(tool_name, tool_input) if tool_name else None,
            'url': extract_url(tool_name, tool_input) if tool_name else None,
        }

    def _process_post_tool_use(self, data: dict) -> dict:
        """Process PostToolUse event with duration calculation."""
        tool_name = data.get('tool_name') or data.get('toolName')
        tool_input = data.get('tool_input') or data.get('toolInput') or {}
        tool_use_id = data.get('tool_use_id') or data.get('toolUseId')
        tool_response = data.get('tool_response') or data.get('toolOutput')

        # Calculate duration from cached PreToolUse
        duration_ms = None
        if tool_use_id:
            cached = self.get_cached_pre_tool_use(tool_use_id)
            if cached:
                try:
                    start_time = datetime.fromisoformat(cached['start_timestamp'].replace('Z', '+00:00'))
                    end_time = datetime.now(timezone.utc)
                    duration_ms = (end_time - start_time).total_seconds() * 1000
                except (ValueError, TypeError):
                    pass
                self.remove_cached_pre_tool_use(tool_use_id)

        # Analyze success/failure
        success, error_msg, has_stderr, interrupted = detect_success(tool_response)

        return {
            'tool_use_id': tool_use_id,
            'tool_name': tool_name,
            'tool_category': classify_tool(tool_name) if tool_name else None,
            'subagent_type': extract_subagent_type(tool_name, tool_input) if tool_name else None,
            'file_path': normalize_path(extract_file_path(tool_name, tool_input)) if tool_name else None,
            'command': extract_command(tool_name, tool_input) if tool_name else None,
            'pattern': extract_pattern(tool_name, tool_input) if tool_name else None,
            'url': extract_url(tool_name, tool_input) if tool_name else None,
            'duration_ms': duration_ms,
            'success': 1 if success else 0,
            'error_message': error_msg,
            'has_stderr': 1 if has_stderr else 0,
            'was_interrupted': 1 if interrupted else 0,
            'output_size_bytes': get_output_size(tool_response),
        }

    def _process_prompt(self, data: dict) -> dict:
        """Process UserPromptSubmit event."""
        prompt = data.get('prompt', '')
        return {
            'prompt_text': prompt[:1000] if prompt else None,
            'prompt_hash': compute_prompt_hash(prompt) if prompt else None,
            'prompt_length': len(prompt) if prompt else 0,
            'prompt_word_count': count_words(prompt),
        }

    def _handle_session_start(self, session_id: str, data: dict, env: dict):
        """Handle SessionStart - cache session info for duration calculation."""
        cwd = data.get('cwd', '')
        self.cache_session_start(session_id, cwd, env)

    def _handle_session_end(self, session_id: str) -> dict:
        """Handle SessionEnd - calculate session duration."""
        result = {}
        cached = self.get_cached_session(session_id)

        if cached:
            try:
                start_time = datetime.fromisoformat(cached['start_timestamp'].replace('Z', '+00:00'))
                end_time = datetime.now(timezone.utc)
                result['duration_ms'] = (end_time - start_time).total_seconds() * 1000
            except (ValueError, TypeError):
                pass
            self.remove_cached_session(session_id)

        return result
