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
    classify_intent,
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
    # Enhanced file extraction (v7)
    extract_all_file_paths,
    FilePathResult,
)
from core.models import FileAccessEvent


class CLISqliteWriter:
    """Context manager for writing hook events to SQLite with field extraction."""

    SCHEMA_VERSION = 7  # v7: Enhanced file tracking with file_access_log table

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
            if 'parent_session_id' not in columns:
                self._migrate_schema_v4_to_v5(cursor)
            if 'intent_type' not in columns:
                self._migrate_schema_v5_to_v6(cursor)
            if 'file_paths_json' not in columns:
                self._migrate_schema_v6_to_v7(cursor)
        else:
            self._create_schema_v7(cursor)

        self.conn.commit()

    def _create_schema_v7(self, cursor):
        """Create the enhanced schema (v7) with file_access_log table."""
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

                synced_to_neo4j INTEGER DEFAULT 0,

                -- v5: Subagent tracking columns
                parent_session_id TEXT,
                agent_id TEXT,
                is_subagent_event INTEGER DEFAULT 0,

                -- v6: Intent classification and sequence tracking
                intent_type TEXT,
                sequence_index INTEGER DEFAULT 0,

                -- v7: Enhanced file tracking
                file_paths_json TEXT,
                access_mode TEXT,
                project_root TEXT,
                glob_match_count INTEGER
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

        # Cache table for session duration and sequence tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_cache (
                session_id TEXT PRIMARY KEY,
                start_timestamp TEXT NOT NULL,
                cwd TEXT,
                git_branch TEXT,
                platform TEXT,
                python_version TEXT,
                prompt_sequence INTEGER DEFAULT 0,
                tool_sequence INTEGER DEFAULT 0
            )
        """)

        # v7: File access log table for multi-file tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_access_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER REFERENCES events(id),
                session_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                normalized_path TEXT NOT NULL,
                access_mode TEXT NOT NULL,
                project_root TEXT,
                timestamp TEXT NOT NULL,
                tool_name TEXT,
                line_numbers_json TEXT,
                is_primary_target INTEGER DEFAULT 1,
                is_glob_expansion INTEGER DEFAULT 0,
                synced_to_neo4j INTEGER DEFAULT 0
            )
        """)

        self._create_indexes(cursor)
        self._create_file_access_indexes(cursor)

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

    def _migrate_schema_v4_to_v5(self, cursor):
        """Migrate from v4 to v5 - add subagent tracking columns."""
        new_columns = [
            ('parent_session_id', 'TEXT'),
            ('agent_id', 'TEXT'),
            ('is_subagent_event', 'INTEGER DEFAULT 0'),
        ]

        for col_name, col_type in new_columns:
            try:
                cursor.execute(f"ALTER TABLE events ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass  # Column already exists

        # Create indexes for subagent queries
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_parent_session ON events(parent_session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_agent_id ON events(agent_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_is_subagent ON events(is_subagent_event)")
        except sqlite3.OperationalError:
            pass

    def _migrate_schema_v5_to_v6(self, cursor):
        """Migrate from v5 to v6 - add intent_type and sequence_index columns."""
        new_columns = [
            ('intent_type', 'TEXT'),
            ('sequence_index', 'INTEGER DEFAULT 0'),
        ]

        for col_name, col_type in new_columns:
            try:
                cursor.execute(f"ALTER TABLE events ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass  # Column already exists

        # Add sequence columns to session_cache
        for col_name in ['prompt_sequence', 'tool_sequence']:
            try:
                cursor.execute(f"ALTER TABLE session_cache ADD COLUMN {col_name} INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # Column already exists

        # Create indexes
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_intent_type ON events(intent_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_sequence ON events(session_id, sequence_index)")
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
            # v5: Subagent tracking indexes
            ('idx_events_parent_session', 'events(parent_session_id)'),
            ('idx_events_agent_id', 'events(agent_id)'),
            ('idx_events_is_subagent', 'events(is_subagent_event)'),
            # v6: Intent and sequence indexes
            ('idx_events_intent_type', 'events(intent_type)'),
            ('idx_events_sequence', 'events(session_id, sequence_index)'),
            # v7: Enhanced file tracking indexes
            ('idx_events_access_mode', 'events(access_mode)'),
            ('idx_events_project_root', 'events(project_root)'),
        ]

        for idx_name, idx_def in indexes:
            try:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_def}")
            except sqlite3.OperationalError:
                pass  # Index already exists

    def _create_file_access_indexes(self, cursor):
        """Create indexes for file_access_log table."""
        indexes = [
            ('idx_file_access_session', 'file_access_log(session_id)'),
            ('idx_file_access_path', 'file_access_log(normalized_path)'),
            ('idx_file_access_project', 'file_access_log(project_root)'),
            ('idx_file_access_mode', 'file_access_log(access_mode)'),
            ('idx_file_access_synced', 'file_access_log(synced_to_neo4j)'),
            ('idx_file_access_event', 'file_access_log(event_id)'),
        ]

        for idx_name, idx_def in indexes:
            try:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_def}")
            except sqlite3.OperationalError:
                pass  # Index already exists

    def _migrate_schema_v6_to_v7(self, cursor):
        """Migrate from v6 to v7 - add enhanced file tracking columns and file_access_log table."""
        # Add new columns to events table
        new_columns = [
            ('file_paths_json', 'TEXT'),
            ('access_mode', 'TEXT'),
            ('project_root', 'TEXT'),
            ('glob_match_count', 'INTEGER'),
        ]

        for col_name, col_type in new_columns:
            try:
                cursor.execute(f"ALTER TABLE events ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass  # Column already exists

        # Create file_access_log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_access_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER REFERENCES events(id),
                session_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                normalized_path TEXT NOT NULL,
                access_mode TEXT NOT NULL,
                project_root TEXT,
                timestamp TEXT NOT NULL,
                tool_name TEXT,
                line_numbers_json TEXT,
                is_primary_target INTEGER DEFAULT 1,
                is_glob_expansion INTEGER DEFAULT 0,
                synced_to_neo4j INTEGER DEFAULT 0
            )
        """)

        # Create v7 indexes
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_access_mode ON events(access_mode)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_project_root ON events(project_root)")
        except sqlite3.OperationalError:
            pass

        self._create_file_access_indexes(cursor)

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
        """Cache session start data for duration calculation and sequence tracking."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO session_cache
            (session_id, start_timestamp, cwd, git_branch, platform, python_version, prompt_sequence, tool_sequence)
            VALUES (?, ?, ?, ?, ?, ?, 0, 0)
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
            SELECT start_timestamp, cwd, git_branch, platform, python_version, prompt_sequence, tool_sequence
            FROM session_cache WHERE session_id = ?
        """, (session_id,))
        row = cursor.fetchone()

        if row:
            return {
                'start_timestamp': row[0],
                'cwd': row[1],
                'git_branch': row[2],
                'platform': row[3],
                'python_version': row[4],
                'prompt_sequence': row[5] or 0,
                'tool_sequence': row[6] or 0,
            }
        return None

    def get_next_sequence(self, session_id: str, sequence_type: str) -> int:
        """Get next sequence number and increment counter.

        Args:
            session_id: The session identifier
            sequence_type: Either 'prompt' or 'tool'

        Returns:
            Next sequence number (0 if session not cached)
        """
        cursor = self.conn.cursor()
        column = 'prompt_sequence' if sequence_type == 'prompt' else 'tool_sequence'

        # Get current value
        cursor.execute(f"SELECT {column} FROM session_cache WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()

        if row is None:
            return 0

        current_seq = row[0] or 0
        next_seq = current_seq + 1

        # Increment counter
        cursor.execute(f"UPDATE session_cache SET {column} = ? WHERE session_id = ?", (next_seq, session_id))
        self.conn.commit()

        return current_seq  # Return current before increment (0-indexed)

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
            # Track sequence for PreToolUse (will be used by PostToolUse)
            fields['sequence_index'] = self.get_next_sequence(session_id, 'tool')
        elif event_type == 'PostToolUse':
            fields.update(self._process_post_tool_use(data))
            # PostToolUse uses same sequence as its PreToolUse (already incremented)
        elif event_type == 'UserPromptSubmit':
            fields.update(self._process_prompt(data))
            fields['sequence_index'] = self.get_next_sequence(session_id, 'prompt')
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
        """Process PostToolUse event with duration calculation and enhanced file extraction."""
        tool_name = data.get('tool_name') or data.get('toolName')
        tool_input = data.get('tool_input') or data.get('toolInput') or {}
        tool_use_id = data.get('tool_use_id') or data.get('toolUseId')
        tool_response = data.get('tool_response') or data.get('toolOutput')
        cwd = data.get('cwd')

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

        # Enhanced file path extraction (v7)
        file_result = extract_all_file_paths(tool_name, tool_input, tool_response, cwd) if tool_name else FilePathResult()

        # Collect all file paths (primary + related)
        all_paths = []
        if file_result.primary_path:
            all_paths.append(file_result.primary_path)
        all_paths.extend(file_result.related_paths)

        return {
            'tool_use_id': tool_use_id,
            'tool_name': tool_name,
            'tool_category': classify_tool(tool_name) if tool_name else None,
            'subagent_type': extract_subagent_type(tool_name, tool_input) if tool_name else None,
            'file_path': file_result.primary_path,  # Backward compat: primary path
            'command': extract_command(tool_name, tool_input) if tool_name else None,
            'pattern': extract_pattern(tool_name, tool_input) if tool_name else None,
            'url': extract_url(tool_name, tool_input) if tool_name else None,
            'duration_ms': duration_ms,
            'success': 1 if success else 0,
            'error_message': error_msg,
            'has_stderr': 1 if has_stderr else 0,
            'was_interrupted': 1 if interrupted else 0,
            'output_size_bytes': get_output_size(tool_response),
            # v7: Enhanced file tracking
            'file_paths_json': json.dumps(all_paths) if all_paths else None,
            'access_mode': file_result.access_mode,
            'project_root': file_result.project_root,
            'glob_match_count': len(file_result.related_paths) if file_result.is_glob_expansion else None,
        }

    def _process_prompt(self, data: dict) -> dict:
        """Process UserPromptSubmit event with intent classification."""
        prompt = data.get('prompt', '')
        return {
            'prompt_text': prompt[:1000] if prompt else None,
            'prompt_hash': compute_prompt_hash(prompt) if prompt else None,
            'prompt_length': len(prompt) if prompt else 0,
            'prompt_word_count': count_words(prompt),
            'intent_type': classify_intent(prompt) if prompt else None,
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

    # -------------------------------------------------------------------------
    # Subagent Tool Call Logging
    # -------------------------------------------------------------------------

    def log_subagent_tool_call(self, parent_session_id: str, agent_id: str,
                               tool_call: dict, subagent_type: Optional[str] = None):
        """Log a tool call extracted from a subagent's transcript.

        Args:
            parent_session_id: The session ID of the parent (main agent)
            agent_id: The subagent's session ID
            tool_call: Dict with tool_name, tool_input, tool_use_id, timestamp,
                      and optionally tool_result
            subagent_type: The type of subagent (Explore, Plan, etc.)
        """
        cursor = self.conn.cursor()
        env = get_environment_context()

        tool_name = tool_call.get('tool_name')
        tool_input = tool_call.get('tool_input') or {}
        tool_result = tool_call.get('tool_result')

        # Analyze success if we have a result
        success, error_msg, has_stderr, interrupted = (True, None, False, False)
        if tool_result is not None:
            success, error_msg, has_stderr, interrupted = detect_success(tool_result)

        fields = {
            'session_id': agent_id,  # The subagent's own session
            'parent_session_id': parent_session_id,
            'agent_id': agent_id,
            'is_subagent_event': 1,
            'event_type': 'SubagentToolCall',
            'timestamp': tool_call.get('timestamp', datetime.now(timezone.utc).isoformat()),
            'raw_json': json.dumps(tool_call, default=str),
            'tool_use_id': tool_call.get('tool_use_id'),
            'tool_name': tool_name,
            'tool_category': classify_tool(tool_name) if tool_name else None,
            'subagent_type': subagent_type,
            'file_path': normalize_path(extract_file_path(tool_name, tool_input)) if tool_name else None,
            'command': extract_command(tool_name, tool_input) if tool_name else None,
            'pattern': extract_pattern(tool_name, tool_input) if tool_name else None,
            'url': extract_url(tool_name, tool_input) if tool_name else None,
            'success': 1 if success else 0,
            'error_message': error_msg,
            'has_stderr': 1 if has_stderr else 0,
            'was_interrupted': 1 if interrupted else 0,
            'output_size_bytes': get_output_size(tool_result) if tool_result else None,
            'git_branch': env.get('git_branch'),
            'platform': env.get('platform'),
            'python_version': env.get('python_version'),
            'synced_to_neo4j': 0,
        }

        columns = ', '.join(fields.keys())
        placeholders = ', '.join(['?'] * len(fields))

        cursor.execute(
            f"INSERT INTO events ({columns}) VALUES ({placeholders})",
            list(fields.values())
        )
        self.conn.commit()

    # -------------------------------------------------------------------------
    # File Access Logging (v7)
    # -------------------------------------------------------------------------

    def log_file_access(self, event_id: int, session_id: str, tool_name: str,
                        file_result: FilePathResult, timestamp: str):
        """Log individual file access events to dedicated table.

        Args:
            event_id: Reference to parent events table row
            session_id: The session identifier
            tool_name: Name of the tool that accessed the file
            file_result: FilePathResult from extract_all_file_paths()
            timestamp: ISO format timestamp
        """
        if not file_result.primary_path and not file_result.related_paths:
            return

        cursor = self.conn.cursor()

        # Log primary path
        if file_result.primary_path:
            cursor.execute("""
                INSERT INTO file_access_log
                (event_id, session_id, file_path, normalized_path, access_mode,
                 project_root, timestamp, tool_name, is_primary_target, is_glob_expansion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0)
            """, (
                event_id,
                session_id,
                file_result.primary_path,  # Original path
                file_result.primary_path,  # Already normalized
                file_result.access_mode,
                file_result.project_root,
                timestamp,
                tool_name,
            ))

        # Log related paths (from glob/grep expansion)
        for related_path in file_result.related_paths:
            cursor.execute("""
                INSERT INTO file_access_log
                (event_id, session_id, file_path, normalized_path, access_mode,
                 project_root, timestamp, tool_name, is_primary_target, is_glob_expansion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """, (
                event_id,
                session_id,
                related_path,
                related_path,
                file_result.access_mode,
                file_result.project_root,
                timestamp,
                tool_name,
                1 if file_result.is_glob_expansion else 0,
            ))

        self.conn.commit()

    def log_file_access_from_event(self, session_id: str, tool_name: str,
                                   tool_input: dict, tool_output: Any,
                                   cwd: Optional[str], timestamp: str) -> Optional[int]:
        """Extract and log file accesses from a tool event.

        Convenience method that combines extraction and logging.

        Args:
            session_id: The session identifier
            tool_name: Name of the tool
            tool_input: Tool input parameters
            tool_output: Tool output/response
            cwd: Current working directory
            timestamp: ISO format timestamp

        Returns:
            Number of file access records created, or None if no files
        """
        file_result = extract_all_file_paths(tool_name, tool_input, tool_output, cwd)

        if not file_result.primary_path and not file_result.related_paths:
            return None

        cursor = self.conn.cursor()
        count = 0

        # Log primary path
        if file_result.primary_path:
            cursor.execute("""
                INSERT INTO file_access_log
                (session_id, file_path, normalized_path, access_mode,
                 project_root, timestamp, tool_name, is_primary_target, is_glob_expansion)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0)
            """, (
                session_id,
                file_result.primary_path,
                file_result.primary_path,
                file_result.access_mode,
                file_result.project_root,
                timestamp,
                tool_name,
            ))
            count += 1

        # Log related paths
        for related_path in file_result.related_paths:
            cursor.execute("""
                INSERT INTO file_access_log
                (session_id, file_path, normalized_path, access_mode,
                 project_root, timestamp, tool_name, is_primary_target, is_glob_expansion)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
            """, (
                session_id,
                related_path,
                related_path,
                file_result.access_mode,
                file_result.project_root,
                timestamp,
                tool_name,
                1 if file_result.is_glob_expansion else 0,
            ))
            count += 1

        self.conn.commit()
        return count
