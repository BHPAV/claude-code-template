"""
Neo4j write operations for CLI hooks.

Synchronous implementation for hook script execution.
"""

import json
from datetime import datetime
from pathlib import Path

import sys

# Add hooks root to path for imports
HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from neo4j import GraphDatabase

from core.config import load_neo4j_config
from core.models import (
    CLISessionStartEvent,
    CLISessionEndEvent,
    CLIToolResultEvent,
    CLIPromptEvent,
)
from core.helpers import sanitize_tool_input


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

    def create_session_node(self, event: CLISessionStartEvent, machine_id: str = None) -> str:
        """
        Create ClaudeCodeSession node with optional Machine linking.

        Args:
            event: Session start event data
            machine_id: Optional machine identifier (e.g., 'box-rig', 'terramaster-nas')

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
                        s.machine_id = $machine_id,
                        s.status = 'active',
                        s.tool_call_count = 0,
                        s.prompt_count = 0,
                        s.metadata = $metadata

                    // Link to Machine if machine_id provided and Machine exists
                    WITH s
                    OPTIONAL MATCH (m:Machine {machine_id: $machine_id})
                    FOREACH (_ IN CASE WHEN m IS NOT NULL THEN [1] ELSE [] END |
                        MERGE (s)-[:RAN_ON]->(m)
                    )
                    """),
                    {
                        "id": session_node_id,
                        "session_id": event.session_id,
                        "timestamp": event.timestamp.isoformat(),
                        "working_dir": event.working_dir,
                        "machine_id": machine_id,
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
                        s.total_duration_seconds = $duration,
                        s.tool_call_count = $tool_count,
                        s.prompt_count = $prompt_count
                    """),
                    {
                        "session_id": event.session_id,
                        "timestamp": event.timestamp.isoformat(),
                        "duration": event.duration_seconds,
                        "tool_count": event.tool_count,
                        "prompt_count": event.prompt_count,
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

        # Use file_path from event if available, otherwise extract from tool_input
        file_path = event.file_path
        if file_path is None:
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
                        file_path: $file_path,
                        tool_category: $tool_category,
                        subagent_type: $subagent_type,
                        command: $command,
                        pattern: $pattern,
                        url: $url,
                        output_size_bytes: $output_size_bytes,
                        has_stderr: $has_stderr,
                        sequence_index: $sequence_index
                    })
                    CREATE (t)-[:PART_OF_SESSION]->(s)

                    // Increment session tool count
                    SET s.tool_call_count = s.tool_call_count + 1

                    // Create File node and ACCESSED_FILE relationship if file_path present
                    WITH t, $file_path as fp
                    WHERE fp IS NOT NULL
                    MERGE (f:File {path: fp})
                    ON CREATE SET f.created_at = datetime(),
                                  f.extension = CASE
                                      WHEN fp CONTAINS '.' THEN split(fp, '.')[-1]
                                      ELSE null
                                  END
                    CREATE (t)-[:ACCESSED_FILE]->(f)
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
                        "tool_category": event.tool_category,
                        "subagent_type": event.subagent_type,
                        "command": event.command[:200] if event.command else None,  # Truncate
                        "pattern": event.pattern,
                        "url": event.url,
                        "output_size_bytes": event.output_size_bytes,
                        "has_stderr": event.has_stderr,
                        "sequence_index": event.sequence_index,
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
                        prompt_length: $length,
                        intent_type: $intent_type,
                        sequence_index: $sequence_index
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
                        "intent_type": event.intent_type,
                        "sequence_index": event.sequence_index,
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

    # -------------------------------------------------------------------------
    # Subagent Methods
    # -------------------------------------------------------------------------

    def create_subagent_session(self, parent_session_id: str, agent_id: str,
                                 subagent_type: str, transcript_path: str,
                                 tool_count: int, timestamp: datetime):
        """
        Create SubagentSession node linked to parent session.

        Args:
            parent_session_id: Parent session ID
            agent_id: The subagent's session ID
            subagent_type: Type of subagent (Explore, Plan, etc.)
            transcript_path: Path to subagent's transcript
            tool_count: Number of tools used by subagent
            timestamp: When subagent stopped
        """
        subagent_node_id = f"cli_subagent:{agent_id}"

        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MATCH (parent:ClaudeCodeSession {session_id: $parent_session_id})
                    MERGE (sub:SubagentSession {id: $id})
                    SET sub.agent_id = $agent_id,
                        sub.parent_session_id = $parent_session_id,
                        sub.subagent_type = $subagent_type,
                        sub.transcript_path = $transcript_path,
                        sub.tool_count = $tool_count,
                        sub.end_time = datetime($timestamp)
                    MERGE (sub)-[:CHILD_OF_SESSION]->(parent)
                    """),
                    {
                        "id": subagent_node_id,
                        "agent_id": agent_id,
                        "parent_session_id": parent_session_id,
                        "subagent_type": subagent_type,
                        "transcript_path": transcript_path,
                        "tool_count": tool_count,
                        "timestamp": timestamp.isoformat(),
                    },
                )
            )

    def create_subagent_tool_call(self, parent_session_id: str, agent_id: str,
                                   tool_data: dict, subagent_type: str = None):
        """
        Create CLIToolCall node for a subagent's tool call.

        Args:
            parent_session_id: Parent session ID
            agent_id: The subagent's session ID
            tool_data: Dict with tool_name, tool_input, tool_use_id, timestamp, etc.
            subagent_type: Type of subagent
        """
        tool_name = tool_data.get('tool_name', 'unknown')
        timestamp = tool_data.get('timestamp', datetime.now().isoformat())
        tool_id = f"cli_subtool:{agent_id}:{timestamp}:{tool_name}"

        # Extract and normalize file_path
        tool_input = tool_data.get('tool_input') or {}
        file_path = tool_input.get('file_path')
        if file_path:
            file_path = Path(file_path).as_posix()

        # Sanitize input
        sanitized_input = sanitize_tool_input(tool_input)

        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MATCH (sub:SubagentSession {agent_id: $agent_id})
                    CREATE (t:CLIToolCall {
                        id: $id,
                        session_id: $agent_id,
                        parent_session_id: $parent_session_id,
                        is_subagent_tool: true,
                        tool_name: $tool_name,
                        timestamp: datetime($timestamp),
                        inputs: $inputs,
                        outputs: $outputs,
                        success: $success,
                        file_path: $file_path,
                        subagent_type: $subagent_type
                    })
                    CREATE (t)-[:PART_OF_SUBAGENT]->(sub)

                    // Create File node and ACCESSED_FILE relationship if file_path present
                    WITH t, $file_path as fp
                    WHERE fp IS NOT NULL
                    MERGE (f:File {path: fp})
                    ON CREATE SET f.created_at = datetime(),
                                  f.extension = CASE
                                      WHEN fp CONTAINS '.' THEN split(fp, '.')[-1]
                                      ELSE null
                                  END
                    CREATE (t)-[:ACCESSED_FILE]->(f)
                    """),
                    {
                        "id": tool_id,
                        "agent_id": agent_id,
                        "parent_session_id": parent_session_id,
                        "tool_name": tool_name,
                        "timestamp": timestamp,
                        "inputs": json.dumps(sanitized_input)[:2000],
                        "outputs": str(tool_data.get('tool_result', ''))[:5000],
                        "success": tool_data.get('success', True),
                        "file_path": file_path,
                        "subagent_type": subagent_type,
                    },
                )
            )

    def link_task_to_subagent(self, task_tool_use_id: str, agent_id: str):
        """
        Create TRIGGERED_SUBAGENT relationship from Task tool call to subagent.

        Args:
            task_tool_use_id: The tool_use_id of the Task tool call
            agent_id: The subagent's session ID
        """
        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MATCH (task:CLIToolCall)
                    WHERE task.tool_name = 'Task' AND task.id CONTAINS $task_id
                    MATCH (sub:SubagentSession {agent_id: $agent_id})
                    MERGE (task)-[:TRIGGERED_SUBAGENT]->(sub)
                    """),
                    {
                        "task_id": task_tool_use_id,
                        "agent_id": agent_id,
                    },
                )
            )

    # -------------------------------------------------------------------------
    # Unified File Model Methods (v7)
    # -------------------------------------------------------------------------

    def merge_unified_file(self, file_path: str, access_mode: str = 'read',
                           project_root: str = None, extension: str = None) -> str:
        """
        MERGE UnifiedFile node and link to existing FileNode if found.

        Args:
            file_path: Normalized Unix-style file path
            access_mode: Access type (read, write, modify, search, execute)
            project_root: Project root directory
            extension: File extension

        Returns:
            str: UnifiedFile node ID
        """
        if not file_path:
            return None

        # Auto-detect extension if not provided
        if extension is None and '.' in file_path:
            extension = file_path.rsplit('.', 1)[-1].lower()

        file_id = f"unified_file:{file_path}"

        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MERGE (uf:UnifiedFile {path: $path})
                    ON CREATE SET
                        uf.id = $id,
                        uf.name = $name,
                        uf.extension = $extension,
                        uf.project_path = $project_root,
                        uf.read_count = CASE WHEN $access_mode = 'read' THEN 1 ELSE 0 END,
                        uf.write_count = CASE WHEN $access_mode = 'write' THEN 1 ELSE 0 END,
                        uf.modify_count = CASE WHEN $access_mode = 'modify' THEN 1 ELSE 0 END,
                        uf.search_count = CASE WHEN $access_mode = 'search' THEN 1 ELSE 0 END,
                        uf.first_accessed = datetime(),
                        uf.last_accessed = datetime(),
                        uf.created_at = datetime()
                    ON MATCH SET
                        uf.read_count = uf.read_count + CASE WHEN $access_mode = 'read' THEN 1 ELSE 0 END,
                        uf.write_count = uf.write_count + CASE WHEN $access_mode = 'write' THEN 1 ELSE 0 END,
                        uf.modify_count = uf.modify_count + CASE WHEN $access_mode = 'modify' THEN 1 ELSE 0 END,
                        uf.search_count = uf.search_count + CASE WHEN $access_mode = 'search' THEN 1 ELSE 0 END,
                        uf.last_accessed = datetime(),
                        uf.updated_at = datetime()

                    // Link to FileNode if exists (by path match)
                    WITH uf
                    OPTIONAL MATCH (fn:FileNode)
                    WHERE fn.path = $path OR fn.path ENDS WITH $path_suffix
                    WITH uf, fn
                    WHERE fn IS NOT NULL
                    MERGE (uf)-[:MERGED_FROM]->(fn)
                    SET uf.content_hash = fn.content_hash,
                        uf.size_bytes = fn.size_bytes,
                        uf.mime_type = fn.mime_type,
                        uf.scanned_at = fn.created_at
                    """),
                    {
                        "id": file_id,
                        "path": file_path,
                        "name": file_path.rsplit('/', 1)[-1] if '/' in file_path else file_path,
                        "extension": extension,
                        "project_root": project_root,
                        "access_mode": access_mode,
                        "path_suffix": '/' + file_path if not file_path.startswith('/') else file_path,
                    },
                )
            )

        return file_id

    def create_multi_file_access(self, tool_call_id: str, session_id: str,
                                  file_paths: list, access_mode: str = 'read',
                                  project_root: str = None, is_glob_expansion: bool = False):
        """
        Create UnifiedFile nodes and ACCESSED_FILE relationships for multiple files.

        Args:
            tool_call_id: ID of the CLIToolCall node
            session_id: Session identifier
            file_paths: List of file paths to link
            access_mode: Access type for all files
            project_root: Common project root
            is_glob_expansion: Whether files came from glob expansion
        """
        if not file_paths:
            return

        with self.driver.session() as session:
            for i, file_path in enumerate(file_paths):
                is_primary = (i == 0)  # First file is primary
                session.execute_write(
                    lambda tx, fp=file_path, primary=is_primary: tx.run(
                        self._with_database("""
                        // Create/update UnifiedFile
                        MERGE (uf:UnifiedFile {path: $path})
                        ON CREATE SET
                            uf.id = 'unified_file:' + $path,
                            uf.name = CASE WHEN $path CONTAINS '/'
                                THEN split($path, '/')[-1]
                                ELSE $path END,
                            uf.extension = CASE WHEN $path CONTAINS '.'
                                THEN split($path, '.')[-1]
                                ELSE null END,
                            uf.project_path = $project_root,
                            uf.read_count = CASE WHEN $access_mode = 'read' THEN 1 ELSE 0 END,
                            uf.write_count = CASE WHEN $access_mode = 'write' THEN 1 ELSE 0 END,
                            uf.modify_count = CASE WHEN $access_mode = 'modify' THEN 1 ELSE 0 END,
                            uf.search_count = CASE WHEN $access_mode = 'search' THEN 1 ELSE 0 END,
                            uf.first_accessed = datetime(),
                            uf.last_accessed = datetime(),
                            uf.created_at = datetime()
                        ON MATCH SET
                            uf.read_count = uf.read_count + CASE WHEN $access_mode = 'read' THEN 1 ELSE 0 END,
                            uf.write_count = uf.write_count + CASE WHEN $access_mode = 'write' THEN 1 ELSE 0 END,
                            uf.modify_count = uf.modify_count + CASE WHEN $access_mode = 'modify' THEN 1 ELSE 0 END,
                            uf.search_count = uf.search_count + CASE WHEN $access_mode = 'search' THEN 1 ELSE 0 END,
                            uf.last_accessed = datetime()

                        // Link to CLIToolCall
                        WITH uf
                        MATCH (t:CLIToolCall {id: $tool_call_id})
                        CREATE (t)-[:ACCESSED_FILE {
                            access_mode: $access_mode,
                            is_primary: $is_primary,
                            is_glob_expansion: $is_glob
                        }]->(uf)
                        """),
                        {
                            "path": fp,
                            "tool_call_id": tool_call_id,
                            "access_mode": access_mode,
                            "project_root": project_root,
                            "is_primary": primary,
                            "is_glob": is_glob_expansion,
                        },
                    )
                )

    def update_co_access_relationships(self, session_id: str, file_paths: list):
        """
        Update CO_ACCESSED_WITH relationships for files in same session.

        Creates or increments co-access count between all pairs of files
        that were accessed in the same session.

        Args:
            session_id: The session identifier
            file_paths: List of file paths accessed in this session
        """
        if not file_paths or len(file_paths) < 2:
            return

        # Get unique paths
        unique_paths = list(set(file_paths))
        if len(unique_paths) < 2:
            return

        with self.driver.session() as session:
            # Create/update co-access relationships for all pairs
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    UNWIND $paths as path1
                    UNWIND $paths as path2
                    WITH path1, path2
                    WHERE path1 < path2  // Avoid duplicates and self-links
                    MATCH (f1:UnifiedFile {path: path1})
                    MATCH (f2:UnifiedFile {path: path2})
                    MERGE (f1)-[r:CO_ACCESSED_WITH]-(f2)
                    ON CREATE SET
                        r.co_access_count = 1,
                        r.session_count = 1,
                        r.created_at = datetime(),
                        r.updated_at = datetime()
                    ON MATCH SET
                        r.co_access_count = r.co_access_count + 1,
                        r.updated_at = datetime()
                    """),
                    {"paths": unique_paths},
                )
            )

    def create_session_file_access(self, session_id: str, file_path: str,
                                    access_mode: str, timestamp: str):
        """
        Create SESSION_ACCESSED relationship between session and file.

        Args:
            session_id: The session identifier
            file_path: Normalized file path
            access_mode: Access type
            timestamp: ISO format timestamp
        """
        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MATCH (s:ClaudeCodeSession {session_id: $session_id})
                    MERGE (uf:UnifiedFile {path: $path})
                    ON CREATE SET
                        uf.id = 'unified_file:' + $path,
                        uf.created_at = datetime()
                    MERGE (s)-[r:SESSION_ACCESSED]->(uf)
                    ON CREATE SET
                        r.first_access = datetime($timestamp),
                        r.last_access = datetime($timestamp),
                        r.read_count = CASE WHEN $access_mode = 'read' THEN 1 ELSE 0 END,
                        r.write_count = CASE WHEN $access_mode = 'write' THEN 1 ELSE 0 END
                    ON MATCH SET
                        r.last_access = datetime($timestamp),
                        r.read_count = r.read_count + CASE WHEN $access_mode = 'read' THEN 1 ELSE 0 END,
                        r.write_count = r.write_count + CASE WHEN $access_mode = 'write' THEN 1 ELSE 0 END
                    """),
                    {
                        "session_id": session_id,
                        "path": file_path,
                        "access_mode": access_mode,
                        "timestamp": timestamp,
                    },
                )
            )

    def migrate_file_to_unified(self) -> dict:
        """
        Migrate existing File nodes to UnifiedFile model.

        This is a one-time migration operation that:
        1. Creates UnifiedFile nodes from existing File nodes
        2. Links to FileNode if path matches
        3. Migrates ACCESSED_FILE relationships

        Returns:
            dict: Migration statistics
        """
        stats = {
            'files_migrated': 0,
            'filenode_links': 0,
            'access_rels_migrated': 0,
            'success': True,
        }

        with self.driver.session() as session:
            # Count existing File nodes
            result = session.run(
                self._with_database("MATCH (f:File) RETURN count(f) as count")
            )
            file_count = result.single()['count']
            stats['source_file_count'] = file_count

            # Create UnifiedFile from File
            result = session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MATCH (f:File)
                    MERGE (uf:UnifiedFile {path: f.path})
                    ON CREATE SET
                        uf.id = 'unified_file:' + f.path,
                        uf.extension = f.extension,
                        uf.read_count = COALESCE(f.read_count, 0),
                        uf.write_count = COALESCE(f.write_count, 0),
                        uf.created_at = COALESCE(f.created_in_graph, datetime()),
                        uf.first_accessed = f.created_in_graph
                    RETURN count(uf) as created
                    """)
                ).single()
            )
            stats['files_migrated'] = result['created'] if result else 0

            # Link to FileNode by path
            result = session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MATCH (uf:UnifiedFile)
                    OPTIONAL MATCH (fn:FileNode)
                    WHERE fn.path = uf.path
                    WITH uf, fn
                    WHERE fn IS NOT NULL
                    MERGE (uf)-[r:MERGED_FROM]->(fn)
                    SET uf.content_hash = fn.content_hash,
                        uf.size_bytes = fn.size_bytes,
                        uf.mime_type = fn.mime_type
                    RETURN count(r) as linked
                    """)
                ).single()
            )
            stats['filenode_links'] = result['linked'] if result else 0

            # Create new ACCESSED_FILE to UnifiedFile (preserving old relationships)
            result = session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MATCH (t:CLIToolCall)-[r:ACCESSED_FILE]->(f:File)
                    MATCH (uf:UnifiedFile {path: f.path})
                    MERGE (t)-[r2:ACCESSED_UNIFIED_FILE]->(uf)
                    RETURN count(r2) as migrated
                    """)
                ).single()
            )
            stats['access_rels_migrated'] = result['migrated'] if result else 0

        return stats
