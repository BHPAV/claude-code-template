"""
Configuration for Claude Code hooks.

Standalone configuration for hook scripts, independent of agent configuration.
"""

import os
from dataclasses import dataclass, field


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
