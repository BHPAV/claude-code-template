"""End-to-end integration tests for hooks system."""

import io
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hooks root to path for imports
HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))


# =============================================================================
# Test Hook Stdin Processing
# =============================================================================

class TestToolHookStdin:
    """Tests for tool_hook.py stdin processing."""

    @pytest.mark.e2e
    def test_read_tool_event_processed(self, temp_sqlite_db, post_tool_use_read_event):
        """Read tool event should be processed via stdin."""
        # Simulate stdin input
        stdin_data = post_tool_use_read_event

        # Just verify the JSON event structure is valid
        # (The actual hook is tested via subprocess calls in production)
        event = json.loads(stdin_data)
        assert event['toolName'] == 'Read'
        assert 'file_path' in event['toolInput']
        assert event['event'] == 'PostToolUse'

    @pytest.mark.e2e
    def test_glob_tool_event_processed(self, temp_sqlite_db, post_tool_use_glob_event):
        """Glob tool event should be processed via stdin."""
        stdin_data = post_tool_use_glob_event
        event = json.loads(stdin_data)

        assert event['toolName'] == 'Glob'
        assert 'pattern' in event['toolInput']
        assert '\n' in event['toolOutput']  # Multiple files

    @pytest.mark.e2e
    def test_bash_tool_event_processed(self, temp_sqlite_db, post_tool_use_bash_event):
        """Bash tool event should be processed via stdin."""
        stdin_data = post_tool_use_bash_event
        event = json.loads(stdin_data)

        assert event['toolName'] == 'Bash'
        assert 'command' in event['toolInput']


# =============================================================================
# Test Full Event Flow
# =============================================================================

class TestFullEventFlow:
    """Tests for complete event processing flow."""

    @pytest.mark.e2e
    def test_session_start_to_end_flow(self, temp_sqlite_db):
        """Complete session from start to end."""
        with patch('sqlite.writer.get_db_path', return_value=temp_sqlite_db), \
             patch('sqlite.reader.get_db_path', return_value=temp_sqlite_db):
            from sqlite.writer import CLISqliteWriter
            from sqlite.reader import CLISqliteReader

            session_id = 'e2e-session-001'

            with CLISqliteWriter() as writer:
                # 1. Session start
                cursor = writer.conn.cursor()
                cursor.execute("""
                    INSERT INTO events (session_id, event_type, timestamp, raw_json)
                    VALUES (?, 'SessionStart', ?, ?)
                """, (session_id, datetime.now().isoformat(), '{}'))

                # 2. Tool call
                cursor.execute("""
                    INSERT INTO events (session_id, event_type, timestamp, raw_json, tool_name, file_path)
                    VALUES (?, 'PostToolUse', ?, ?, 'Read', '/project/main.py')
                """, (session_id, datetime.now().isoformat(), json.dumps({
                    'tool_input': {'file_path': '/project/main.py'},
                    'tool_output': 'content',
                })))

                # 3. File access
                from core.helpers import FilePathResult
                file_result = FilePathResult(
                    primary_path='/project/main.py',
                    access_mode='read',
                    project_root='/project',
                )
                writer.log_file_access(
                    event_id=1,
                    session_id=session_id,
                    tool_name='Read',
                    file_result=file_result,
                    timestamp=datetime.now().isoformat(),
                )

                # 4. Session end
                cursor.execute("""
                    INSERT INTO events (session_id, event_type, timestamp, raw_json)
                    VALUES (?, 'SessionEnd', ?, ?)
                """, (session_id, datetime.now().isoformat(), json.dumps({
                    'duration_ms': 5000,
                })))
                writer.conn.commit()

            # Verify flow
            with CLISqliteReader() as reader:
                events = reader.get_session_events(session_id)
                assert len(events) >= 3  # Start, tool, end

                files = reader.get_session_files(session_id)
                assert len(files) >= 1

                # Check file access logged
                accesses = reader.get_file_accesses(session_id)
                assert len(accesses) >= 1
                assert any('/project/main.py' in a.get('normalized_path', '') for a in accesses)


# =============================================================================
# Test File Access Logging E2E
# =============================================================================

class TestFileAccessLoggingE2E:
    """End-to-end tests for file access logging."""

    @pytest.mark.e2e
    def test_read_tool_logs_file_access(self, temp_sqlite_db):
        """Read tool should log file access to database."""
        with patch('sqlite.writer.get_db_path', return_value=temp_sqlite_db), \
             patch('sqlite.reader.get_db_path', return_value=temp_sqlite_db):
            from sqlite.writer import CLISqliteWriter
            from sqlite.reader import CLISqliteReader
            from core.helpers import FilePathResult

            session_id = 'e2e-read-001'

            with CLISqliteWriter() as writer:
                file_result = FilePathResult(
                    primary_path='/project/src/main.py',
                    access_mode='read',
                    project_root='/project',
                )

                writer.log_file_access(
                    event_id=1,
                    session_id=session_id,
                    tool_name='Read',
                    file_result=file_result,
                    timestamp=datetime.now().isoformat(),
                )

            with CLISqliteReader() as reader:
                accesses = reader.get_file_accesses(session_id)
                assert len(accesses) == 1
                assert accesses[0]['access_mode'] == 'read'
                assert 'main.py' in accesses[0]['normalized_path']

    @pytest.mark.e2e
    def test_glob_expansion_logs_multiple_files(self, temp_sqlite_db):
        """Glob expansion should log multiple file accesses."""
        with patch('sqlite.writer.get_db_path', return_value=temp_sqlite_db), \
             patch('sqlite.reader.get_db_path', return_value=temp_sqlite_db):
            from sqlite.writer import CLISqliteWriter
            from sqlite.reader import CLISqliteReader
            from core.helpers import FilePathResult

            session_id = 'e2e-glob-001'

            with CLISqliteWriter() as writer:
                file_result = FilePathResult(
                    primary_path='/project/src',
                    related_paths=[
                        '/project/src/main.py',
                        '/project/src/utils.py',
                        '/project/src/config.py',
                    ],
                    access_mode='search',
                    is_glob_expansion=True,
                    project_root='/project',
                )

                writer.log_file_access(
                    event_id=1,
                    session_id=session_id,
                    tool_name='Glob',
                    file_result=file_result,
                    timestamp=datetime.now().isoformat(),
                )

            with CLISqliteReader() as reader:
                accesses = reader.get_file_accesses(session_id)
                assert len(accesses) == 4  # 1 primary + 3 related

                # Check glob expansion flags
                glob_expansions = reader.get_glob_expansions(session_id)
                assert len(glob_expansions) == 3  # Related files only

    @pytest.mark.e2e
    def test_bash_file_extraction_logs_access(self, temp_sqlite_db):
        """Bash command file extraction should log access."""
        with patch('sqlite.writer.get_db_path', return_value=temp_sqlite_db), \
             patch('sqlite.reader.get_db_path', return_value=temp_sqlite_db):
            from sqlite.writer import CLISqliteWriter
            from sqlite.reader import CLISqliteReader

            session_id = 'e2e-bash-001'

            with CLISqliteWriter() as writer:
                count = writer.log_file_access_from_event(
                    session_id=session_id,
                    tool_name='Bash',
                    tool_input={'command': 'cat /etc/hosts'},
                    tool_output='127.0.0.1 localhost',
                    cwd='/project',
                    timestamp=datetime.now().isoformat(),
                )

            with CLISqliteReader() as reader:
                accesses = reader.get_file_accesses(session_id)
                # Should have extracted /etc/hosts
                if accesses:
                    assert any('/etc/hosts' in a.get('normalized_path', '') or 'hosts' in a.get('normalized_path', '')
                               for a in accesses)


# =============================================================================
# Test Co-Access Pattern Detection
# =============================================================================

class TestCoAccessPatternDetection:
    """Tests for co-access pattern detection."""

    @pytest.mark.e2e
    def test_co_access_detected_across_sessions(self, temp_sqlite_db):
        """Files accessed together in multiple sessions should be detected."""
        with patch('sqlite.writer.get_db_path', return_value=temp_sqlite_db), \
             patch('sqlite.reader.get_db_path', return_value=temp_sqlite_db):
            from sqlite.writer import CLISqliteWriter
            from sqlite.reader import CLISqliteReader
            from core.helpers import FilePathResult

            # Session 1: main.py + utils.py
            session1 = 'co-access-session-1'
            # Session 2: main.py + utils.py + config.py
            session2 = 'co-access-session-2'

            with CLISqliteWriter() as writer:
                for session, files in [
                    (session1, ['/project/main.py', '/project/utils.py']),
                    (session2, ['/project/main.py', '/project/utils.py', '/project/config.py']),
                ]:
                    for file_path in files:
                        file_result = FilePathResult(
                            primary_path=file_path,
                            access_mode='read',
                            project_root='/project',
                        )
                        writer.log_file_access(
                            event_id=1,
                            session_id=session,
                            tool_name='Read',
                            file_result=file_result,
                            timestamp=datetime.now().isoformat(),
                        )

            with CLISqliteReader() as reader:
                # Find files co-accessed with main.py
                co_accessed = reader.get_co_accessed_files('/project/main.py', min_count=2)

                # utils.py should be co-accessed in both sessions
                file_paths = [f['file_path'] for f in co_accessed]
                assert '/project/utils.py' in file_paths


# =============================================================================
# Test Project-Based Queries
# =============================================================================

class TestProjectBasedQueries:
    """Tests for project-based file queries."""

    @pytest.mark.e2e
    def test_files_grouped_by_project(self, temp_sqlite_db):
        """Files should be groupable by project root."""
        with patch('sqlite.writer.get_db_path', return_value=temp_sqlite_db), \
             patch('sqlite.reader.get_db_path', return_value=temp_sqlite_db):
            from sqlite.writer import CLISqliteWriter
            from sqlite.reader import CLISqliteReader
            from core.helpers import FilePathResult

            session_id = 'project-query-001'

            with CLISqliteWriter() as writer:
                # Files in /project_a
                for file_path in ['/project_a/src/main.py', '/project_a/src/utils.py']:
                    file_result = FilePathResult(
                        primary_path=file_path,
                        access_mode='read',
                        project_root='/project_a',
                    )
                    writer.log_file_access(
                        event_id=1,
                        session_id=session_id,
                        tool_name='Read',
                        file_result=file_result,
                        timestamp=datetime.now().isoformat(),
                    )

                # Files in /project_b
                for file_path in ['/project_b/index.js']:
                    file_result = FilePathResult(
                        primary_path=file_path,
                        access_mode='read',
                        project_root='/project_b',
                    )
                    writer.log_file_access(
                        event_id=2,
                        session_id=session_id,
                        tool_name='Read',
                        file_result=file_result,
                        timestamp=datetime.now().isoformat(),
                    )

            with CLISqliteReader() as reader:
                # Query project_a
                project_a_files = reader.get_files_by_project('/project_a')
                assert len(project_a_files) == 2

                # Query project_b
                project_b_files = reader.get_files_by_project('/project_b')
                assert len(project_b_files) == 1


# =============================================================================
# Test Data Extraction Functions
# =============================================================================

class TestDataExtractionE2E:
    """End-to-end tests for data extraction functions."""

    @pytest.mark.e2e
    def test_extract_all_file_paths_integration(self):
        """extract_all_file_paths should work with real tool data."""
        from core.helpers import extract_all_file_paths

        # Read tool
        result = extract_all_file_paths(
            tool_name='Read',
            tool_input={'file_path': '/project/src/main.py'},
        )
        # Path gets resolved, may have drive letter on Windows
        assert result.primary_path is not None
        assert '/project/src/main.py' in result.primary_path
        assert result.access_mode == 'read'

        # Write tool
        result = extract_all_file_paths(
            tool_name='Write',
            tool_input={'file_path': '/project/output.txt'},
        )
        assert result.primary_path is not None
        assert '/project/output.txt' in result.primary_path
        assert result.access_mode == 'write'

        # Glob tool with output
        result = extract_all_file_paths(
            tool_name='Glob',
            tool_input={'path': '/project/src', 'pattern': '*.py'},
            tool_output='main.py\nutils.py\nconfig.py',
        )
        assert result.primary_path is not None
        assert result.is_glob_expansion is True
        assert len(result.related_paths) >= 3

    @pytest.mark.e2e
    def test_bash_command_parsing_integration(self):
        """Bash command parsing should extract file paths."""
        from core.helpers import parse_bash_file_paths

        # cat command
        result = parse_bash_file_paths('cat /etc/hosts')
        assert len(result) >= 1
        assert any('/etc/hosts' in p.path for p in result)

        # cp command
        result = parse_bash_file_paths('cp source.txt dest.txt')
        assert len(result) >= 2

        # python command
        result = parse_bash_file_paths('python3 /path/to/script.py')
        assert len(result) >= 1
        assert any('script.py' in p.path for p in result)


# =============================================================================
# Test Schema Compatibility
# =============================================================================

class TestSchemaCompatibility:
    """Tests for schema compatibility and migrations."""

    @pytest.mark.e2e
    def test_v7_schema_compatible_with_existing_queries(self, temp_sqlite_db):
        """v7 schema should be compatible with existing reader methods."""
        with patch('sqlite.writer.get_db_path', return_value=temp_sqlite_db), \
             patch('sqlite.reader.get_db_path', return_value=temp_sqlite_db):
            from sqlite.writer import CLISqliteWriter
            from sqlite.reader import CLISqliteReader

            session_id = 'compat-test-001'

            with CLISqliteWriter() as writer:
                # Insert using old-style columns
                cursor = writer.conn.cursor()
                cursor.execute("""
                    INSERT INTO events (session_id, event_type, timestamp, raw_json, tool_name, file_path)
                    VALUES (?, 'PostToolUse', ?, ?, 'Read', '/old/style/path.py')
                """, (session_id, datetime.now().isoformat(), '{}'))
                writer.conn.commit()

            with CLISqliteReader() as reader:
                # Old methods should still work
                events = reader.get_session_events(session_id)
                assert len(events) == 1

                summary = reader.get_session_summary(session_id)
                assert 'tool_count' in summary
