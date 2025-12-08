"""Unit tests for core/models.py data models."""

import sys
from datetime import datetime
from pathlib import Path

import pytest

# Add hooks root to path for imports
HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from core.models import (
    CLISessionStartEvent,
    CLISessionEndEvent,
    CLIToolCallEvent,
    CLIToolResultEvent,
    CLIPromptEvent,
    FileAccessEvent,
)


# =============================================================================
# Test CLISessionStartEvent
# =============================================================================

class TestCLISessionStartEvent:
    """Tests for CLISessionStartEvent dataclass."""

    @pytest.mark.unit
    def test_required_fields(self):
        """Required fields should be settable."""
        event = CLISessionStartEvent(
            session_id='test-session-001',
            timestamp=datetime.now(),
            working_dir='/project',
        )
        assert event.session_id == 'test-session-001'
        assert isinstance(event.timestamp, datetime)
        assert event.working_dir == '/project'

    @pytest.mark.unit
    def test_default_metadata(self):
        """Metadata should default to empty dict."""
        event = CLISessionStartEvent(
            session_id='test-session-001',
            timestamp=datetime.now(),
            working_dir='/project',
        )
        assert event.metadata == {}

    @pytest.mark.unit
    def test_custom_metadata(self):
        """Custom metadata should be stored."""
        metadata = {'platform': 'win32', 'git_branch': 'main'}
        event = CLISessionStartEvent(
            session_id='test-session-001',
            timestamp=datetime.now(),
            working_dir='/project',
            metadata=metadata,
        )
        assert event.metadata == metadata
        assert event.metadata['platform'] == 'win32'


# =============================================================================
# Test CLISessionEndEvent
# =============================================================================

class TestCLISessionEndEvent:
    """Tests for CLISessionEndEvent dataclass."""

    @pytest.mark.unit
    def test_required_fields(self):
        """Required fields should be settable."""
        event = CLISessionEndEvent(
            session_id='test-session-001',
            timestamp=datetime.now(),
            duration_seconds=120.5,
        )
        assert event.session_id == 'test-session-001'
        assert event.duration_seconds == 120.5

    @pytest.mark.unit
    def test_default_counters(self):
        """Counters should default to 0."""
        event = CLISessionEndEvent(
            session_id='test-session-001',
            timestamp=datetime.now(),
            duration_seconds=60.0,
        )
        assert event.tool_count == 0
        assert event.prompt_count == 0

    @pytest.mark.unit
    def test_custom_counters(self):
        """Custom counters should be stored."""
        event = CLISessionEndEvent(
            session_id='test-session-001',
            timestamp=datetime.now(),
            duration_seconds=300.0,
            tool_count=15,
            prompt_count=5,
        )
        assert event.tool_count == 15
        assert event.prompt_count == 5


# =============================================================================
# Test CLIToolCallEvent
# =============================================================================

class TestCLIToolCallEvent:
    """Tests for CLIToolCallEvent dataclass."""

    @pytest.mark.unit
    def test_required_fields(self):
        """Required fields should be settable."""
        event = CLIToolCallEvent(
            session_id='test-session-001',
            tool_name='Read',
            tool_input={'file_path': '/path/file.py'},
            timestamp=datetime.now(),
            call_id='tool_use_001',
        )
        assert event.session_id == 'test-session-001'
        assert event.tool_name == 'Read'
        assert event.tool_input['file_path'] == '/path/file.py'

    @pytest.mark.unit
    def test_default_sequence_index(self):
        """Sequence index should default to 0."""
        event = CLIToolCallEvent(
            session_id='test-session-001',
            tool_name='Read',
            tool_input={},
            timestamp=datetime.now(),
            call_id='tool_use_001',
        )
        assert event.sequence_index == 0


# =============================================================================
# Test CLIToolResultEvent
# =============================================================================

class TestCLIToolResultEvent:
    """Tests for CLIToolResultEvent dataclass."""

    @pytest.mark.unit
    def test_required_fields(self):
        """Required fields should be settable."""
        event = CLIToolResultEvent(
            session_id='test-session-001',
            tool_name='Read',
            tool_input={'file_path': '/path/file.py'},
            tool_output='file contents',
            timestamp=datetime.now(),
            call_id='tool_use_001',
        )
        assert event.session_id == 'test-session-001'
        assert event.tool_name == 'Read'
        assert event.tool_output == 'file contents'

    @pytest.mark.unit
    def test_default_success(self):
        """Success should default to True."""
        event = CLIToolResultEvent(
            session_id='test-session-001',
            tool_name='Read',
            tool_input={},
            tool_output='',
            timestamp=datetime.now(),
            call_id='tool_use_001',
        )
        assert event.success is True

    @pytest.mark.unit
    def test_default_optional_fields(self):
        """Optional fields should have correct defaults."""
        event = CLIToolResultEvent(
            session_id='test-session-001',
            tool_name='Read',
            tool_input={},
            tool_output='',
            timestamp=datetime.now(),
            call_id='tool_use_001',
        )
        assert event.duration_ms is None
        assert event.error is None
        assert event.tool_category is None
        assert event.subagent_type is None
        assert event.command is None
        assert event.pattern is None
        assert event.url is None
        assert event.file_path is None
        assert event.output_size_bytes is None
        assert event.has_stderr is False
        assert event.sequence_index == 0

    @pytest.mark.unit
    def test_new_file_tracking_fields_exist(self):
        """New file tracking fields from v7 should exist."""
        event = CLIToolResultEvent(
            session_id='test-session-001',
            tool_name='Read',
            tool_input={},
            tool_output='',
            timestamp=datetime.now(),
            call_id='tool_use_001',
        )
        # These fields should exist and have default values
        assert hasattr(event, 'file_paths')
        assert hasattr(event, 'access_mode')
        assert hasattr(event, 'project_root')
        assert hasattr(event, 'glob_matches')
        assert hasattr(event, 'grep_matches')

    @pytest.mark.unit
    def test_file_paths_default_empty_list(self):
        """file_paths should default to empty list."""
        event = CLIToolResultEvent(
            session_id='test-session-001',
            tool_name='Read',
            tool_input={},
            tool_output='',
            timestamp=datetime.now(),
            call_id='tool_use_001',
        )
        assert event.file_paths == []

    @pytest.mark.unit
    def test_glob_matches_default_empty_list(self):
        """glob_matches should default to empty list."""
        event = CLIToolResultEvent(
            session_id='test-session-001',
            tool_name='Glob',
            tool_input={},
            tool_output='',
            timestamp=datetime.now(),
            call_id='tool_use_001',
        )
        assert event.glob_matches == []

    @pytest.mark.unit
    def test_grep_matches_default_empty_list(self):
        """grep_matches should default to empty list."""
        event = CLIToolResultEvent(
            session_id='test-session-001',
            tool_name='Grep',
            tool_input={},
            tool_output='',
            timestamp=datetime.now(),
            call_id='tool_use_001',
        )
        assert event.grep_matches == []

    @pytest.mark.unit
    def test_access_mode_default_none(self):
        """access_mode should default to None."""
        event = CLIToolResultEvent(
            session_id='test-session-001',
            tool_name='Read',
            tool_input={},
            tool_output='',
            timestamp=datetime.now(),
            call_id='tool_use_001',
        )
        assert event.access_mode is None

    @pytest.mark.unit
    def test_project_root_default_none(self):
        """project_root should default to None."""
        event = CLIToolResultEvent(
            session_id='test-session-001',
            tool_name='Read',
            tool_input={},
            tool_output='',
            timestamp=datetime.now(),
            call_id='tool_use_001',
        )
        assert event.project_root is None

    @pytest.mark.unit
    def test_file_path_backward_compatibility(self):
        """file_path (singular) should still work for backward compat."""
        event = CLIToolResultEvent(
            session_id='test-session-001',
            tool_name='Read',
            tool_input={},
            tool_output='',
            timestamp=datetime.now(),
            call_id='tool_use_001',
            file_path='/project/src/main.py',
        )
        assert event.file_path == '/project/src/main.py'

    @pytest.mark.unit
    def test_all_file_tracking_fields_populated(self):
        """All new file tracking fields should be settable."""
        event = CLIToolResultEvent(
            session_id='test-session-001',
            tool_name='Glob',
            tool_input={'path': '/src', 'pattern': '*.py'},
            tool_output='main.py\nutils.py',
            timestamp=datetime.now(),
            call_id='tool_use_001',
            file_paths=['/src/main.py', '/src/utils.py'],
            access_mode='search',
            project_root='/project',
            glob_matches=['main.py', 'utils.py'],
            grep_matches=[],
        )
        assert event.file_paths == ['/src/main.py', '/src/utils.py']
        assert event.access_mode == 'search'
        assert event.project_root == '/project'
        assert event.glob_matches == ['main.py', 'utils.py']
        assert event.grep_matches == []


# =============================================================================
# Test CLIPromptEvent
# =============================================================================

class TestCLIPromptEvent:
    """Tests for CLIPromptEvent dataclass."""

    @pytest.mark.unit
    def test_required_fields(self):
        """Required fields should be settable."""
        event = CLIPromptEvent(
            session_id='test-session-001',
            prompt_text='Help me fix this bug',
            timestamp=datetime.now(),
        )
        assert event.session_id == 'test-session-001'
        assert event.prompt_text == 'Help me fix this bug'

    @pytest.mark.unit
    def test_default_optional_fields(self):
        """Optional fields should have correct defaults."""
        event = CLIPromptEvent(
            session_id='test-session-001',
            prompt_text='Hello',
            timestamp=datetime.now(),
        )
        assert event.intent_type is None
        assert event.sequence_index == 0


# =============================================================================
# Test FileAccessEvent
# =============================================================================

class TestFileAccessEvent:
    """Tests for FileAccessEvent dataclass."""

    @pytest.mark.unit
    def test_required_fields(self):
        """Required fields should be settable."""
        event = FileAccessEvent(
            session_id='test-session-001',
            file_path='/project/src/main.py',
            normalized_path='/project/src/main.py',
            access_mode='read',
            timestamp=datetime.now(),
            tool_name='Read',
        )
        assert event.session_id == 'test-session-001'
        assert event.file_path == '/project/src/main.py'
        assert event.normalized_path == '/project/src/main.py'
        assert event.access_mode == 'read'
        assert event.tool_name == 'Read'

    @pytest.mark.unit
    def test_default_event_id(self):
        """event_id should default to None."""
        event = FileAccessEvent(
            session_id='test-session-001',
            file_path='/path/file.py',
            normalized_path='/path/file.py',
            access_mode='read',
            timestamp=datetime.now(),
            tool_name='Read',
        )
        assert event.event_id is None

    @pytest.mark.unit
    def test_default_project_root(self):
        """project_root should default to None."""
        event = FileAccessEvent(
            session_id='test-session-001',
            file_path='/path/file.py',
            normalized_path='/path/file.py',
            access_mode='read',
            timestamp=datetime.now(),
            tool_name='Read',
        )
        assert event.project_root is None

    @pytest.mark.unit
    def test_default_line_numbers(self):
        """line_numbers should default to empty list."""
        event = FileAccessEvent(
            session_id='test-session-001',
            file_path='/path/file.py',
            normalized_path='/path/file.py',
            access_mode='read',
            timestamp=datetime.now(),
            tool_name='Read',
        )
        assert event.line_numbers == []

    @pytest.mark.unit
    def test_default_is_primary_target(self):
        """is_primary_target should default to True."""
        event = FileAccessEvent(
            session_id='test-session-001',
            file_path='/path/file.py',
            normalized_path='/path/file.py',
            access_mode='read',
            timestamp=datetime.now(),
            tool_name='Read',
        )
        assert event.is_primary_target is True

    @pytest.mark.unit
    def test_default_is_glob_expansion(self):
        """is_glob_expansion should default to False."""
        event = FileAccessEvent(
            session_id='test-session-001',
            file_path='/path/file.py',
            normalized_path='/path/file.py',
            access_mode='read',
            timestamp=datetime.now(),
            tool_name='Read',
        )
        assert event.is_glob_expansion is False

    @pytest.mark.unit
    def test_default_synced_to_neo4j(self):
        """synced_to_neo4j should default to False."""
        event = FileAccessEvent(
            session_id='test-session-001',
            file_path='/path/file.py',
            normalized_path='/path/file.py',
            access_mode='read',
            timestamp=datetime.now(),
            tool_name='Read',
        )
        assert event.synced_to_neo4j is False

    @pytest.mark.unit
    def test_all_fields_populated(self):
        """All fields should be settable."""
        event = FileAccessEvent(
            session_id='test-session-001',
            file_path='/project/src/main.py',
            normalized_path='/project/src/main.py',
            access_mode='search',
            timestamp=datetime.now(),
            tool_name='Grep',
            event_id=42,
            project_root='/project',
            line_numbers=[10, 25, 50],
            is_primary_target=False,
            is_glob_expansion=True,
            synced_to_neo4j=True,
        )
        assert event.event_id == 42
        assert event.project_root == '/project'
        assert event.line_numbers == [10, 25, 50]
        assert event.is_primary_target is False
        assert event.is_glob_expansion is True
        assert event.synced_to_neo4j is True

    @pytest.mark.unit
    def test_access_modes(self):
        """Various access modes should be accepted."""
        modes = ['read', 'write', 'modify', 'search', 'execute']
        for mode in modes:
            event = FileAccessEvent(
                session_id='test-session-001',
                file_path='/path/file.py',
                normalized_path='/path/file.py',
                access_mode=mode,
                timestamp=datetime.now(),
                tool_name='Test',
            )
            assert event.access_mode == mode

    @pytest.mark.unit
    def test_line_numbers_type(self):
        """line_numbers should accept list of integers."""
        event = FileAccessEvent(
            session_id='test-session-001',
            file_path='/path/file.py',
            normalized_path='/path/file.py',
            access_mode='search',
            timestamp=datetime.now(),
            tool_name='Grep',
            line_numbers=[1, 10, 100, 1000],
        )
        assert all(isinstance(n, int) for n in event.line_numbers)
        assert event.line_numbers == [1, 10, 100, 1000]

    @pytest.mark.unit
    def test_timestamp_type(self):
        """timestamp should be a datetime object."""
        now = datetime.now()
        event = FileAccessEvent(
            session_id='test-session-001',
            file_path='/path/file.py',
            normalized_path='/path/file.py',
            access_mode='read',
            timestamp=now,
            tool_name='Read',
        )
        assert isinstance(event.timestamp, datetime)
        assert event.timestamp == now
