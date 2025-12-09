# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a standalone Claude Code hooks system called "Claudius" that captures and logs all Claude Code CLI interactions to a Neo4j graph database. The system logs user prompts, tool calls, tool results, and session lifecycle events for analysis and visualization.

## Architecture

### Hook System Design

The system uses Claude Code's hook mechanism to intercept events:
- **UserPromptSubmit**: Captures user prompts via `prompt_hook.py`
- **SessionStart/SessionEnd**: Tracks session lifecycle via `session_hook.py`
- **PreToolUse/PostToolUse**: Logs tool calls and results via `tool_hook.py`
- **SubagentStop**: Captures tool calls made BY subagents via `subagent_stop_hook.py`

All hooks are Python scripts that read JSON from stdin and write to SQLite, with Neo4j sync on SessionEnd.

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
- `CLIToolCall`: Tool invocations with timing, inputs/outputs (includes subagent tools with `is_subagent_tool: true`)
- `CLIMetrics`: Aggregated session statistics
- `SubagentSession`: Subagent session metadata with parent linkage
- `File`: (External) File nodes from repository mapping

**Relationships:**
- `PART_OF_SESSION`: Links prompts/tools to sessions
- `ACCESSED_FILE`: Links tools to files they operated on
- `SUMMARIZES`: Links metrics to sessions
- `CHILD_OF_SESSION`: Links SubagentSession to parent ClaudeCodeSession
- `TRIGGERED_SUBAGENT`: Links Task tool call to SubagentSession it spawned
- `PART_OF_SUBAGENT`: Links subagent tool calls to their SubagentSession

### SQLite Schema (v7)

**events table** - All hook events:
- Core: `session_id`, `event_type`, `timestamp`, `raw_json`
- Tool data: `tool_name`, `tool_use_id`, `file_path`, `command`, `pattern`, `url`
- File tracking: `file_paths_json`, `access_mode`, `project_root`, `glob_match_count`
- Subagent: `parent_session_id`, `agent_id`, `is_subagent_event`
- Metrics: `duration_ms`, `output_size_bytes`, `has_stderr`, `sequence_index`

**file_access_log table** - Detailed file access tracking:
- `session_id`, `file_path`, `normalized_path`, `access_mode`
- `project_root`, `tool_name`, `line_numbers_json`
- `is_primary_target`, `is_glob_expansion`, `synced_to_neo4j`

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

### NAS Access (SSH)

Claude Code has direct SSH access to the Terramaster NAS via key-based authentication.

**Connection Details:**
- **Alias:** `terramaster` (preferred - no credentials needed)
- **Host:** `192.168.1.20` (BOX-NAS)
- **User:** `boxhead`
- **Key:** `~/.ssh/id_terramaster`

**Usage Examples:**
```bash
# Run a command on the NAS (use alias - no password needed)
ssh terramaster "ls -la /srv/media"

# Check Docker containers
ssh terramaster "docker ps"

# View NAS storage
ssh terramaster "df -h"

# Transfer files TO the NAS
scp local-file.txt terramaster:/srv/projects/

# Transfer files FROM the NAS
scp terramaster:/srv/projects/file.txt ./
```

**NAS Storage Paths:**
- `/srv/media` - Movies, TV, music
- `/srv/projects` - Development projects
- `/srv/backups` - Backup storage
- `/srv/robotics` - Rover telemetry, datasets

**Docker Services on NAS:**
- Neo4j (7687), Jellyfin (8096), Home Assistant (8123)
- Sonarr (8989), Radarr (7878), qBittorrent (8080)
- Code-Server (8443), Immich (2283)

### Tailscale SSH Access

The homelab uses Tailscale SSH for secure, key-free authentication between machines.

**Available Machines:**
| Machine | Tailscale Name | IP | OS |
|---------|---------------|-----|-----|
| box-rig | box-rig | 100.120.211.28 | Windows |
| box-rex | box-rex | 100.98.133.117 | Windows |
| box-mac | box-mac-1 | 100.69.182.91 | macOS |
| terramaster-nas | terramaster-nas | 100.74.45.35 | Linux |

**Direct Connection (Tailscale CLI):**
```bash
# Interactive session
tailscale ssh boxhead@box-rig
tailscale ssh boxhead@box-rex
tailscale ssh boxhead@box-mac-1

# Run command
tailscale ssh boxhead@box-rex "nvidia-smi"
```

**Python Usage (DomoEnv):**
```python
from domo.domo_env import DomoEnv

env = DomoEnv()

# Check machine status
status = env.get_tailscale_status()
print(f"Online: {[m for m, s in status['machines'].items() if s['online']]}")

# Run command on remote machine
stdout, stderr, rc = env.ssh_run("box-rex", "nvidia-smi")
print(stdout)

# Interactive session
env.ssh_connect("box-rig")
```

**Python Usage (TailscaleSSH directly):**
```python
from domo.ssh import TailscaleSSH

ssh = TailscaleSSH()

# Check status
print(ssh.is_online("box-rex"))

# Run command
stdout, stderr, rc = ssh.run_command("box-rex", "hostname")

# Test all connections
results = ssh.test_all_connections()
```

**CLI Usage:**
```bash
# Show machine status
python domo/domo_env.py ssh-status

# SSH to machine (interactive)
python domo/domo_env.py ssh box-rig

# Run command on machine
python domo/domo_env.py ssh box-rex "dir C:\\"

# Test connections
python domo/domo_env.py ssh-test
python domo/domo_env.py ssh-test box-rig
```

**Pre-requisites:** Enable Tailscale SSH on each target machine:
```powershell
# Windows (admin PowerShell)
tailscale set --ssh

# macOS/Linux
sudo tailscale set --ssh
```

## Testing

### Automated Test Suite

The hooks system has a comprehensive pytest-based test suite with 224 tests covering:

- **Unit tests**: File path extraction, data models, helper functions
- **Integration tests**: SQLite reader/writer, Neo4j operations (mocked)
- **End-to-end tests**: Complete hook stdin processing, session flows

**Run the full test suite:**
```bash
cd .claude/hooks
python -m pytest tests/ -v
```

**Run specific test categories:**
```bash
# Unit tests only
python -m pytest tests/ -v -m unit

# Integration tests only
python -m pytest tests/ -v -m integration

# End-to-end tests only
python -m pytest tests/ -v -m e2e
```

**Test file structure:**
```
.claude/hooks/tests/
├── conftest.py           # Shared fixtures (temp DB, mocks)
├── test_helpers.py       # Unit tests for core/helpers.py extraction functions
├── test_models.py        # Data model validation tests
├── test_sqlite_writer.py # SQLite schema and write operation tests
├── test_sqlite_reader.py # SQLite query method tests
├── test_neo4j_writer.py  # Neo4j operations (mocked)
├── test_sync.py          # SQLite→Neo4j sync orchestration tests
└── test_integration.py   # End-to-end hook processing tests
```

**Key fixtures (conftest.py):**
- `temp_sqlite_db`: Temporary SQLite database with v7 schema
- `sqlite_writer`: Writer instance connected to temp database
- `sqlite_reader`: Reader instance connected to temp database
- `populated_file_access_db`: Database with sample file access records
- `mock_neo4j_driver`: Mocked Neo4j driver for testing graph operations
- `sample_file_path_result`: Sample FilePathResult for testing
- `sample_tool_event`: Sample CLIToolResultEvent for testing

### Manual Hook Testing

Test individual hooks directly:

```bash
# Test prompt hook
echo '{"sessionId": "test-123", "prompt": "test"}' | python .claude/hooks/entrypoints/prompt_hook.py

# Test session start
echo '{"event": "SessionStart", "sessionId": "test-123"}' | python .claude/hooks/entrypoints/session_hook.py

# Test tool hook
echo '{"event": "PostToolUse", "sessionId": "test-123", "toolName": "Read", "toolInput": {}, "toolOutput": "success"}' | python .claude/hooks/entrypoints/tool_hook.py

# Test subagent stop hook (requires valid transcript_path)
echo '{"sessionId": "test-123", "transcript_path": "/path/to/transcript.jsonl"}' | python .claude/hooks/entrypoints/subagent_stop_hook.py
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

// Subagent activity for a session
USE claude_hooks
MATCH (sub:SubagentSession)-[:CHILD_OF_SESSION]->(s:ClaudeCodeSession {session_id: $session_id})
RETURN sub.agent_id, sub.subagent_type, sub.tool_count;

// All tool calls made by subagents
USE claude_hooks
MATCH (t:CLIToolCall {is_subagent_tool: true})-[:PART_OF_SUBAGENT]->(sub:SubagentSession)
RETURN sub.subagent_type, t.tool_name, count(*) as uses
ORDER BY uses DESC;

// Sessions by machine
USE claudehooks
MATCH (s:ClaudeCodeSession)-[:RAN_ON]->(m:Machine)
RETURN m.machine_id, count(s) as sessions
ORDER BY sessions DESC;
```

## Machine Context

This session runs on a homelab machine. Machine detection is automatic via:
1. `MACHINE_ID` environment variable (explicit override)
2. Hostname pattern matching
3. IP address matching against inventory
4. GPU detection (RTX 5090 = box-rig, RTX 4090 = box-rex)

### Get Current Machine Context

```python
from domo.domo_env import DomoEnv

env = DomoEnv()
print(f"Machine: {env.machine_id}")
print(f"Role: {env.machine_info.role}")
print(f"Detection: {env.machine_info.detection_method}")

# Get machine-specific prompt
print(env.get_machine_prompt())

# Get environment spec (full/medium/minimal)
print(env.get_spec('medium'))

# Get combined context
print(env.get_full_context('medium'))
```

### CLI Usage

```bash
# Print context at medium compression
python domo/inject_context.py

# Print full context
python domo/inject_context.py --level full

# Print minimal context
python domo/inject_context.py --level minimal

# Output as JSON
python domo/inject_context.py --json
```

### Available Machines

| Machine ID        | Role               | VLAN  | GPU/Specs        |
|-------------------|--------------------|-------|------------------|
| box-rig           | GPU Workstation    | 30    | RTX 5090 (32GB)  |
| box-rex           | GPU Workstation    | 30    | RTX 4090 (24GB)  |
| terramaster-nas   | NAS/Docker Host    | 10,20 | i3-N305, 32GB    |
| macbook-pro       | Mobile Workstation | 30    | Apple Silicon    |
| ugv-rover-jetson  | Robotics Platform  | 50    | Jetson Orin      |
| lab-pc            | Lab Base Station   | 50    | Raspberry Pi 5   |

### Neo4j Database Note

The CLI hooks now write to the `claudehooks` database (not `claude_hooks` - Neo4j doesn't allow underscores in database names). Sessions are linked to Machine nodes via `RAN_ON` relationships.
