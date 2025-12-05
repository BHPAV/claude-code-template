"""
Unified configuration for Claude Code hooks.

Combines SQLite and Neo4j configuration in one module.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


# ============================================================================
# SQLite Configuration
# ============================================================================

def get_db_path() -> Path:
    """Get SQLite database path from environment or default.

    Environment variable: SQLITE_DB_PATH

    Returns:
        Path to the SQLite database file
    """
    default = Path(__file__).parent.parent / "data" / "claude_hooks.db"
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

    Environment variable: HOOK_LOG_LEVEL

    Returns:
        Log level string (default: WARNING)
    """
    return os.environ.get("HOOK_LOG_LEVEL", "WARNING")


# ============================================================================
# Neo4j Configuration
# ============================================================================

@dataclass
class Neo4jConfig:
    """Configuration for Neo4j connection."""

    uri: str = field(default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    user: str = field(default_factory=lambda: os.getenv("NEO4J_USER", "neo4j"))
    password: str = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", "password"))
    database: str = field(default_factory=lambda: os.getenv("NEO4J_DATABASE", "neo4j"))

    # Connection pool settings
    max_connection_pool_size: int = 50
    connection_timeout: float = 5.0
    max_connection_lifetime: float = 30.0


def load_neo4j_config() -> Neo4jConfig:
    """
    Load Neo4j configuration from environment variables.

    Environment variables:
    - NEO4J_URI (default: bolt://localhost:7687)
    - NEO4J_USER (default: neo4j)
    - NEO4J_PASSWORD (default: password)
    - NEO4J_DATABASE (default: neo4j)

    Returns:
        Neo4jConfig: Configuration object with connection settings
    """
    return Neo4jConfig()


def is_neo4j_available() -> bool:
    """
    Check if Neo4j is reachable.

    Returns:
        bool: True if Neo4j is reachable, False otherwise.
    """
    try:
        from neo4j import GraphDatabase

        config = load_neo4j_config()
        driver = GraphDatabase.driver(
            config.uri,
            auth=(config.user, config.password),
            connection_timeout=config.connection_timeout
        )
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception:
        return False
