"""
Neo4j write operations for CLI hooks.

Synchronous implementation for hook script execution.
"""

import json
from datetime import datetime
from pathlib import Path

from neo4j import GraphDatabase

from config import load_neo4j_config
from models import (
    CLISessionStartEvent,
    CLISessionEndEvent,
    CLIToolResultEvent,
    CLIPromptEvent,
    sanitize_tool_input,
)


class CLINeo4jWriter:
    """Writes CLI hook events to Neo4j."""

    def __init__(self):
        self.config = load_neo4j_config()
        self.database = self.config.database
        self.driver = GraphDatabase.driver(
            self.config.uri,
            auth=(self.config.user, self.config.password),
            connection_timeout=5.0,
            max_connection_lifetime=30.0,
        )

    def _with_database(self, query: str) -> str:
        """Prepend USE database statement to query."""
        return f"USE {self.database}\n{query}"

    def close(self):
        """Close driver connection."""
        if self.driver:
            self.driver.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def create_session_node(self, event: CLISessionStartEvent) -> str:
        """
        Create ClaudeCodeSession node.

        Args:
            event: Session start event data

        Returns:
            str: Session node ID
        """
        session_node_id = f"cli_session:{event.session_id}"

        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MERGE (s:ClaudeCodeSession {id: $id})
                    SET s.session_id = $session_id,
                        s.start_time = datetime($timestamp),
                        s.working_dir = $working_dir,
                        s.status = 'active',
                        s.tool_call_count = 0,
                        s.prompt_count = 0,
                        s.metadata = $metadata
                    """),
                    {
                        "id": session_node_id,
                        "session_id": event.session_id,
                        "timestamp": event.timestamp.isoformat(),
                        "working_dir": event.working_dir,
                        "metadata": json.dumps(event.metadata),
                    },
                )
            )

        return session_node_id

    def complete_session_node(self, event: CLISessionEndEvent):
        """
        Update ClaudeCodeSession with end data.

        Args:
            event: Session end event data
        """
        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MATCH (s:ClaudeCodeSession {session_id: $session_id})
                    SET s.end_time = datetime($timestamp),
                        s.status = 'completed',
                        s.total_duration_seconds = $duration
                    """),
                    {
                        "session_id": event.session_id,
                        "timestamp": event.timestamp.isoformat(),
                        "duration": event.duration_seconds,
                    },
                )
            )

    def create_tool_call_node(self, event: CLIToolResultEvent):
        """
        Create CLIToolCall node (on PostToolUse).

        Args:
            event: Tool result event data
        """
        tool_id = f"cli_tool:{event.session_id}:{event.timestamp.isoformat()}:{event.tool_name}"

        # Extract file_path if present (for Read/Write/Edit tools)
        file_path = event.tool_input.get("file_path", None)

        # Normalize file path to Unix-style for consistency with repository mapping
        if file_path:
            file_path = Path(file_path).as_posix()

        # Sanitize sensitive data
        sanitized_input = sanitize_tool_input(event.tool_input)

        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MATCH (s:ClaudeCodeSession {session_id: $session_id})
                    CREATE (t:CLIToolCall {
                        id: $id,
                        session_id: $session_id,
                        tool_name: $tool_name,
                        timestamp: datetime($timestamp),
                        inputs: $inputs,
                        outputs: $outputs,
                        duration_ms: $duration_ms,
                        success: $success,
                        error: $error,
                        file_path: $file_path
                    })
                    CREATE (t)-[:PART_OF_SESSION]->(s)

                    // Increment session tool count
                    SET s.tool_call_count = s.tool_call_count + 1

                    // Link to File node if file_path present
                    WITH t, $file_path as fp
                    WHERE fp IS NOT NULL
                    OPTIONAL MATCH (f:File {path: fp})
                    FOREACH (_ IN CASE WHEN f IS NOT NULL THEN [1] ELSE [] END |
                        CREATE (t)-[:ACCESSED_FILE]->(f)
                    )
                    """),
                    {
                        "id": tool_id,
                        "session_id": event.session_id,
                        "tool_name": event.tool_name,
                        "timestamp": event.timestamp.isoformat(),
                        "inputs": json.dumps(sanitized_input)[:2000],  # Truncate
                        "outputs": str(event.tool_output)[:5000],  # Truncate
                        "duration_ms": event.duration_ms,
                        "success": event.success,
                        "error": event.error,
                        "file_path": file_path,
                    },
                )
            )

    def create_prompt_node(self, event: CLIPromptEvent):
        """
        Create CLIPrompt node.

        Args:
            event: Prompt event data
        """
        import hashlib

        prompt_hash = hashlib.sha256(event.prompt_text.encode()).hexdigest()
        prompt_id = f"cli_prompt:{event.session_id}:{event.timestamp.isoformat()}"

        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MATCH (s:ClaudeCodeSession {session_id: $session_id})
                    CREATE (p:CLIPrompt {
                        id: $id,
                        session_id: $session_id,
                        prompt_text: $prompt_text,
                        full_prompt_hash: $hash,
                        timestamp: datetime($timestamp),
                        prompt_length: $length
                    })
                    CREATE (p)-[:PART_OF_SESSION]->(s)

                    // Increment session prompt count
                    SET s.prompt_count = s.prompt_count + 1
                    """),
                    {
                        "id": prompt_id,
                        "session_id": event.session_id,
                        "prompt_text": event.prompt_text[:1000],  # Truncate
                        "hash": prompt_hash,
                        "timestamp": event.timestamp.isoformat(),
                        "length": len(event.prompt_text),
                    },
                )
            )

    def create_metrics_summary(self, session_id: str):
        """
        Generate and store metrics summary for a session.

        Args:
            session_id: Session identifier
        """
        with self.driver.session() as session:
            # Query tool usage - consume results inside transaction
            def query_tool_usage(tx):
                result = tx.run(
                    self._with_database("""
                    MATCH (t:CLIToolCall)-[:PART_OF_SESSION]->(s:ClaudeCodeSession {session_id: $session_id})
                    RETURN
                        t.tool_name as tool,
                        count(*) as count,
                        avg(t.duration_ms) as avg_duration
                    ORDER BY count DESC
                    """),
                    {"session_id": session_id},
                )
                return list(result)  # Consume immediately

            tool_records = session.execute_read(query_tool_usage)

            tool_usage = {}
            total_duration = 0
            total_count = 0
            most_used_tool = None

            for record in tool_records:
                tool = record["tool"]
                count = record["count"]
                avg_dur = record["avg_duration"] or 0

                tool_usage[tool] = count
                total_duration += avg_dur * count
                total_count += count

                if most_used_tool is None:
                    most_used_tool = tool

            avg_duration = total_duration / total_count if total_count > 0 else 0

            # Get prompt count from session - consume results inside transaction
            def query_session_counts(tx):
                result = tx.run(
                    self._with_database("""
                    MATCH (s:ClaudeCodeSession {session_id: $session_id})
                    RETURN s.prompt_count as prompt_count, s.tool_call_count as tool_count
                    """),
                    {"session_id": session_id},
                )
                return list(result)  # Consume immediately

            count_records = session.execute_read(query_session_counts)

            prompt_count = 0
            tool_count = 0
            for record in count_records:
                prompt_count = record["prompt_count"]
                tool_count = record["tool_count"]

            # Create metrics node
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MATCH (s:ClaudeCodeSession {session_id: $session_id})
                    CREATE (m:CLIMetrics {
                        id: $id,
                        session_id: $session_id,
                        tool_usage_summary: $tool_usage,
                        most_used_tool: $most_used_tool,
                        avg_tool_duration_ms: $avg_duration,
                        total_prompts: $total_prompts,
                        total_tools: $total_tools,
                        calculated_at: datetime()
                    })
                    CREATE (m)-[:SUMMARIZES]->(s)
                    """),
                    {
                        "id": f"cli_metrics:{session_id}",
                        "session_id": session_id,
                        "tool_usage": json.dumps(tool_usage),
                        "most_used_tool": most_used_tool,
                        "avg_duration": avg_duration,
                        "total_prompts": prompt_count,
                        "total_tools": tool_count,
                    },
                )
            )
