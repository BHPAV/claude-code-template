# Claude Code CLI Quick Reference

## Core Usage Patterns

```bash
claude                          # Interactive REPL
claude "query"                  # REPL with initial prompt
claude -p "query"               # Non-interactive, print & exit
cat file | claude -p "query"    # Pipe content in
claude -c                       # Continue last conversation
claude -c -p "query"            # Continue non-interactively
claude -r <session-id> "query"  # Resume specific session
```

## Key Flags

### Output Control
| Flag | Effect |
|------|--------|
| `-p, --print` | Non-interactive mode |
| `--output-format` | `text` (default), `json`, `stream-json` |
| `--input-format` | `text` (default), `stream-json` |
| `--verbose` | Full turn-by-turn output |
| `--json-schema` | Validate output against schema |

### System Prompt
| Flag | Effect |
|------|--------|
| `--system-prompt` | Replace entire system prompt |
| `--system-prompt-file` | Load from file (print mode) |
| `--append-system-prompt` | Add to default prompt |

### Tools & Permissions
| Flag | Effect |
|------|--------|
| `--allowedTools` | Whitelist tools (comma/space sep) |
| `--disallowedTools` | Blacklist tools |
| `--permission-mode` | Set permission mode |
| `--dangerously-skip-permissions` | Skip all prompts (risky) |

### Agent/Model
| Flag | Effect |
|------|--------|
| `--model` | `sonnet`, `opus`, `haiku` or full ID |
| `--max-turns` | Limit agentic turns |
| `--agents` | Custom subagents via JSON |

### Session/Directory
| Flag | Effect |
|------|--------|
| `-c, --continue` | Resume most recent session |
| `-r, --resume` | Resume by session ID |
| `--add-dir` | Add working directories |
| `--mcp-config` | Load MCP servers from JSON |

## JSON Output Format

```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "result": "response text",
  "session_id": "abc123",
  "total_cost_usd": 0.003,
  "duration_ms": 1234,
  "num_turns": 6
}
```

## Streaming JSON (stream-json)

JSONL format - each line is JSON object. Starts with system init, ends with result stats.

## Streaming JSON Input

Requires: `-p` + `--output-format stream-json`
Accepts JSONL user messages via stdin for multi-turn guidance mid-execution.

## Multi-Turn Patterns

```bash
# Continue where you left off
claude --continue "do next thing"

# Resume specific session
claude --resume SESSION_ID "update request"

# Resume non-interactively
claude --resume SESSION_ID "fix it" --no-interactive
```

## Practical Examples

```bash
# Timeout long ops
timeout 300 claude -p "$prompt"

# JSON output for parsing
claude -p "query" --output-format json | jq .result

# Restrict tools
claude -p "review code" --allowedTools "Read,Grep,Glob"

# Custom MCP servers
claude -p "query" --mcp-config servers.json

# Pipeline
git diff | claude -p "review this diff" --output-format json
```

## Error Handling

- Check exit codes
- Check stderr
- JSON output has `is_error` field
- Use timeouts for safety

## Subagent JSON Format

```json
{
  "name": "agent-name",
  "description": "what it does",
  "system_prompt": "instructions",
  "tools": ["Read", "Grep"],  // optional
  "model": "haiku"            // optional
}
```

## Commands

| Command | Purpose |
|---------|---------|
| `claude update` | Update CLI |
| `claude mcp` | Configure MCP servers |
