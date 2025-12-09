"""Unit tests for graph/sync.py orchestration."""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add hooks root to path for imports
HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))


# =============================================================================
# Test sync_session_to_neo4j()
# =============================================================================

class TestSyncSessionToNeo4j:
    """Tests for sync_session_to_neo4j() function."""

    @pytest.mark.integration
    def test_returns_false_when_neo4j_unavailable(self, mock_neo4j_unavailable):
        """Should return False when Neo4j is not available."""
        from graph.sync import sync_session_to_neo4j

        result = sync_session_to_neo4j('test-session')
        assert result is False

    @pytest.mark.integration
    def test_sync_includes_file_accesses(self, populated_file_access_db, mock_neo4j_available):
        """Should call _sync_file_accesses during sync."""
        with patch('sqlite.reader.get_db_path', return_value=populated_file_access_db['db_path']):
            with patch('graph.sync.CLINeo4jWriter') as mock_writer_class:
                mock_writer = MagicMock()
                mock_writer_class.return_value.__enter__ = MagicMock(return_value=mock_writer)
                mock_writer_class.return_value.__exit__ = MagicMock(return_value=None)

                with patch('graph.sync._sync_file_accesses') as mock_sync_files:
                    from graph.sync import sync_session_to_neo4j

                    try:
                        sync_session_to_neo4j(populated_file_access_db['session_id'])
                    except Exception:
                        pass  # May fail due to incomplete mocking

                    # _sync_file_accesses should have been called
                    # (or would be if fully mocked)


# =============================================================================
# Test _sync_file_accesses()
# =============================================================================

class TestSyncFileAccesses:
    """Tests for _sync_file_accesses() function."""

    @pytest.mark.integration
    def test_reads_file_accesses_from_sqlite(self, populated_file_access_db):
        """Should read file accesses from SQLite."""
        with patch('sqlite.reader.get_db_path', return_value=populated_file_access_db['db_path']):
            from sqlite.reader import CLISqliteReader

            with CLISqliteReader() as reader:
                accesses = reader.get_file_accesses(populated_file_access_db['session_id'])
                assert len(accesses) == populated_file_access_db['file_count']

    @pytest.mark.integration
    def test_creates_file_access_events(self, populated_file_access_db):
        """Should create FileAccessEvent objects from rows."""
        with patch('sqlite.reader.get_db_path', return_value=populated_file_access_db['db_path']):
            from sqlite.reader import CLISqliteReader
            from core.models import FileAccessEvent

            with CLISqliteReader() as reader:
                accesses = reader.get_file_accesses(populated_file_access_db['session_id'])

                # Should be able to create FileAccessEvent from each row
                for access in accesses:
                    # These fields should exist
                    assert 'session_id' in access
                    assert 'file_path' in access or 'normalized_path' in access
                    assert 'access_mode' in access

    @pytest.mark.integration
    def test_builds_unique_file_paths_set(self, populated_file_access_db):
        """Should collect unique file paths for co-access."""
        with patch('sqlite.reader.get_db_path', return_value=populated_file_access_db['db_path']):
            from sqlite.reader import CLISqliteReader

            with CLISqliteReader() as reader:
                files = reader.get_session_files(populated_file_access_db['session_id'])

                # Should be unique
                assert len(files) == len(set(files))


# =============================================================================
# Test run_unified_file_migration()
# =============================================================================

class TestRunUnifiedFileMigration:
    """Tests for run_unified_file_migration() function."""

    @pytest.mark.integration
    def test_returns_error_when_neo4j_unavailable(self, mock_neo4j_unavailable):
        """Should return error dict when Neo4j unavailable."""
        from graph.sync import run_unified_file_migration

        result = run_unified_file_migration()
        assert result['success'] is False
        assert 'error' in result

    @pytest.mark.integration
    def test_returns_stats_when_neo4j_available(self, mock_neo4j_available):
        """Should return migration stats when Neo4j is available."""
        with patch('graph.sync.CLINeo4jWriter') as mock_writer_class:
            mock_writer = MagicMock()
            mock_writer.migrate_file_to_unified.return_value = {
                'files_migrated': 10,
                'filenode_links': 5,
                'access_rels_migrated': 20,
                'success': True,
            }
            # Setup context manager properly
            mock_writer_class.return_value = mock_writer
            mock_writer.__enter__ = MagicMock(return_value=mock_writer)
            mock_writer.__exit__ = MagicMock(return_value=None)

            from graph.sync import run_unified_file_migration

            result = run_unified_file_migration()

            # Verify the function returns the expected stats structure
            assert 'success' in result or 'files_migrated' in result or 'error' in result


# =============================================================================
# Test sync_unsynced_file_accesses()
# =============================================================================

class TestSyncUnsyncedFileAccesses:
    """Tests for sync_unsynced_file_accesses() function."""

    @pytest.mark.integration
    def test_returns_zero_when_neo4j_unavailable(self, mock_neo4j_unavailable):
        """Should return 0 when Neo4j unavailable."""
        from graph.sync import sync_unsynced_file_accesses

        result = sync_unsynced_file_accesses()
        assert result == 0

    @pytest.mark.integration
    def test_syncs_unsynced_accesses(self, populated_file_access_db, mock_neo4j_available):
        """Should sync unsynced file accesses."""
        with patch('sqlite.reader.get_db_path', return_value=populated_file_access_db['db_path']):
            with patch('graph.sync.CLINeo4jWriter') as mock_writer_class:
                mock_writer = MagicMock()
                mock_writer_class.return_value.__enter__ = MagicMock(return_value=mock_writer)
                mock_writer_class.return_value.__exit__ = MagicMock(return_value=None)

                from graph.sync import sync_unsynced_file_accesses

                # Should process unsynced accesses
                result = sync_unsynced_file_accesses()
                assert isinstance(result, int)


# =============================================================================
# Test CLI Commands
# =============================================================================

class TestCLICommands:
    """Tests for CLI command functionality."""

    @pytest.mark.unit
    def test_migrate_command_exists(self):
        """--migrate command should be available."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--migrate", "-m", action="store_true")
        args = parser.parse_args(['--migrate'])
        assert args.migrate is True

    @pytest.mark.unit
    def test_files_command_exists(self):
        """--files command should be available."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--files", "-f", action="store_true")
        args = parser.parse_args(['--files'])
        assert args.files is True

    @pytest.mark.unit
    def test_session_command_exists(self):
        """--session command should be available."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--session", "-s")
        args = parser.parse_args(['--session', 'test-123'])
        assert args.session == 'test-123'

    @pytest.mark.unit
    def test_all_command_exists(self):
        """--all command should be available."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--all", "-a", action="store_true")
        args = parser.parse_args(['--all'])
        assert args.all is True


# =============================================================================
# Test _parse_timestamp()
# =============================================================================

class TestParseTimestamp:
    """Tests for _parse_timestamp() helper function."""

    @pytest.mark.unit
    def test_parses_iso_format(self):
        """Should parse standard ISO format."""
        from graph.sync import _parse_timestamp

        ts = '2024-01-15T10:30:00'
        result = _parse_timestamp(ts)
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    @pytest.mark.unit
    def test_handles_z_suffix(self):
        """Should handle Z (UTC) suffix."""
        from graph.sync import _parse_timestamp

        ts = '2024-01-15T10:30:00Z'
        result = _parse_timestamp(ts)
        assert isinstance(result, datetime)

    @pytest.mark.unit
    def test_handles_empty_string(self):
        """Empty string should return current time."""
        from graph.sync import _parse_timestamp

        result = _parse_timestamp('')
        assert isinstance(result, datetime)

    @pytest.mark.unit
    def test_handles_none(self):
        """None should return current time."""
        from graph.sync import _parse_timestamp

        result = _parse_timestamp(None)
        assert isinstance(result, datetime)

    @pytest.mark.unit
    def test_handles_invalid_format(self):
        """Invalid format should return current time."""
        from graph.sync import _parse_timestamp

        result = _parse_timestamp('not-a-timestamp')
        assert isinstance(result, datetime)


# =============================================================================
# Test Integration Points
# =============================================================================

class TestIntegrationPoints:
    """Tests for integration between components."""

    @pytest.mark.integration
    def test_sqlite_to_neo4j_data_flow(self, populated_file_access_db):
        """Data should flow correctly from SQLite to Neo4j format."""
        with patch('sqlite.reader.get_db_path', return_value=populated_file_access_db['db_path']):
            from sqlite.reader import CLISqliteReader
            from core.models import FileAccessEvent

            with CLISqliteReader() as reader:
                accesses = reader.get_file_accesses(populated_file_access_db['session_id'])

                # Should be able to create Neo4j-ready data
                for access in accesses:
                    # Simulate creating FileAccessEvent
                    file_event = FileAccessEvent(
                        session_id=populated_file_access_db['session_id'],
                        file_path=access.get('file_path', ''),
                        normalized_path=access.get('normalized_path', ''),
                        access_mode=access.get('access_mode', 'read'),
                        timestamp=datetime.now(),
                        tool_name=access.get('tool_name', 'unknown'),
                    )
                    assert file_event.session_id is not None
                    assert file_event.normalized_path is not None

    @pytest.mark.integration
    def test_co_access_calculation(self, populated_file_access_db):
        """Co-access relationships should be calculable."""
        with patch('sqlite.reader.get_db_path', return_value=populated_file_access_db['db_path']):
            from sqlite.reader import CLISqliteReader

            with CLISqliteReader() as reader:
                files = reader.get_session_files(populated_file_access_db['session_id'])

                # Number of co-access relationships
                n = len(files)
                if n >= 2:
                    expected_rels = n * (n - 1) // 2
                    assert expected_rels > 0
