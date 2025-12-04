"""Helper functions for SQLite hooks data extraction and analysis."""

import hashlib
import json
import platform
import subprocess
import sys
from typing import Any, Optional, Tuple


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
        Category string: 'file_ops', 'search', 'bash', 'web', 'task', 'question', 'plan', or 'other'
    """
    if not tool_name:
        return 'other'
    for category, tools in TOOL_CATEGORIES.items():
        if tool_name in tools:
            return category
    return 'other'


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
