# Claude Code Hooks

Standalone hooks system for logging Claude Code CLI interactions to Neo4j.

## Overview

This directory contains a complete, self-contained hooks system for Claude Code that captures and logs:
- User prompts
- Tool calls and results
- Session lifecycle (start/end)
- Performance metrics

All data is stored in a Neo4j graph database for analysis and visualization.

## Directory Structure

```
.claude/hooks/
├── core/
│   ├── config.py         # SQLite & Neo4j configuration
│   ├── models.py         # Data models (dataclasses)
│   └── helpers.py        # File path extraction, classification utils
├── sqlite/
│   ├── reader.py         # SQLite query operations
│   └── writer.py         # SQLite write operations (schema v7)
├── graph/
│   ├── writer.py         # Neo4j write operations
│   └── sync.py           # SQLite → Neo4j sync orchestration
├── entrypoints/
│   ├── prompt_hook.py    # UserPromptSubmit handler
│   ├── session_hook.py   # SessionStart/SessionEnd handlers
│   ├── tool_hook.py      # PreToolUse/PostToolUse handlers
│   └── subagent_stop_hook.py  # SubagentStop handler
├── tests/                # Pytest test suite (224 tests)
│   ├── conftest.py
│   ├── test_*.py
│   └── pytest.ini
└── data/
    └── claude_hooks.db   # SQLite database
```

## Configuration

The hooks system is configured via environment variables:

```bash
# Required
NEO4J_URI=bolt://localhost:7687      # Neo4j connection URI
NEO4J_USER=neo4j                     # Neo4j username
NEO4J_PASSWORD=password              # Neo4j password

# Optional
NEO4J_DATABASE=neo4j                 # Target database (default: neo4j)
```

### Windows
```cmd
set NEO4J_URI=bolt://localhost:7687
set NEO4J_USER=neo4j
set NEO4J_PASSWORD=password
set NEO4J_DATABASE=logging
```

### Linux/Mac
```bash
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=mypassword
export NEO4J_DATABASE=claude_hooks
```

### PowerShell
```powershell
$env:NEO4J_URI="bolt://localhost:7687"
$env:NEO4J_USER="neo4j"
$env:NEO4J_PASSWORD="mypassword"
$env:NEO4J_DATABASE="claude_hooks"
```

## Database Selection

All Cypher queries automatically include a `USE {database}` statement to ensure data is written to the correct database. This is configured via the `NEO4J_DATABASE` environment variable.

Example query:
```cypher
USE claude_hooks
MATCH (s:ClaudeCodeSession {session_id: $session_id})
RETURN s
```

## Neo4j Schema

### Nodes
- **ClaudeCodeSession** - CLI session information
- **CLIPrompt** - User prompts
- **CLIToolCall** - Tool invocations with timing and results
- **CLIMetrics** - Aggregated session metrics

### Relationships
- **PART_OF_SESSION** - Links prompts and tools to sessions
- **ACCESSED_FILE** - Links tool calls to file nodes
- **SUMMARIZES** - Links metrics to sessions

## Installation

The hooks are already configured in `.claude/settings.local.json`. Ensure:

1. Neo4j is running and accessible
2. Environment variables are set (or defaults are correct)
3. Python `neo4j` driver is installed: `pip install neo4j`

## Testing

### Automated Test Suite

The hooks system includes a comprehensive pytest test suite with 224 tests.

**Run all tests:**
```bash
python -m pytest tests/ -v
```

**Test categories:**
```bash
# Unit tests (fast, no external dependencies)
python -m pytest tests/ -v -m unit

# Integration tests (SQLite/Neo4j mocked)
python -m pytest tests/ -v -m integration

# End-to-end tests (full hook flows)
python -m pytest tests/ -v -m e2e
```

**Test files:**
- `tests/conftest.py` - Shared fixtures (temp databases, mocks)
- `tests/test_helpers.py` - File path extraction functions (40+ tests)
- `tests/test_models.py` - Data model validation
- `tests/test_sqlite_writer.py` - SQLite schema and writes
- `tests/test_sqlite_reader.py` - SQLite query methods
- `tests/test_neo4j_writer.py` - Neo4j operations (mocked)
- `tests/test_sync.py` - Sync orchestration
- `tests/test_integration.py` - E2E hook processing

### Manual Hook Testing

Test individual hooks:

```bash
# Test prompt hook
echo '{"sessionId": "test-123", "prompt": "test"}' | python entrypoints/prompt_hook.py

# Test session start
echo '{"event": "SessionStart", "sessionId": "test-123"}' | python entrypoints/session_hook.py

# Test tool hook
echo '{"event": "PostToolUse", "sessionId": "test-123", "toolName": "Read", "toolInput": {}, "toolOutput": "success"}' | python entrypoints/tool_hook.py
```

## Error Handling

All hooks:
- Exit with code 0 (never block CLI operations)
- Log errors to stderr with `[CLI Hook]` prefix
- Silently skip logging if Neo4j is unavailable
- Sanitize sensitive data (passwords, tokens, API keys)

## Standalone Design

This hooks directory is completely self-contained:
- No dependencies on agent code (`src/agents/v3/`)
- Own Neo4jConfig implementation
- Can be copied to other projects
- Consistent environment variable names with agent config

## Query Examples

```cypher
// Find all sessions in last 24 hours
USE claude_hooks
MATCH (s:ClaudeCodeSession)
WHERE s.start_time > datetime() - duration('PT24H')
RETURN s
ORDER BY s.start_time DESC;

// Most used tools by session
USE claude_hooks
MATCH (t:CLIToolCall)-[:PART_OF_SESSION]->(s:ClaudeCodeSession)
RETURN s.session_id, t.tool_name, count(*) as uses
ORDER BY uses DESC;

// Sessions with errors
USE claude_hooks
MATCH (t:CLIToolCall {success: false})-[:PART_OF_SESSION]->(s:ClaudeCodeSession)
RETURN DISTINCT s.session_id, s.start_time, collect(t.tool_name) as failed_tools;
```
