"""Shared pytest fixtures for Claudius hooks tests."""

import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add hooks root to path for imports
HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from core.helpers import FilePathResult, BashFilePath, GrepMatch, ResolvedPath
from core.models import CLIToolResultEvent, FileAccessEvent


# =============================================================================
# SQLite Fixtures
# =============================================================================

@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path."""
    return tmp_path / "test_hooks.db"


@pytest.fixture
def temp_sqlite_db(temp_db_path):
    """Create an in-memory SQLite database with v7 schema.

    Patches get_db_path to return the temp path.
    """
    # Create the database directly with schema
    import sqlite3
    conn = sqlite3.connect(str(temp_db_path))
    cursor = conn.cursor()

    # Create v7 schema
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            raw_json TEXT,
            tool_name TEXT,
            tool_use_id TEXT,
            file_path TEXT,
            success INTEGER DEFAULT 1,
            error_message TEXT,
            duration_ms REAL,
            prompt_text TEXT,
            prompt_hash TEXT,
            cwd TEXT,
            platform TEXT,
            git_branch TEXT,
            python_version TEXT,
            tool_category TEXT,
            subagent_type TEXT,
            command TEXT,
            pattern TEXT,
            url TEXT,
            output_size_bytes INTEGER,
            has_stderr INTEGER DEFAULT 0,
            sequence_index INTEGER DEFAULT 0,
            intent_type TEXT,
            synced_to_neo4j INTEGER DEFAULT 0,
            parent_session_id TEXT,
            agent_id TEXT,
            is_subagent_event INTEGER DEFAULT 0,
            file_paths_json TEXT,
            access_mode TEXT,
            project_root TEXT,
            glob_match_count INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_access_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
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

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_access_path ON file_access_log(normalized_path)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_access_session ON file_access_log(session_id)")
    cursor.execute("PRAGMA user_version = 7")

    conn.commit()
    conn.close()

    yield temp_db_path


@pytest.fixture
def sqlite_writer(temp_sqlite_db):
    """Create a SQLite writer with temp database."""
    import sqlite3
    # Create a simple writer-like object
    class SimpleWriter:
        def __init__(self, db_path):
            self.conn = sqlite3.connect(str(db_path))
            self.conn.row_factory = sqlite3.Row

        def log_file_access(self, event_id, session_id, tool_name, file_result, timestamp):
            """Log file access to database."""
            cursor = self.conn.cursor()

            # Log primary path
            if file_result.primary_path:
                cursor.execute("""
                    INSERT INTO file_access_log
                    (event_id, session_id, file_path, normalized_path, access_mode,
                     project_root, tool_name, timestamp, is_primary_target, is_glob_expansion)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                """, (
                    event_id,
                    session_id,
                    file_result.primary_path,
                    file_result.primary_path,
                    file_result.access_mode,
                    file_result.project_root,
                    tool_name,
                    timestamp,
                    1 if file_result.is_glob_expansion else 0,
                ))

            # Log related paths
            for path in file_result.related_paths:
                cursor.execute("""
                    INSERT INTO file_access_log
                    (event_id, session_id, file_path, normalized_path, access_mode,
                     project_root, tool_name, timestamp, is_primary_target, is_glob_expansion)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                """, (
                    event_id,
                    session_id,
                    path,
                    path,
                    file_result.access_mode,
                    file_result.project_root,
                    tool_name,
                    timestamp,
                    1 if file_result.is_glob_expansion else 0,
                ))

            self.conn.commit()

        def log_file_access_from_event(self, session_id, tool_name, tool_input, tool_output, cwd, timestamp):
            """Extract and log file access from event data."""
            from core.helpers import extract_all_file_paths
            result = extract_all_file_paths(tool_name, tool_input, tool_output, cwd)
            if result.primary_path:
                self.log_file_access(None, session_id, tool_name, result, timestamp)
                return 1 + len(result.related_paths)
            return 0

    writer = SimpleWriter(temp_sqlite_db)
    yield writer
    writer.conn.close()


@pytest.fixture
def sqlite_reader(temp_sqlite_db):
    """Create a SQLite reader with temp database."""
    with patch('sqlite.reader.get_db_path', return_value=temp_sqlite_db):
        from sqlite.reader import CLISqliteReader
        with CLISqliteReader() as reader:
            yield reader


@pytest.fixture
def populated_file_access_db(sqlite_writer, temp_sqlite_db):
    """Database populated with sample file access records."""
    # Create a session first
    session_id = "test-session-001"

    # Insert session start event
    cursor = sqlite_writer.conn.cursor()
    cursor.execute("""
        INSERT INTO events (session_id, event_type, timestamp, raw_json)
        VALUES (?, 'SessionStart', ?, ?)
    """, (session_id, datetime.now().isoformat(), '{}'))

    # Insert file access records
    file_accesses = [
        (session_id, '/project/src/main.py', '/project/src/main.py', 'read', '/project', 'Read', 1, 0),
        (session_id, '/project/src/utils.py', '/project/src/utils.py', 'read', '/project', 'Read', 1, 0),
        (session_id, '/project/src/config.py', '/project/src/config.py', 'write', '/project', 'Write', 1, 0),
        (session_id, '/project/tests/test_main.py', '/project/tests/test_main.py', 'read', '/project', 'Glob', 0, 1),
        (session_id, '/project/tests/test_utils.py', '/project/tests/test_utils.py', 'read', '/project', 'Glob', 0, 1),
    ]

    for fa in file_accesses:
        cursor.execute("""
            INSERT INTO file_access_log
            (session_id, file_path, normalized_path, access_mode, project_root,
             tool_name, is_primary_target, is_glob_expansion, timestamp, synced_to_neo4j)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (*fa, datetime.now().isoformat()))

    sqlite_writer.conn.commit()

    return {
        'db_path': temp_sqlite_db,
        'session_id': session_id,
        'file_count': len(file_accesses),
    }


# =============================================================================
# Neo4j Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_neo4j_driver():
    """Create a mocked Neo4j driver."""
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=None)

    # Track executed queries
    executed_queries = []

    def track_query(query, params=None):
        executed_queries.append({'query': query, 'params': params})
        mock_result = MagicMock()
        mock_result.single.return_value = {'count': 0}
        return mock_result

    mock_session.run = track_query
    mock_session.execute_write = lambda fn: fn(mock_session)

    mock_driver._executed_queries = executed_queries

    return mock_driver


@pytest.fixture
def mock_neo4j_available():
    """Patch is_neo4j_available to return True."""
    with patch('core.config.is_neo4j_available', return_value=True):
        yield


@pytest.fixture
def mock_neo4j_unavailable():
    """Patch is_neo4j_available to return False."""
    with patch('core.config.is_neo4j_available', return_value=False):
        yield


# =============================================================================
# Sample Data Fixtures
# =============================================================================

@pytest.fixture
def sample_file_path_result():
    """FilePathResult with typical data."""
    return FilePathResult(
        primary_path='/project/src/main.py',
        related_paths=['/project/src/utils.py', '/project/src/config.py'],
        access_mode='read',
        is_glob_expansion=False,
        project_root='/project'
    )


@pytest.fixture
def sample_glob_file_result():
    """FilePathResult from Glob expansion."""
    return FilePathResult(
        primary_path='/project/src',
        related_paths=[
            '/project/src/main.py',
            '/project/src/utils.py',
            '/project/src/config.py',
        ],
        access_mode='search',
        is_glob_expansion=True,
        project_root='/project'
    )


@pytest.fixture
def sample_tool_event():
    """CLIToolResultEvent for testing."""
    return CLIToolResultEvent(
        session_id='test-session-001',
        tool_name='Read',
        tool_input={'file_path': '/project/src/main.py'},
        tool_output='file contents here',
        timestamp=datetime.now(),
        call_id='tool_use_001',
        duration_ms=50.0,
        success=True,
    )


@pytest.fixture
def sample_file_access_event():
    """FileAccessEvent for testing."""
    return FileAccessEvent(
        session_id='test-session-001',
        file_path='/project/src/main.py',
        normalized_path='/project/src/main.py',
        access_mode='read',
        timestamp=datetime.now(),
        tool_name='Read',
        event_id=1,
        project_root='/project',
        line_numbers=[],
        is_primary_target=True,
        is_glob_expansion=False,
        synced_to_neo4j=False,
    )


@pytest.fixture
def sample_grep_matches():
    """List of GrepMatch for testing."""
    return [
        GrepMatch(file_path='/src/main.py', line_number=10, match_content='def main():'),
        GrepMatch(file_path='/src/utils.py', line_number=25, match_content='def helper():'),
        GrepMatch(file_path='/src/config.py', line_number=5, match_content='CONFIG = {}'),
    ]


@pytest.fixture
def sample_bash_file_paths():
    """List of BashFilePath for testing."""
    return [
        BashFilePath(path='/src/main.py', operation='read', is_source=True, is_destination=False),
        BashFilePath(path='/dst/main.py', operation='copy', is_source=False, is_destination=True),
    ]


# =============================================================================
# Temporary File System Fixtures
# =============================================================================

@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory with markers."""
    project = tmp_path / "test_project"
    project.mkdir()

    # Create .git directory (marker)
    (project / ".git").mkdir()

    # Create source files
    src = project / "src"
    src.mkdir()
    (src / "main.py").write_text("# main.py")
    (src / "utils.py").write_text("# utils.py")

    # Create tests
    tests = project / "tests"
    tests.mkdir()
    (tests / "test_main.py").write_text("# test_main.py")

    return project


@pytest.fixture
def temp_nested_projects(tmp_path):
    """Create nested project directories for testing."""
    outer = tmp_path / "outer"
    outer.mkdir()
    (outer / ".git").mkdir()  # Git marker at outer

    inner = outer / "inner"
    inner.mkdir()
    (inner / "pyproject.toml").write_text("[tool.pytest]")  # Python marker at inner

    innermost = inner / "subproject"
    innermost.mkdir()
    (innermost / "file.py").write_text("# file")

    return {
        'outer': outer,
        'inner': inner,
        'innermost': innermost,
    }


# =============================================================================
# Hook Input/Output Fixtures
# =============================================================================

@pytest.fixture
def post_tool_use_read_event():
    """PostToolUse event JSON for Read tool."""
    return json.dumps({
        "event": "PostToolUse",
        "sessionId": "test-session-001",
        "toolName": "Read",
        "toolInput": {"file_path": "/project/src/main.py"},
        "toolOutput": "file contents here",
    })


@pytest.fixture
def post_tool_use_glob_event():
    """PostToolUse event JSON for Glob tool."""
    return json.dumps({
        "event": "PostToolUse",
        "sessionId": "test-session-002",
        "toolName": "Glob",
        "toolInput": {"path": "/project/src", "pattern": "*.py"},
        "toolOutput": "main.py\nutils.py\nconfig.py",
    })


@pytest.fixture
def post_tool_use_bash_event():
    """PostToolUse event JSON for Bash tool."""
    return json.dumps({
        "event": "PostToolUse",
        "sessionId": "test-session-003",
        "toolName": "Bash",
        "toolInput": {"command": "cat /etc/hosts"},
        "toolOutput": "127.0.0.1 localhost",
    })


@pytest.fixture
def session_start_event():
    """SessionStart event JSON."""
    return json.dumps({
        "event": "SessionStart",
        "sessionId": "test-session-001",
    })


@pytest.fixture
def session_end_event():
    """SessionEnd event JSON."""
    return json.dumps({
        "event": "SessionEnd",
        "sessionId": "test-session-001",
    })


# =============================================================================
# Environment Fixtures
# =============================================================================

@pytest.fixture
def clean_environment():
    """Provide a clean environment without Neo4j vars."""
    env_vars = ['NEO4J_URI', 'NEO4J_USER', 'NEO4J_PASSWORD', 'NEO4J_DATABASE']
    original = {k: os.environ.get(k) for k in env_vars}

    for var in env_vars:
        if var in os.environ:
            del os.environ[var]

    yield

    # Restore
    for var, value in original.items():
        if value is not None:
            os.environ[var] = value
        elif var in os.environ:
            del os.environ[var]
