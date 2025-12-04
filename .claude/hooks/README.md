# Claude Code Hooks

Standalone hooks system for logging Claude Code CLI interactions to Neo4j.

## Overview

This directory contains a complete, self-contained hooks system for Claude Code that captures and logs:
- User prompts
- Tool calls and results
- Session lifecycle (start/end)
- Performance metrics

All data is stored in a Neo4j graph database for analysis and visualization.

## Files

- **config.py** - Standalone Neo4j configuration (no external dependencies)
- **models.py** - Data models for hook events
- **neo4j_writer.py** - Neo4j write operations with database selection support
- **prompt_hooks.py** - UserPromptSubmit hook handler
- **session_hooks.py** - SessionStart/SessionEnd hook handlers
- **tool_hooks.py** - PreToolUse/PostToolUse hook handlers

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

Test individual hooks:

```bash
# Test prompt hook
echo '{"sessionId": "test-123", "prompt": "test"}' | python prompt_hooks.py

# Test session start
echo '{"event": "SessionStart", "sessionId": "test-123"}' | python session_hooks.py

# Test tool hook
echo '{"event": "PostToolUse", "sessionId": "test-123", "toolName": "Read", "toolInput": {}, "toolOutput": "success"}' | python tool_hooks.py
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
