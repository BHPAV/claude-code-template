# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a standalone Claude Code hooks system called "Claudius" that captures and logs all Claude Code CLI interactions to a Neo4j graph database. The system logs user prompts, tool calls, tool results, and session lifecycle events for analysis and visualization.

## Architecture

### Hook System Design

The system uses Claude Code's hook mechanism to intercept events:
- **UserPromptSubmit**: Captures user prompts via `prompt_hooks.py`
- **SessionStart/SessionEnd**: Tracks session lifecycle via `session_hooks.py`
- **PreToolUse/PostToolUse**: Logs tool calls and results via `tool_hooks.py`

All hooks are Python scripts that read JSON from stdin and write to Neo4j synchronously.

### Key Components

**`.claude/hooks/config.py`**: Configuration loader that reads from environment variables
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`
- Provides `is_neo4j_available()` connectivity check
- Self-contained, no external dependencies

**`.claude/hooks/models.py`**: Data models for all hook events
- `CLISessionStartEvent`, `CLISessionEndEvent`: Session lifecycle
- `CLIToolCallEvent`, `CLIToolResultEvent`: Tool execution
- `CLIPromptEvent`: User prompts
- `sanitize_tool_input()`: Removes sensitive data (passwords, tokens, API keys)

**`.claude/hooks/neo4j_writer.py`**: Synchronous Neo4j write operations
- `CLINeo4jWriter`: Context manager for database connections
- `_with_database()`: Prepends `USE {database}` to all queries for multi-database support
- Creates nodes: `ClaudeCodeSession`, `CLIPrompt`, `CLIToolCall`, `CLIMetrics`
- Links tool calls to `File` nodes via `ACCESSED_FILE` relationships
- Normalizes file paths to Unix-style (forward slashes) for consistency

**`.claude/hooks/prompt_hooks.py`**: UserPromptSubmit handler
- Truncates prompts to 1000 chars for storage
- Stores SHA256 hash for deduplication
- Increments session prompt counter

**`.claude/hooks/session_hooks.py`**: SessionStart/SessionEnd handlers
- Uses `.session_cache.json` to track session start times
- Calculates session duration on end
- Generates metrics summary via `create_metrics_summary()`

**`.claude/hooks/tool_hooks.py`**: PreToolUse/PostToolUse handlers
- Uses `.tool_call_cache.json` to match pre/post events
- Calculates tool execution duration in milliseconds
- Extracts and normalizes `file_path` from tool inputs
- Links to existing `File` nodes if present
- Basic error detection via keyword matching ("error", "failed", "exception")

### Neo4j Schema

**Nodes:**
- `ClaudeCodeSession`: Session metadata with counters
- `CLIPrompt`: User prompts with text and hash
- `CLIToolCall`: Tool invocations with timing, inputs/outputs
- `CLIMetrics`: Aggregated session statistics
- `File`: (External) File nodes from repository mapping

**Relationships:**
- `PART_OF_SESSION`: Links prompts/tools to sessions
- `ACCESSED_FILE`: Links tools to files they operated on
- `SUMMARIZES`: Links metrics to sessions

### Error Handling Philosophy

All hooks follow the same pattern:
- Always exit with code 0 (never block CLI)
- Log errors to stderr with `[CLI Hook]` prefix
- Silently skip if Neo4j unavailable
- Consume Neo4j query results immediately inside transactions to prevent connection issues

## Configuration

### Environment Variables

Set these before running Claude Code:

```powershell
# PowerShell (Windows)
$env:NEO4J_URI="bolt://localhost:7687"
$env:NEO4J_USER="neo4j"
$env:NEO4J_PASSWORD="mypassword"
$env:NEO4J_DATABASE="claude_hooks"
```

```bash
# Bash (Linux/Mac)
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=mypassword
export NEO4J_DATABASE=claude_hooks
```

### Hook Configuration

Hooks are registered in `.claude/settings.local.json` and execute Python scripts via command hooks. The configuration also includes permission settings for allowed Bash commands and WebFetch domains.

## Testing

Test individual hooks directly:

```bash
# Test prompt hook
echo '{"sessionId": "test-123", "prompt": "test"}' | python .claude/hooks/prompt_hooks.py

# Test session start
echo '{"event": "SessionStart", "sessionId": "test-123"}' | python .claude/hooks/session_hooks.py

# Test tool hook
echo '{"event": "PostToolUse", "sessionId": "test-123", "toolName": "Read", "toolInput": {}, "toolOutput": "success"}' | python .claude/hooks/tool_hooks.py
```

## Development Notes

### Working with Hooks

- Hook scripts must read from stdin and exit quickly (non-blocking)
- All Neo4j operations use context managers for proper cleanup
- Cache files (`.session_cache.json`, `.tool_call_cache.json`) are ephemeral and failure-tolerant
- Truncate large data before storage: prompts (1000 chars), inputs (2000 chars), outputs (5000 chars)

### Database Operations

- All Cypher queries include `USE {database}` for multi-database support
- Query results must be consumed inside the transaction (use `list(result)`)
- File paths are normalized to Unix-style before storage or querying
- Tool inputs are sanitized to remove sensitive keys before logging

### Extending the System

To add new hook types:
1. Define event model in `models.py`
2. Add write method to `CLINeo4jWriter`
3. Create hook handler script (follow existing pattern)
4. Register in `.claude/settings.local.json`

### Querying Session Data

Example Cypher queries:

```cypher
// Sessions in last 24 hours
USE claude_hooks
MATCH (s:ClaudeCodeSession)
WHERE s.start_time > datetime() - duration('PT24H')
RETURN s ORDER BY s.start_time DESC;

// Most used tools
USE claude_hooks
MATCH (t:CLIToolCall)-[:PART_OF_SESSION]->(s:ClaudeCodeSession)
RETURN s.session_id, t.tool_name, count(*) as uses
ORDER BY uses DESC;

// Failed operations
USE claude_hooks
MATCH (t:CLIToolCall {success: false})-[:PART_OF_SESSION]->(s:ClaudeCodeSession)
RETURN DISTINCT s.session_id, collect(t.tool_name) as failed_tools;
```
