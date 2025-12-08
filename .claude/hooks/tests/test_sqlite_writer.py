"""Unit tests for sqlite/writer.py schema and write operations."""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hooks root to path for imports
HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from core.helpers import FilePathResult


# =============================================================================
# Test Schema v7
# =============================================================================

class TestSchemaV7:
    """Tests for SQLite schema version 7."""

    @pytest.mark.integration
    def test_fresh_database_creates_schema(self, temp_db_path):
        """Fresh database should create correct schema tables."""
        with patch('sqlite.writer.get_db_path', return_value=temp_db_path):
            from sqlite.writer import CLISqliteWriter

            with CLISqliteWriter() as writer:
                # Check that events table exists
                cursor = writer.conn.cursor()
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='events'
                """)
                assert cursor.fetchone() is not None

    @pytest.mark.integration
    def test_events_table_exists(self, sqlite_writer):
        """events table should exist."""
        cursor = sqlite_writer.conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='events'
        """)
        result = cursor.fetchone()
        assert result is not None

    @pytest.mark.integration
    def test_file_access_log_table_exists(self, sqlite_writer):
        """file_access_log table should exist."""
        cursor = sqlite_writer.conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='file_access_log'
        """)
        result = cursor.fetchone()
        assert result is not None

    @pytest.mark.integration
    def test_events_v7_columns_exist(self, sqlite_writer):
        """Events table should have v7 columns."""
        cursor = sqlite_writer.conn.cursor()
        cursor.execute("PRAGMA table_info(events)")
        columns = {row[1] for row in cursor.fetchall()}

        # v7 columns
        assert 'file_paths_json' in columns
        assert 'access_mode' in columns
        assert 'project_root' in columns
        assert 'glob_match_count' in columns

    @pytest.mark.integration
    def test_file_access_log_columns(self, sqlite_writer):
        """file_access_log should have all required columns."""
        cursor = sqlite_writer.conn.cursor()
        cursor.execute("PRAGMA table_info(file_access_log)")
        columns = {row[1] for row in cursor.fetchall()}

        expected = {
            'id', 'event_id', 'session_id', 'file_path', 'normalized_path',
            'access_mode', 'project_root', 'timestamp', 'tool_name',
            'line_numbers_json', 'is_primary_target', 'is_glob_expansion',
            'synced_to_neo4j'
        }
        assert expected.issubset(columns)

    @pytest.mark.integration
    def test_file_access_log_indexes_exist(self, sqlite_writer):
        """file_access_log indexes should exist."""
        cursor = sqlite_writer.conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND tbl_name='file_access_log'
        """)
        indexes = {row[0] for row in cursor.fetchall()}

        # Should have path and session indexes
        assert any('path' in idx.lower() for idx in indexes)
        assert any('session' in idx.lower() for idx in indexes)


# =============================================================================
# Test log_file_access()
# =============================================================================

class TestLogFileAccess:
    """Tests for log_file_access() method."""

    @pytest.mark.integration
    def test_single_primary_file(self, sqlite_writer):
        """Single primary file should create one record."""
        file_result = FilePathResult(
            primary_path='/project/src/main.py',
            related_paths=[],
            access_mode='read',
            is_glob_expansion=False,
            project_root='/project',
        )

        sqlite_writer.log_file_access(
            event_id=1,
            session_id='test-session-001',
            tool_name='Read',
            file_result=file_result,
            timestamp=datetime.now().isoformat(),
        )

        cursor = sqlite_writer.conn.cursor()
        cursor.execute("SELECT * FROM file_access_log WHERE session_id = ?",
                       ('test-session-001',))
        rows = cursor.fetchall()

        assert len(rows) == 1

    @pytest.mark.integration
    def test_primary_with_related_files(self, sqlite_writer):
        """Primary + related files should create multiple records."""
        file_result = FilePathResult(
            primary_path='/project/src',
            related_paths=['/project/src/main.py', '/project/src/utils.py', '/project/src/config.py'],
            access_mode='search',
            is_glob_expansion=True,
            project_root='/project',
        )

        sqlite_writer.log_file_access(
            event_id=2,
            session_id='test-session-002',
            tool_name='Glob',
            file_result=file_result,
            timestamp=datetime.now().isoformat(),
        )

        cursor = sqlite_writer.conn.cursor()
        cursor.execute("SELECT * FROM file_access_log WHERE session_id = ?",
                       ('test-session-002',))
        rows = cursor.fetchall()

        assert len(rows) == 4  # 1 primary + 3 related

    @pytest.mark.integration
    def test_glob_expansion_flag(self, sqlite_writer):
        """is_glob_expansion should be set correctly."""
        file_result = FilePathResult(
            primary_path='/src',
            related_paths=['/src/a.py', '/src/b.py'],
            access_mode='search',
            is_glob_expansion=True,
            project_root='/project',
        )

        sqlite_writer.log_file_access(
            event_id=3,
            session_id='test-session-003',
            tool_name='Glob',
            file_result=file_result,
            timestamp=datetime.now().isoformat(),
        )

        cursor = sqlite_writer.conn.cursor()
        cursor.execute("""
            SELECT is_glob_expansion FROM file_access_log
            WHERE session_id = ? AND is_primary_target = 0
        """, ('test-session-003',))
        rows = cursor.fetchall()

        # Related files from glob should have is_glob_expansion=1
        assert all(row[0] == 1 for row in rows)

    @pytest.mark.integration
    def test_project_root_stored(self, sqlite_writer):
        """Project root should be stored."""
        file_result = FilePathResult(
            primary_path='/project/src/main.py',
            related_paths=[],
            access_mode='read',
            is_glob_expansion=False,
            project_root='/project',
        )

        sqlite_writer.log_file_access(
            event_id=4,
            session_id='test-session-004',
            tool_name='Read',
            file_result=file_result,
            timestamp=datetime.now().isoformat(),
        )

        cursor = sqlite_writer.conn.cursor()
        cursor.execute("""
            SELECT project_root FROM file_access_log
            WHERE session_id = ?
        """, ('test-session-004',))
        row = cursor.fetchone()

        assert row[0] == '/project'

    @pytest.mark.integration
    def test_access_modes(self, sqlite_writer):
        """Various access modes should be stored correctly."""
        modes = ['read', 'write', 'modify', 'search', 'execute']

        for i, mode in enumerate(modes):
            file_result = FilePathResult(
                primary_path=f'/path/file{i}.py',
                related_paths=[],
                access_mode=mode,
                is_glob_expansion=False,
            )

            sqlite_writer.log_file_access(
                event_id=10 + i,
                session_id=f'test-mode-{mode}',
                tool_name='Test',
                file_result=file_result,
                timestamp=datetime.now().isoformat(),
            )

            cursor = sqlite_writer.conn.cursor()
            cursor.execute("""
                SELECT access_mode FROM file_access_log
                WHERE session_id = ?
            """, (f'test-mode-{mode}',))
            row = cursor.fetchone()

            assert row[0] == mode

    @pytest.mark.integration
    def test_primary_target_marking(self, sqlite_writer):
        """Primary target should be marked is_primary_target=1."""
        file_result = FilePathResult(
            primary_path='/src/main.py',
            related_paths=['/src/utils.py'],
            access_mode='search',
            is_glob_expansion=True,
        )

        sqlite_writer.log_file_access(
            event_id=20,
            session_id='test-primary-mark',
            tool_name='Glob',
            file_result=file_result,
            timestamp=datetime.now().isoformat(),
        )

        cursor = sqlite_writer.conn.cursor()

        # Check primary
        cursor.execute("""
            SELECT is_primary_target FROM file_access_log
            WHERE session_id = ? AND normalized_path LIKE '%main.py'
        """, ('test-primary-mark',))
        row = cursor.fetchone()
        assert row[0] == 1

        # Check related
        cursor.execute("""
            SELECT is_primary_target FROM file_access_log
            WHERE session_id = ? AND normalized_path LIKE '%utils.py'
        """, ('test-primary-mark',))
        row = cursor.fetchone()
        assert row[0] == 0


# =============================================================================
# Test log_file_access_from_event()
# =============================================================================

class TestLogFileAccessFromEvent:
    """Tests for log_file_access_from_event() convenience method."""

    @pytest.mark.integration
    def test_read_tool_extraction(self, sqlite_writer):
        """Read tool should extract and log file_path."""
        count = sqlite_writer.log_file_access_from_event(
            session_id='test-from-event-001',
            tool_name='Read',
            tool_input={'file_path': '/project/src/main.py'},
            tool_output='file contents',
            cwd='/project',
            timestamp=datetime.now().isoformat(),
        )

        assert count >= 1

        cursor = sqlite_writer.conn.cursor()
        cursor.execute("""
            SELECT normalized_path, access_mode FROM file_access_log
            WHERE session_id = ?
        """, ('test-from-event-001',))
        row = cursor.fetchone()

        assert row is not None
        assert 'main.py' in row[0]
        assert row[1] == 'read'

    @pytest.mark.integration
    def test_write_tool_extraction(self, sqlite_writer):
        """Write tool should extract with write mode."""
        count = sqlite_writer.log_file_access_from_event(
            session_id='test-from-event-002',
            tool_name='Write',
            tool_input={'file_path': '/project/src/new.py'},
            tool_output='',
            cwd='/project',
            timestamp=datetime.now().isoformat(),
        )

        cursor = sqlite_writer.conn.cursor()
        cursor.execute("""
            SELECT access_mode FROM file_access_log
            WHERE session_id = ?
        """, ('test-from-event-002',))
        row = cursor.fetchone()

        assert row[0] == 'write'

    @pytest.mark.integration
    def test_glob_output_parsing(self, sqlite_writer):
        """Glob output should be parsed for file paths."""
        count = sqlite_writer.log_file_access_from_event(
            session_id='test-from-event-003',
            tool_name='Glob',
            tool_input={'path': '/project/src', 'pattern': '*.py'},
            tool_output='main.py\nutils.py\nconfig.py',
            cwd='/project',
            timestamp=datetime.now().isoformat(),
        )

        assert count >= 1

        cursor = sqlite_writer.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM file_access_log
            WHERE session_id = ?
        """, ('test-from-event-003',))
        row = cursor.fetchone()

        # Should have primary path + related files
        assert row[0] >= 1

    @pytest.mark.integration
    def test_unknown_tool_returns_none(self, sqlite_writer):
        """Unknown tool should return 0 or None."""
        count = sqlite_writer.log_file_access_from_event(
            session_id='test-from-event-004',
            tool_name='WebFetch',
            tool_input={'url': 'https://example.com'},
            tool_output='response',
            cwd='/project',
            timestamp=datetime.now().isoformat(),
        )

        # Should return 0 or None for unknown tools
        assert count == 0 or count is None


# =============================================================================
# Test Schema Migration
# =============================================================================

class TestSchemaMigration:
    """Tests for schema migration functionality."""

    @pytest.mark.integration
    def test_writer_works_with_existing_database(self, temp_db_path):
        """Writer should work with existing database and add missing columns."""
        # First create a minimal database manually
        conn = sqlite3.connect(str(temp_db_path))
        cursor = conn.cursor()

        # Create minimal events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                raw_json TEXT,
                tool_name TEXT,
                file_path TEXT
            )
        """)
        conn.commit()
        conn.close()

        # Now open with writer and verify it works
        with patch('sqlite.writer.get_db_path', return_value=temp_db_path):
            from sqlite.writer import CLISqliteWriter

            with CLISqliteWriter() as writer:
                # Writer should be able to connect and work
                cursor = writer.conn.cursor()

                # Should be able to insert data
                cursor.execute("""
                    INSERT INTO events (session_id, event_type, timestamp, raw_json)
                    VALUES (?, 'SessionStart', ?, '{}')
                """, ('test-session', datetime.now().isoformat()))
                writer.conn.commit()

                # Verify insertion
                cursor.execute("SELECT COUNT(*) FROM events")
                count = cursor.fetchone()[0]
                assert count >= 1


# =============================================================================
# Test Event Writing with File Access
# =============================================================================

class TestEventWritingWithFileAccess:
    """Tests for event writing that includes file access logging."""

    @pytest.mark.integration
    def test_post_tool_use_logs_file_access(self, sqlite_writer):
        """PostToolUse should trigger file access logging."""
        # Create a PostToolUse event
        event_data = {
            'event': 'PostToolUse',
            'session_id': 'test-post-tool-001',
            'tool_name': 'Read',
            'tool_input': {'file_path': '/project/src/main.py'},
            'tool_output': 'file contents',
        }

        cursor = sqlite_writer.conn.cursor()

        # Insert event
        cursor.execute("""
            INSERT INTO events (session_id, event_type, timestamp, raw_json, tool_name, file_path)
            VALUES (?, 'PostToolUse', ?, ?, 'Read', '/project/src/main.py')
        """, (
            'test-post-tool-001',
            datetime.now().isoformat(),
            json.dumps(event_data),
        ))
        event_id = cursor.lastrowid
        sqlite_writer.conn.commit()

        # Log file access
        file_result = FilePathResult(
            primary_path='/project/src/main.py',
            access_mode='read',
        )
        sqlite_writer.log_file_access(
            event_id=event_id,
            session_id='test-post-tool-001',
            tool_name='Read',
            file_result=file_result,
            timestamp=datetime.now().isoformat(),
        )

        # Verify file_access_log entry
        cursor.execute("""
            SELECT event_id, tool_name FROM file_access_log
            WHERE session_id = ?
        """, ('test-post-tool-001',))
        row = cursor.fetchone()

        assert row is not None
        assert row[0] == event_id
        assert row[1] == 'Read'
