# Claude Code Headless Mode Quick Reference

## Core Syntax

```bash
claude -p "task description" [options]
```

`-p` / `--print` = non-interactive, output result and exit

## Key Flags

| Flag | Purpose |
|------|---------|
| `-p, --print` | Non-interactive mode |
| `--output-format` | `text` (default), `json`, `stream-json` |
| `--input-format` | `text` (default), `stream-json` |
| `-c, --continue` | Resume most recent session |
| `-r, --resume <id>` | Resume specific session |
| `--verbose` | Full turn-by-turn logging |
| `--append-system-prompt` | Add instructions (print mode only) |
| `--allowedTools` | Whitelist tools (comma/space sep) |
| `--disallowedTools` | Blacklist tools |
| `--mcp-config` | Load MCP servers from JSON file |
| `--permission-prompt-tool` | MCP tool for permission handling |
| `--max-turns` | Limit agentic turns |

## Output Formats

| Format | Use Case |
|--------|----------|
| `text` | Human readable, shell scripts |
| `json` | Programmatic parsing |
| `stream-json` | Real-time streaming, JSONL |

## JSON Output Schema

```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "result": "Response text...",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_cost_usd": 0.003,
  "duration_ms": 1234,
  "duration_api_ms": 800,
  "num_turns": 6
}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Always `"result"` |
| `subtype` | string | `"success"` or `"error"` |
| `is_error` | bool | Error occurred |
| `result` | string | Response content |
| `session_id` | string | UUID for resume |
| `total_cost_usd` | float | API cost |
| `duration_ms` | int | Total time |
| `duration_api_ms` | int | API time only |
| `num_turns` | int | Conversation turns |

## Input Methods

### Argument
```bash
claude -p "analyze this code"
```

### Stdin Pipe
```bash
cat file.py | claude -p "review this"
git diff | claude -p "summarize changes"
```

### Streaming JSON Input
Requires: `-p` + `--output-format stream-json` + `--input-format stream-json`

```bash
echo '{"type":"user","message":{"role":"user","content":[{"type":"text","text":"task"}]}}' \
  | claude -p --output-format=stream-json --input-format=stream-json
```

## Multi-Turn Sessions

```bash
# Continue most recent
claude -c "next instruction"
claude --continue -p "next instruction"

# Resume by session ID
claude -r SESSION_ID "update request"
claude --resume SESSION_ID -p "fix issues"

# Get session ID from JSON output
session_id=$(claude -p "start task" --output-format json | jq -r '.session_id')
claude -p --resume "$session_id" "continue task"
```

## Streaming JSON Output (stream-json)

JSONL format - one JSON object per line:

```
{"type":"system","message":{...}}
{"type":"assistant","message":{...}}
{"type":"result","subtype":"success",...}
```

## Practical Examples

### Parse JSON Result
```bash
claude -p "query" --output-format json | jq -r '.result'
```

### With Timeout
```bash
timeout 300 claude -p "long task" --output-format json
```

### Restrict Tools
```bash
claude -p "review code" --allowedTools "Read,Grep,Glob"
```

### Custom System Prompt
```bash
claude -p "task" --append-system-prompt "You are a security expert..."
```

### Pipeline with MCP
```bash
claude -p "query database" \
  --mcp-config servers.json \
  --allowedTools "Read,mcp__postgres"
```

### Session Chaining
```bash
# Start session, capture ID
id=$(claude -p "start review" --output-format json | jq -r '.session_id')

# Continue with context
claude -p --resume "$id" "check security"
claude -p --resume "$id" "check performance"
claude -p --resume "$id" "generate summary"
```

### Error Handling
```bash
if ! result=$(claude -p "$prompt" --output-format json 2>err.log); then
    echo "Failed: $(cat err.log)" >&2
    exit 1
fi

if [ "$(echo "$result" | jq -r '.is_error')" = "true" ]; then
    echo "Error in response" >&2
    exit 1
fi

echo "$result" | jq -r '.result'
```

## Best Practices

| Practice | Reason |
|----------|--------|
| Use `--output-format json` | Reliable parsing |
| Check exit codes + `is_error` | Catch failures |
| Implement timeouts | Prevent hangs |
| Add delays between calls | Respect rate limits |
| Use `--allowedTools` | Security + predictability |
| Capture `session_id` | Enable multi-turn workflows |
