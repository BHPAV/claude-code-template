"""SQLite configuration loader for Claude Code hooks."""
import os
from pathlib import Path


def get_db_path() -> Path:
    """Get SQLite database path from environment or default.

    Environment variable: SQLITE_DB_PATH

    Returns:
        Path to the SQLite database file
    """
    default = Path(__file__).parent / "claude_hooks.db"
    return Path(os.environ.get("SQLITE_DB_PATH", default))


def is_sqlite_available() -> bool:
    """Check if SQLite database is accessible.

    Creates parent directories if needed.

    Returns:
        True if database can be connected to, False otherwise
    """
    try:
        import sqlite3
        path = get_db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
        conn.close()
        return True
    except Exception:
        return False


def get_log_level() -> str:
    """Get logging level from environment.

    Environment variable: SQLITE_HOOK_LOG_LEVEL

    Returns:
        Log level string (default: WARNING)
    """
    return os.environ.get("SQLITE_HOOK_LOG_LEVEL", "WARNING")
