"""Helper functions for hooks data extraction and analysis."""

import hashlib
import json
import platform
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Tool category classification
TOOL_CATEGORIES = {
    'file_ops': ['Read', 'Write', 'Edit', 'MultiEdit', 'NotebookEdit'],
    'search': ['Grep', 'Glob'],
    'bash': ['Bash', 'BashOutput', 'KillShell'],
    'web': ['WebFetch', 'WebSearch'],
    'task': ['Task', 'TodoWrite', 'TodoRead', 'Agent', 'Subagent'],
    'question': ['AskUserQuestion'],
    'plan': ['EnterPlanMode', 'ExitPlanMode'],
}


def classify_tool(tool_name: str) -> str:
    """Classify tool into category.

    Args:
        tool_name: Name of the tool

    Returns:
        Category string: 'file_ops', 'search', 'bash', 'web', 'task', 'question', 'plan', 'mcp', or 'other'
    """
    if not tool_name:
        return 'other'

    # Detect MCP tools by prefix (e.g., mcp__neo4j__read_neo4j_cypher)
    if tool_name.startswith('mcp__'):
        return 'mcp'

    for category, tools in TOOL_CATEGORIES.items():
        if tool_name in tools:
            return category
    return 'other'


def classify_intent(prompt_text: str) -> str:
    """Classify prompt intent based on keywords.

    Args:
        prompt_text: The user's prompt text

    Returns:
        Intent category: 'debug', 'refactor', 'search', 'explain', 'review', or 'implement'
    """
    if not prompt_text:
        return 'implement'

    text = prompt_text.lower()

    if any(kw in text for kw in ['fix', 'bug', 'error', 'broken', 'issue', 'not working', 'crash', 'fail']):
        return 'debug'
    elif any(kw in text for kw in ['refactor', 'clean', 'reorganize', 'restructure', 'simplify', 'improve']):
        return 'refactor'
    elif any(kw in text for kw in ['find', 'search', 'where', 'locate', 'which file', 'look for']):
        return 'search'
    elif any(kw in text for kw in ['explain', 'what does', 'how does', 'why', 'understand', 'what is']):
        return 'explain'
    elif any(kw in text for kw in ['review', 'check', 'look at', 'analyze', 'examine', 'inspect']):
        return 'review'
    else:
        return 'implement'


def extract_file_path(tool_name: str, tool_input: dict) -> Optional[str]:
    """Extract file_path from tool input.

    Args:
        tool_name: Name of the tool
        tool_input: Tool input parameters dict

    Returns:
        File path if found, None otherwise
    """
    if not tool_input:
        return None

    if tool_name in ['Read', 'Write', 'Edit', 'MultiEdit', 'NotebookEdit']:
        return tool_input.get('file_path') or tool_input.get('filePath')
    elif tool_name in ['Glob', 'Grep']:
        return tool_input.get('path')
    return None


def extract_command(tool_name: str, tool_input: dict) -> Optional[str]:
    """Extract command from Bash tool input (first line, max 200 chars).

    Args:
        tool_name: Name of the tool
        tool_input: Tool input parameters dict

    Returns:
        First line of command truncated to 200 chars, or None
    """
    if tool_name not in ['Bash', 'BashOutput']:
        return None
    if not tool_input:
        return None

    cmd = tool_input.get('command', '')
    if not cmd:
        return None

    first_line = cmd.split('\n')[0].strip()
    return first_line[:200] if first_line else None


def extract_pattern(tool_name: str, tool_input: dict) -> Optional[str]:
    """Extract pattern from search tools.

    Args:
        tool_name: Name of the tool
        tool_input: Tool input parameters dict

    Returns:
        Search pattern if found, None otherwise
    """
    if not tool_input:
        return None

    if tool_name in ['Grep', 'Glob']:
        return tool_input.get('pattern')
    return None


def extract_url(tool_name: str, tool_input: dict) -> Optional[str]:
    """Extract URL from web tools.

    Args:
        tool_name: Name of the tool
        tool_input: Tool input parameters dict

    Returns:
        URL or query string if found, None otherwise
    """
    if not tool_input:
        return None

    if tool_name == 'WebFetch':
        return tool_input.get('url')
    elif tool_name == 'WebSearch':
        return tool_input.get('query')
    return None


def extract_subagent_type(tool_name: str, tool_input: dict) -> Optional[str]:
    """Extract subagent_type from Task tool input.

    Args:
        tool_name: Name of the tool
        tool_input: Tool input parameters dict

    Returns:
        Subagent type if Task tool, None otherwise
    """
    if tool_name != 'Task' or not tool_input:
        return None
    return tool_input.get('subagent_type')


def compute_prompt_hash(prompt_text: str) -> str:
    """Compute SHA256 hash of prompt for deduplication.

    Args:
        prompt_text: The prompt text to hash

    Returns:
        SHA256 hex digest
    """
    if not prompt_text:
        return hashlib.sha256(b'').hexdigest()
    return hashlib.sha256(prompt_text.encode('utf-8')).hexdigest()


def count_words(text: str) -> int:
    """Count words in text.

    Args:
        text: Text to count words in

    Returns:
        Number of words
    """
    if not text:
        return 0
    return len(text.split())


def detect_success(tool_response: Any) -> Tuple[bool, Optional[str], bool, bool]:
    """Analyze tool response for success/failure.

    Args:
        tool_response: The tool response (dict or string)

    Returns:
        Tuple of (success, error_message, has_stderr, was_interrupted)
    """
    if tool_response is None:
        return True, None, False, False

    # Handle dict response (from tool_response field)
    if isinstance(tool_response, dict):
        stderr = tool_response.get('stderr', '') or ''
        stdout = tool_response.get('stdout', '') or ''
        interrupted = tool_response.get('interrupted', False)

        has_stderr = bool(stderr and stderr.strip())

        # Check for error indicators
        combined_output = f"{stdout} {stderr}".lower()
        error_keywords = ['error', 'failed', 'exception', 'traceback', 'fatal', 'denied', 'permission denied']

        has_error = any(kw in combined_output for kw in error_keywords)

        error_msg = None
        if has_error:
            # Prefer stderr for error message
            if stderr and stderr.strip():
                error_msg = stderr.strip()[:500]
            elif stdout:
                # Extract error lines from stdout
                error_lines = [line for line in stdout.split('\n')
                              if any(kw in line.lower() for kw in error_keywords)]
                if error_lines:
                    error_msg = '\n'.join(error_lines[:5])[:500]

        success = not has_error and not interrupted
        return success, error_msg, has_stderr, bool(interrupted)

    # Handle string response
    output_str = str(tool_response).lower()
    error_keywords = ['error', 'failed', 'exception', 'traceback', 'fatal', 'denied']
    has_error = any(kw in output_str for kw in error_keywords)

    error_msg = None
    if has_error:
        error_msg = str(tool_response)[:500]

    return not has_error, error_msg, False, False


def get_output_size(tool_response: Any) -> int:
    """Calculate response size in bytes.

    Args:
        tool_response: The tool response

    Returns:
        Size in bytes
    """
    if tool_response is None:
        return 0
    if isinstance(tool_response, dict):
        return len(json.dumps(tool_response, default=str).encode('utf-8'))
    return len(str(tool_response).encode('utf-8'))


def get_git_branch() -> Optional[str]:
    """Get current git branch if in a repo.

    Returns:
        Branch name or None if not in a git repo
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def get_environment_context() -> dict:
    """Gather environment context information.

    Returns:
        Dict with git_branch, platform, python_version
    """
    return {
        'git_branch': get_git_branch(),
        'platform': f"{platform.system()} {platform.release()}",
        'python_version': platform.python_version()
    }


def sanitize_tool_input(tool_input: dict) -> dict:
    """Remove sensitive data from tool inputs before storage.

    Args:
        tool_input: Original tool input dict

    Returns:
        Sanitized copy with sensitive values replaced
    """
    if not tool_input:
        return {}

    sensitive_keys = ['password', 'api_key', 'token', 'secret', 'auth', 'credential', 'key']
    sanitized = {}

    for key, value in tool_input.items():
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            sanitized[key] = '[REDACTED]'
        elif isinstance(value, dict):
            sanitized[key] = sanitize_tool_input(value)
        else:
            sanitized[key] = value

    return sanitized


def normalize_path(path: str) -> Optional[str]:
    """Normalize file path to Unix-style forward slashes.

    Args:
        path: File path to normalize

    Returns:
        Normalized path or None if empty
    """
    if not path:
        return None
    return path.replace('\\', '/')


# -----------------------------------------------------------------------------
# Enhanced File Path Extraction (Phase 1 of Unified File Model)
# -----------------------------------------------------------------------------


@dataclass
class FilePathResult:
    """Result of file path extraction from a tool call."""
    primary_path: Optional[str] = None
    related_paths: List[str] = field(default_factory=list)
    access_mode: str = 'read'  # read, write, modify, search, execute
    is_glob_expansion: bool = False
    project_root: Optional[str] = None


@dataclass
class BashFilePath:
    """A file path extracted from a bash command."""
    path: str
    operation: str  # read, write, delete, copy, move, create, execute, list
    is_source: bool = True
    is_destination: bool = False


@dataclass
class GrepMatch:
    """A file match from grep output."""
    file_path: str
    line_number: Optional[int] = None
    match_content: Optional[str] = None


@dataclass
class ResolvedPath:
    """A resolved and normalized file path."""
    absolute_path: str
    normalized_path: str  # Unix-style forward slashes
    project_root: Optional[str] = None
    relative_to_project: Optional[str] = None
    exists: Optional[bool] = None


# Regex patterns for bash command parsing
BASH_FILE_PATTERNS = {
    # find <path> -name "pattern"
    'find': re.compile(r'^find\s+([^\s]+)', re.IGNORECASE),
    # ls <path>
    'ls': re.compile(r'^ls\s+(?:-[a-zA-Z]+\s+)*([^\s|>]+)', re.IGNORECASE),
    # cat/head/tail <path>
    'cat': re.compile(r'^(?:cat|head|tail)\s+(?:-[a-zA-Z0-9]+\s+)*([^\s|>]+)', re.IGNORECASE),
    # cp <src> <dst>
    'cp': re.compile(r'^cp\s+(?:-[a-zA-Z]+\s+)*([^\s]+)\s+([^\s]+)', re.IGNORECASE),
    # mv <src> <dst>
    'mv': re.compile(r'^mv\s+(?:-[a-zA-Z]+\s+)*([^\s]+)\s+([^\s]+)', re.IGNORECASE),
    # rm <path>
    'rm': re.compile(r'^rm\s+(?:-[a-zA-Z]+\s+)*([^\s]+)', re.IGNORECASE),
    # mkdir <path>
    'mkdir': re.compile(r'^mkdir\s+(?:-[a-zA-Z]+\s+)*([^\s]+)', re.IGNORECASE),
    # touch <path>
    'touch': re.compile(r'^touch\s+([^\s]+)', re.IGNORECASE),
    # python/python3 <script>
    'python': re.compile(r'^python[3]?\s+(?:-[a-zA-Z]+\s+)*([^\s]+\.py)', re.IGNORECASE),
    # git add <path>
    'git_add': re.compile(r'^git\s+add\s+([^\s]+)', re.IGNORECASE),
    # chmod/chown <path>
    'chmod': re.compile(r'^(?:chmod|chown)\s+[^\s]+\s+([^\s]+)', re.IGNORECASE),
    # cd <path>
    'cd': re.compile(r'^cd\s+([^\s;&|]+)', re.IGNORECASE),
}

# Access mode mapping by tool name
TOOL_ACCESS_MODES = {
    'Read': 'read',
    'Write': 'write',
    'Edit': 'modify',
    'MultiEdit': 'modify',
    'NotebookEdit': 'modify',
    'Glob': 'search',
    'Grep': 'search',
    'Bash': 'execute',
    'BashOutput': 'execute',
}


def detect_project_root(path: str) -> Optional[str]:
    """Detect project root by looking for common project markers.

    Walks up from the given path looking for:
    - .git directory
    - package.json
    - pyproject.toml
    - Cargo.toml
    - go.mod

    Args:
        path: Starting path to search from

    Returns:
        Project root path or None if not found
    """
    try:
        current = Path(path)
        if current.is_file():
            current = current.parent

        project_markers = ['.git', 'package.json', 'pyproject.toml', 'Cargo.toml', 'go.mod', 'CLAUDE.md']

        while current != current.parent:
            for marker in project_markers:
                if (current / marker).exists():
                    return str(current)
            current = current.parent
    except Exception:
        pass
    return None


def resolve_file_path(path: str, cwd: Optional[str] = None) -> ResolvedPath:
    """Resolve and normalize a file path.

    Args:
        path: File path to resolve (can be relative or absolute)
        cwd: Current working directory for relative path resolution

    Returns:
        ResolvedPath with absolute and normalized paths
    """
    if not path:
        return ResolvedPath(
            absolute_path='',
            normalized_path='',
            project_root=None,
            relative_to_project=None,
            exists=None
        )

    try:
        p = Path(path)

        # Resolve relative paths
        if not p.is_absolute() and cwd:
            p = Path(cwd) / p

        # Get absolute path (resolve symlinks if possible)
        try:
            absolute = str(p.resolve())
        except Exception:
            absolute = str(p.absolute())

        # Normalize to Unix-style
        normalized = absolute.replace('\\', '/')

        # Detect project root
        project_root = detect_project_root(absolute)

        # Calculate relative path to project
        relative_to_project = None
        if project_root:
            try:
                rel = Path(absolute).relative_to(project_root)
                relative_to_project = str(rel).replace('\\', '/')
            except ValueError:
                pass

        # Check existence (optional, might be slow)
        try:
            exists = p.exists()
        except Exception:
            exists = None

        return ResolvedPath(
            absolute_path=absolute,
            normalized_path=normalized,
            project_root=project_root.replace('\\', '/') if project_root else None,
            relative_to_project=relative_to_project,
            exists=exists
        )
    except Exception:
        # Fallback for invalid paths
        return ResolvedPath(
            absolute_path=path,
            normalized_path=path.replace('\\', '/'),
            project_root=None,
            relative_to_project=None,
            exists=None
        )


def parse_bash_file_paths(command: str, cwd: Optional[str] = None) -> List[BashFilePath]:
    """Parse file paths from a bash command.

    Handles common commands: find, ls, cat, cp, mv, rm, mkdir, touch, python, git add, etc.

    Args:
        command: The bash command string
        cwd: Current working directory for relative path resolution

    Returns:
        List of BashFilePath objects with extracted paths and operations
    """
    if not command:
        return []

    results = []
    cmd = command.strip()

    # Try each pattern
    for cmd_type, pattern in BASH_FILE_PATTERNS.items():
        match = pattern.match(cmd)
        if not match:
            continue

        if cmd_type in ['cp', 'mv']:
            # Source and destination
            src = match.group(1)
            dst = match.group(2)
            op = 'copy' if cmd_type == 'cp' else 'move'
            results.append(BashFilePath(path=src, operation=op, is_source=True, is_destination=False))
            results.append(BashFilePath(path=dst, operation=op, is_source=False, is_destination=True))
        elif cmd_type == 'rm':
            results.append(BashFilePath(path=match.group(1), operation='delete', is_source=True))
        elif cmd_type in ['mkdir', 'touch']:
            results.append(BashFilePath(path=match.group(1), operation='create', is_source=False, is_destination=True))
        elif cmd_type == 'python':
            results.append(BashFilePath(path=match.group(1), operation='execute', is_source=True))
        elif cmd_type in ['cat', 'head', 'tail']:
            results.append(BashFilePath(path=match.group(1), operation='read', is_source=True))
        elif cmd_type in ['ls', 'find', 'cd']:
            results.append(BashFilePath(path=match.group(1), operation='list', is_source=True))
        elif cmd_type == 'git_add':
            results.append(BashFilePath(path=match.group(1), operation='stage', is_source=True))
        elif cmd_type == 'chmod':
            results.append(BashFilePath(path=match.group(1), operation='modify', is_source=True))
        break  # Only match first pattern

    return results


def extract_glob_results(tool_output: Any) -> List[str]:
    """Parse Glob tool output to extract matched file paths.

    Glob output is typically newline-separated file paths.

    Args:
        tool_output: The tool output (string or dict)

    Returns:
        List of file paths found in the output
    """
    if not tool_output:
        return []

    # Handle dict output
    if isinstance(tool_output, dict):
        output_str = tool_output.get('stdout', '') or tool_output.get('output', '') or ''
    else:
        output_str = str(tool_output)

    if not output_str:
        return []

    # Split by newlines and filter empty/invalid lines
    paths = []
    for line in output_str.split('\n'):
        line = line.strip()
        if line and not line.startswith('[') and not line.startswith('{'):
            # Basic validation: looks like a path
            if '/' in line or '\\' in line or line.endswith(('.py', '.js', '.ts', '.json', '.md', '.txt', '.yaml', '.yml')):
                paths.append(line)

    return paths


def extract_grep_file_matches(tool_output: Any) -> List[GrepMatch]:
    """Parse Grep tool output to extract files with matches.

    Grep output can be in various formats:
    - file:line:content (with line numbers)
    - file:content (without line numbers)
    - file (files_with_matches mode)

    Args:
        tool_output: The tool output (string or dict)

    Returns:
        List of GrepMatch objects with file paths and optional line info
    """
    if not tool_output:
        return []

    # Handle dict output
    if isinstance(tool_output, dict):
        output_str = tool_output.get('stdout', '') or tool_output.get('output', '') or ''
    else:
        output_str = str(tool_output)

    if not output_str:
        return []

    matches = []
    seen_files = set()

    for line in output_str.split('\n'):
        line = line.strip()
        if not line:
            continue

        # Try to parse file:line:content format
        # Handle Windows paths (C:\path\file.py:10:content)
        if ':' in line:
            parts = line.split(':')

            # Windows absolute path check (C:\ or D:\)
            if len(parts) >= 2 and len(parts[0]) == 1 and parts[0].isalpha():
                # Reconstruct Windows path
                file_path = f"{parts[0]}:{parts[1]}"
                remaining = parts[2:] if len(parts) > 2 else []
            else:
                file_path = parts[0]
                remaining = parts[1:]

            # Try to extract line number
            line_num = None
            content = None
            if remaining:
                try:
                    line_num = int(remaining[0])
                    content = ':'.join(remaining[1:]) if len(remaining) > 1 else None
                except ValueError:
                    content = ':'.join(remaining)

            if file_path and file_path not in seen_files:
                seen_files.add(file_path)
                matches.append(GrepMatch(
                    file_path=file_path,
                    line_number=line_num,
                    match_content=content[:200] if content else None
                ))
        else:
            # Just a file path (files_with_matches mode)
            if line not in seen_files:
                seen_files.add(line)
                matches.append(GrepMatch(file_path=line))

    return matches


def extract_all_file_paths(
    tool_name: str,
    tool_input: dict,
    tool_output: Any = None,
    cwd: Optional[str] = None
) -> FilePathResult:
    """Extract all file paths from a tool call, including from output.

    This is the enhanced extraction function that handles:
    - Direct file path parameters (Read, Write, Edit, etc.)
    - Bash command parsing
    - Glob result expansion
    - Grep match extraction

    Args:
        tool_name: Name of the tool
        tool_input: Tool input parameters dict
        tool_output: Tool output (for Glob/Grep result extraction)
        cwd: Current working directory

    Returns:
        FilePathResult with primary path, related paths, and access mode
    """
    result = FilePathResult()

    if not tool_input:
        tool_input = {}

    # Determine access mode
    result.access_mode = TOOL_ACCESS_MODES.get(tool_name, 'read')

    # Extract primary path based on tool type
    if tool_name in ['Read', 'Write', 'Edit', 'MultiEdit', 'NotebookEdit']:
        primary = tool_input.get('file_path') or tool_input.get('filePath')
        if primary:
            resolved = resolve_file_path(primary, cwd)
            result.primary_path = resolved.normalized_path
            result.project_root = resolved.project_root

    elif tool_name in ['Glob', 'Grep']:
        # Primary path is the search base directory
        base_path = tool_input.get('path')
        if base_path:
            resolved = resolve_file_path(base_path, cwd)
            result.primary_path = resolved.normalized_path
            result.project_root = resolved.project_root

        # Extract matched files from output
        if tool_output:
            if tool_name == 'Glob':
                glob_results = extract_glob_results(tool_output)
                result.related_paths = [normalize_path(p) for p in glob_results if p]
                result.is_glob_expansion = len(result.related_paths) > 0
            elif tool_name == 'Grep':
                grep_matches = extract_grep_file_matches(tool_output)
                result.related_paths = [normalize_path(m.file_path) for m in grep_matches if m.file_path]

    elif tool_name in ['Bash', 'BashOutput']:
        command = tool_input.get('command', '')
        bash_paths = parse_bash_file_paths(command, cwd)

        if bash_paths:
            # First source path becomes primary
            for bp in bash_paths:
                if bp.is_source:
                    resolved = resolve_file_path(bp.path, cwd)
                    result.primary_path = resolved.normalized_path
                    result.project_root = resolved.project_root

                    # Map bash operation to access mode
                    op_to_mode = {
                        'read': 'read',
                        'delete': 'write',
                        'copy': 'read',
                        'move': 'modify',
                        'create': 'write',
                        'execute': 'execute',
                        'list': 'search',
                        'stage': 'read',
                        'modify': 'modify',
                    }
                    result.access_mode = op_to_mode.get(bp.operation, 'execute')
                    break

            # Add all other paths as related
            for bp in bash_paths:
                resolved = resolve_file_path(bp.path, cwd)
                if resolved.normalized_path and resolved.normalized_path != result.primary_path:
                    result.related_paths.append(resolved.normalized_path)

    return result


# -----------------------------------------------------------------------------
# Transcript Parsing
# -----------------------------------------------------------------------------

def parse_transcript_tool_calls(transcript_path: str) -> List[Dict]:
    """Parse JSONL transcript and extract all tool_use events with their results.

    Reads a Claude Code transcript JSONL file and extracts tool invocations,
    matching tool_use events with their corresponding tool_result events.

    Args:
        transcript_path: Path to the JSONL transcript file

    Returns:
        List of dicts, each containing:
        - tool_name: Name of the tool
        - tool_input: Tool input parameters
        - tool_use_id: Unique tool invocation ID
        - timestamp: When the tool was called
        - tool_result: Result content (if found)

    Raises:
        FileNotFoundError: If transcript file doesn't exist
        json.JSONDecodeError: If JSONL is malformed
    """
    path = Path(transcript_path)
    if not path.exists():
        return []

    tool_calls = []
    tool_results = {}  # Map tool_use_id -> result content

    # First pass: collect all tool results
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Look for tool_result in message content
            message = event.get('message', {})
            content_list = message.get('content', [])

            if not isinstance(content_list, list):
                continue

            for content in content_list:
                if not isinstance(content, dict):
                    continue

                if content.get('type') == 'tool_result':
                    tool_use_id = content.get('tool_use_id')
                    result_content = content.get('content')
                    if tool_use_id and result_content:
                        tool_results[tool_use_id] = result_content

    # Second pass: collect tool_use events and match with results
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            message = event.get('message', {})
            content_list = message.get('content', [])
            timestamp = event.get('timestamp')

            if not isinstance(content_list, list):
                continue

            for content in content_list:
                if not isinstance(content, dict):
                    continue

                if content.get('type') == 'tool_use':
                    tool_use_id = content.get('id')
                    tool_call = {
                        'tool_name': content.get('name'),
                        'tool_input': content.get('input', {}),
                        'tool_use_id': tool_use_id,
                        'timestamp': timestamp,
                        'tool_result': tool_results.get(tool_use_id),
                    }
                    tool_calls.append(tool_call)

    return tool_calls


def get_subagent_session_id_from_transcript(transcript_path: str) -> Optional[str]:
    """Extract the sessionId from a transcript file.

    Args:
        transcript_path: Path to the JSONL transcript file

    Returns:
        Session ID if found, None otherwise
    """
    path = Path(transcript_path)
    if not path.exists():
        return None

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                event = json.loads(line)
                session_id = event.get('sessionId')
                if session_id:
                    return session_id
            except json.JSONDecodeError:
                continue

    return None
