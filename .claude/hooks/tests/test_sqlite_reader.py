"""Unit tests for sqlite/reader.py query methods."""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hooks root to path for imports
HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))


# =============================================================================
# Test get_file_accesses()
# =============================================================================

class TestGetFileAccesses:
    """Tests for get_file_accesses() method."""

    @pytest.mark.integration
    def test_returns_all_accesses(self, populated_file_access_db):
        """Should return all file accesses for session."""
        # Patch in the reader's namespace where it was imported
        with patch('sqlite.reader.get_db_path', return_value=populated_file_access_db['db_path']):
            from sqlite.reader import CLISqliteReader

            with CLISqliteReader() as reader:
                result = reader.get_file_accesses(populated_file_access_db['session_id'])

                assert len(result) == populated_file_access_db['file_count']

    @pytest.mark.integration
    def test_returns_correct_fields(self, populated_file_access_db):
        """Should return dicts with all required fields."""
        with patch('sqlite.reader.get_db_path', return_value=populated_file_access_db['db_path']):
            from sqlite.reader import CLISqliteReader

            with CLISqliteReader() as reader:
                result = reader.get_file_accesses(populated_file_access_db['session_id'])

                assert all('normalized_path' in r for r in result)
                assert all('access_mode' in r for r in result)
                assert all('tool_name' in r for r in result)
                assert all('session_id' in r for r in result)

    @pytest.mark.integration
    def test_empty_session_returns_empty(self, temp_sqlite_db):
        """Non-existent session should return empty list."""
        with patch('sqlite.reader.get_db_path', return_value=temp_sqlite_db):
            from sqlite.reader import CLISqliteReader

            with CLISqliteReader() as reader:
                result = reader.get_file_accesses('nonexistent-session')
                assert result == []


# =============================================================================
# Test get_unsynced_file_accesses()
# =============================================================================

class TestGetUnsyncedFileAccesses:
    """Tests for get_unsynced_file_accesses() method."""

    @pytest.mark.integration
    def test_returns_unsynced_only(self, populated_file_access_db):
        """Should return only unsynced file accesses."""
        with patch('sqlite.reader.get_db_path', return_value=populated_file_access_db['db_path']):
            from sqlite.reader import CLISqliteReader

            with CLISqliteReader() as reader:
                result = reader.get_unsynced_file_accesses()

                # All should be unsynced (synced_to_neo4j = 0)
                assert all(r.get('synced_to_neo4j', 0) == 0 for r in result)

    @pytest.mark.integration
    def test_excludes_synced(self, populated_file_access_db, sqlite_writer):
        """Should exclude synced file accesses."""
        with patch('sqlite.reader.get_db_path', return_value=populated_file_access_db['db_path']):
            from sqlite.reader import CLISqliteReader

            # Mark some as synced
            cursor = sqlite_writer.conn.cursor()
            cursor.execute("""
                UPDATE file_access_log SET synced_to_neo4j = 1
                WHERE id IN (SELECT id FROM file_access_log LIMIT 2)
            """)
            sqlite_writer.conn.commit()

            with CLISqliteReader() as reader:
                result = reader.get_unsynced_file_accesses()

                # Should have 3 less than total
                assert len(result) == populated_file_access_db['file_count'] - 2


# =============================================================================
# Test get_session_files()
# =============================================================================

class TestGetSessionFiles:
    """Tests for get_session_files() method."""

    @pytest.mark.integration
    def test_returns_unique_paths(self, populated_file_access_db):
        """Should return unique file paths only."""
        with patch('sqlite.reader.get_db_path', return_value=populated_file_access_db['db_path']):
            from sqlite.reader import CLISqliteReader

            with CLISqliteReader() as reader:
                result = reader.get_session_files(populated_file_access_db['session_id'])

                # All paths should be unique
                assert len(result) == len(set(result))

    @pytest.mark.integration
    def test_returns_normalized_paths(self, populated_file_access_db):
        """Should return normalized paths."""
        with patch('sqlite.reader.get_db_path', return_value=populated_file_access_db['db_path']):
            from sqlite.reader import CLISqliteReader

            with CLISqliteReader() as reader:
                result = reader.get_session_files(populated_file_access_db['session_id'])

                # Should be strings
                assert all(isinstance(p, str) for p in result)


# =============================================================================
# Test get_file_access_summary()
# =============================================================================

class TestGetFileAccessSummary:
    """Tests for get_file_access_summary() method."""

    @pytest.mark.integration
    def test_returns_summary_dict(self, populated_file_access_db):
        """Should return dict with summary fields."""
        with patch('sqlite.reader.get_db_path', return_value=populated_file_access_db['db_path']):
            from sqlite.reader import CLISqliteReader

            with CLISqliteReader() as reader:
                result = reader.get_file_access_summary(populated_file_access_db['session_id'])

                assert 'total_accesses' in result
                assert 'unique_files' in result
                assert 'by_mode' in result
                assert 'project_roots' in result

    @pytest.mark.integration
    def test_total_accesses_correct(self, populated_file_access_db):
        """total_accesses should match file count."""
        with patch('sqlite.reader.get_db_path', return_value=populated_file_access_db['db_path']):
            from sqlite.reader import CLISqliteReader

            with CLISqliteReader() as reader:
                result = reader.get_file_access_summary(populated_file_access_db['session_id'])

                assert result['total_accesses'] == populated_file_access_db['file_count']

    @pytest.mark.integration
    def test_by_mode_breakdown(self, populated_file_access_db):
        """by_mode should have correct breakdown."""
        with patch('sqlite.reader.get_db_path', return_value=populated_file_access_db['db_path']):
            from sqlite.reader import CLISqliteReader

            with CLISqliteReader() as reader:
                result = reader.get_file_access_summary(populated_file_access_db['session_id'])

                # Should have read and write modes (based on fixture data)
                assert 'read' in result['by_mode']
                assert 'write' in result['by_mode']


# =============================================================================
# Test get_co_accessed_files()
# =============================================================================

class TestGetCoAccessedFiles:
    """Tests for get_co_accessed_files() method."""

    @pytest.mark.integration
    def test_finds_co_accessed_files(self, temp_sqlite_db, sqlite_writer):
        """Should find files accessed together."""
        # Create two sessions with overlapping files
        session1 = 'co-access-session-1'
        session2 = 'co-access-session-2'
        timestamp = datetime.now().isoformat()

        cursor = sqlite_writer.conn.cursor()

        # Session 1: main.py, utils.py
        for path in ['/project/main.py', '/project/utils.py']:
            cursor.execute("""
                INSERT INTO file_access_log
                (session_id, file_path, normalized_path, access_mode, tool_name, timestamp, synced_to_neo4j)
                VALUES (?, ?, ?, 'read', 'Read', ?, 0)
            """, (session1, path, path, timestamp))

        # Session 2: main.py, utils.py, config.py
        for path in ['/project/main.py', '/project/utils.py', '/project/config.py']:
            cursor.execute("""
                INSERT INTO file_access_log
                (session_id, file_path, normalized_path, access_mode, tool_name, timestamp, synced_to_neo4j)
                VALUES (?, ?, ?, 'read', 'Read', ?, 0)
            """, (session2, path, path, timestamp))

        sqlite_writer.conn.commit()

        with patch('sqlite.reader.get_db_path', return_value=temp_sqlite_db):
            from sqlite.reader import CLISqliteReader

            with CLISqliteReader() as reader:
                result = reader.get_co_accessed_files('/project/main.py', min_count=2)

                # utils.py should be co-accessed in both sessions
                file_paths = [r['file_path'] for r in result]
                assert '/project/utils.py' in file_paths

    @pytest.mark.integration
    def test_min_count_filter(self, temp_sqlite_db, sqlite_writer):
        """Should respect min_count threshold."""
        session1 = 'min-count-session-1'
        timestamp = datetime.now().isoformat()

        cursor = sqlite_writer.conn.cursor()

        # Only one session with these files
        for path in ['/project/a.py', '/project/b.py']:
            cursor.execute("""
                INSERT INTO file_access_log
                (session_id, file_path, normalized_path, access_mode, tool_name, timestamp, synced_to_neo4j)
                VALUES (?, ?, ?, 'read', 'Read', ?, 0)
            """, (session1, path, path, timestamp))

        sqlite_writer.conn.commit()

        with patch('sqlite.reader.get_db_path', return_value=temp_sqlite_db):
            from sqlite.reader import CLISqliteReader

            with CLISqliteReader() as reader:
                # With min_count=2, should not find b.py (only 1 co-access)
                result = reader.get_co_accessed_files('/project/a.py', min_count=2)
                assert len(result) == 0

                # With min_count=1, should find b.py
                result = reader.get_co_accessed_files('/project/a.py', min_count=1)
                file_paths = [r['file_path'] for r in result]
                assert '/project/b.py' in file_paths


# =============================================================================
# Test get_files_by_project()
# =============================================================================

class TestGetFilesByProject:
    """Tests for get_files_by_project() method."""

    @pytest.mark.integration
    def test_returns_files_in_project(self, populated_file_access_db):
        """Should return files with matching project_root."""
        with patch('sqlite.reader.get_db_path', return_value=populated_file_access_db['db_path']):
            from sqlite.reader import CLISqliteReader

            with CLISqliteReader() as reader:
                result = reader.get_files_by_project('/project')

                # All files in fixture have /project root
                assert len(result) == populated_file_access_db['file_count']

    @pytest.mark.integration
    def test_returns_correct_fields(self, populated_file_access_db):
        """Should return dicts with expected fields."""
        with patch('sqlite.reader.get_db_path', return_value=populated_file_access_db['db_path']):
            from sqlite.reader import CLISqliteReader

            with CLISqliteReader() as reader:
                result = reader.get_files_by_project('/project')

                if result:
                    assert 'normalized_path' in result[0]
                    assert 'access_count' in result[0]
                    assert 'access_modes' in result[0]
                    assert 'session_count' in result[0]

    @pytest.mark.integration
    def test_non_matching_project_returns_empty(self, populated_file_access_db):
        """Non-matching project root should return empty list."""
        with patch('sqlite.reader.get_db_path', return_value=populated_file_access_db['db_path']):
            from sqlite.reader import CLISqliteReader

            with CLISqliteReader() as reader:
                result = reader.get_files_by_project('/other-project')
                assert result == []


# =============================================================================
# Test get_glob_expansions()
# =============================================================================

class TestGetGlobExpansions:
    """Tests for get_glob_expansions() method."""

    @pytest.mark.integration
    def test_returns_glob_expansions_only(self, populated_file_access_db):
        """Should return only glob expansion files."""
        with patch('sqlite.reader.get_db_path', return_value=populated_file_access_db['db_path']):
            from sqlite.reader import CLISqliteReader

            with CLISqliteReader() as reader:
                result = reader.get_glob_expansions(populated_file_access_db['session_id'])

                # All should be glob expansions
                assert all(r.get('is_glob_expansion', 0) == 1 for r in result)

    @pytest.mark.integration
    def test_correct_count(self, populated_file_access_db):
        """Should return correct number of glob expansions."""
        with patch('sqlite.reader.get_db_path', return_value=populated_file_access_db['db_path']):
            from sqlite.reader import CLISqliteReader

            with CLISqliteReader() as reader:
                result = reader.get_glob_expansions(populated_file_access_db['session_id'])

                # Fixture has 2 glob expansion files
                assert len(result) == 2


# =============================================================================
# Test mark_file_accesses_synced()
# =============================================================================

class TestMarkFileAccessesSynced:
    """Tests for mark_file_accesses_synced() method."""

    @pytest.mark.integration
    def test_marks_all_synced(self, populated_file_access_db):
        """Should mark all file accesses for session as synced."""
        with patch('sqlite.reader.get_db_path', return_value=populated_file_access_db['db_path']):
            from sqlite.reader import CLISqliteReader

            with CLISqliteReader() as reader:
                reader.mark_file_accesses_synced(populated_file_access_db['session_id'])

                # Verify all are synced
                cursor = reader.conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM file_access_log
                    WHERE session_id = ? AND synced_to_neo4j = 0
                """, (populated_file_access_db['session_id'],))
                unsynced = cursor.fetchone()[0]

                assert unsynced == 0

    @pytest.mark.integration
    def test_only_marks_specified_session(self, temp_sqlite_db, sqlite_writer):
        """Should only mark specified session, not others."""
        session1 = 'sync-session-1'
        session2 = 'sync-session-2'
        timestamp = datetime.now().isoformat()

        cursor = sqlite_writer.conn.cursor()

        # Create accesses for both sessions
        for session in [session1, session2]:
            cursor.execute("""
                INSERT INTO file_access_log
                (session_id, file_path, normalized_path, access_mode, tool_name, timestamp, synced_to_neo4j)
                VALUES (?, '/path/file.py', '/path/file.py', 'read', 'Read', ?, 0)
            """, (session, timestamp))

        sqlite_writer.conn.commit()

        with patch('sqlite.reader.get_db_path', return_value=temp_sqlite_db):
            from sqlite.reader import CLISqliteReader

            with CLISqliteReader() as reader:
                reader.mark_file_accesses_synced(session1)

                # Session 1 should be synced
                cursor = reader.conn.cursor()
                cursor.execute("""
                    SELECT synced_to_neo4j FROM file_access_log
                    WHERE session_id = ?
                """, (session1,))
                assert cursor.fetchone()[0] == 1

                # Session 2 should still be unsynced
                cursor.execute("""
                    SELECT synced_to_neo4j FROM file_access_log
                    WHERE session_id = ?
                """, (session2,))
                assert cursor.fetchone()[0] == 0


# =============================================================================
# Test Existing Reader Methods (regression)
# =============================================================================

class TestExistingReaderMethods:
    """Regression tests for existing reader methods."""

    @pytest.mark.integration
    def test_get_session_events(self, populated_file_access_db, sqlite_writer):
        """get_session_events should still work."""
        # Add an event to the session
        cursor = sqlite_writer.conn.cursor()
        cursor.execute("""
            INSERT INTO events (session_id, event_type, timestamp, raw_json)
            VALUES (?, 'PostToolUse', ?, '{}')
        """, (populated_file_access_db['session_id'], datetime.now().isoformat()))
        sqlite_writer.conn.commit()

        with patch('sqlite.reader.get_db_path', return_value=populated_file_access_db['db_path']):
            from sqlite.reader import CLISqliteReader

            with CLISqliteReader() as reader:
                result = reader.get_session_events(populated_file_access_db['session_id'])
                assert len(result) >= 1

    @pytest.mark.integration
    def test_get_session_summary(self, populated_file_access_db, sqlite_writer):
        """get_session_summary should still work."""
        # Add events to the session
        cursor = sqlite_writer.conn.cursor()
        cursor.execute("""
            INSERT INTO events (session_id, event_type, timestamp, raw_json, tool_name)
            VALUES (?, 'PostToolUse', ?, '{}', 'Read')
        """, (populated_file_access_db['session_id'], datetime.now().isoformat()))
        sqlite_writer.conn.commit()

        with patch('sqlite.reader.get_db_path', return_value=populated_file_access_db['db_path']):
            from sqlite.reader import CLISqliteReader

            with CLISqliteReader() as reader:
                result = reader.get_session_summary(populated_file_access_db['session_id'])

                assert 'prompt_count' in result
                assert 'tool_count' in result
                assert 'tool_usage' in result
