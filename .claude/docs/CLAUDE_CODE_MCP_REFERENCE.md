# Claude Code MCP Quick Reference

## Transport Types

| Type | Use Case | Status |
|------|----------|--------|
| `http` | Remote/cloud servers | Recommended |
| `sse` | Remote servers | Deprecated |
| `stdio` | Local processes | For local tools/scripts |

## CLI Commands

```bash
# Add servers
claude mcp add --transport http <name> <url>
claude mcp add --transport sse <name> <url>
claude mcp add --transport stdio <name> <command> [args...]

# Manage servers
claude mcp list                    # List configured servers
claude mcp remove <name>           # Remove server

# Double dash separates CLI flags from server command
claude mcp add -s user -- <name> npx some-server --server-flag
#              ^CLI flag  ^server command + its flags
```

## Configuration Scopes

| Scope | Flag | Storage Location | Sharing |
|-------|------|------------------|---------|
| Local | (default) | `~/.claude.json` under project path | Private |
| Project | `-s project` | `.mcp.json` at project root | Version control |
| User | `-s user` | `~/.claude.json` | All projects, one user |

## Config File Format

```json
{
  "mcpServers": {
    "server-name": {
      "transport": "http",
      "url": "https://api.example.com/mcp",
      "headers": {
        "Authorization": "Bearer ${API_TOKEN}"
      }
    },
    "local-server": {
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "some-mcp-server"],
      "env": {
        "API_KEY": "${MY_API_KEY:-default_value}"
      }
    }
  }
}
```

## Environment Variable Expansion

| Syntax | Behavior |
|--------|----------|
| `${VAR}` | Expand to env var value |
| `${VAR:-default}` | Use default if unset |

Works in: `command`, `args`, `env`, `url`, `headers`

## Authentication

- OAuth 2.0 for remote servers
- Use `/mcp` in Claude Code to authenticate
- Tokens stored securely, auto-refreshed

## Enterprise Configuration

### Managed Servers
System-level config at `managed-mcp.json` (platform-specific paths)

### Access Control

```json
{
  "allowedMcpServers": ["github", "postgres"],
  "deniedMcpServers": ["blocked-server"]
}
```

- `deniedMcpServers` takes absolute precedence
- Match by server name or command

## Using MCP Resources

```
@server:protocol://resource/path
```

Reference resources via `@` mentions in prompts.

## MCP Prompts as Slash Commands

```
/mcp__servername__promptname
```

MCP-provided prompts become accessible as slash commands.

## Output Limits

| Env Var | Default | Max |
|---------|---------|-----|
| `MAX_MCP_OUTPUT_TOKENS` | 10,000 | 25,000 |

Warning threshold for tool output size.

## Common Server Examples

```bash
# GitHub
claude mcp add --transport http github https://api.github.com/mcp

# Local PostgreSQL
claude mcp add -s user -- postgres npx -y @modelcontextprotocol/server-postgres \
  "postgresql://${DB_USER}:${DB_PASS}@localhost/mydb"

# Filesystem access
claude mcp add -s project -- files npx -y @anthropic/mcp-server-filesystem /path/to/dir

# With env vars
claude mcp add -s user -- sentry npx -y @sentry/mcp-server
```

## Project Config (.mcp.json)

Place at project root for team-shared servers:

```json
{
  "mcpServers": {
    "project-db": {
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres", "${DATABASE_URL}"]
    }
  }
}
```

Committed to version control - env vars keep secrets out.
