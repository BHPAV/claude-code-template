# Claude Code Subagents Quick Reference

## File Locations & Priority

| Location | Scope | Priority |
|----------|-------|----------|
| `.claude/agents/` | Project | Highest |
| Plugin `agents/` | Via plugin | Medium |
| `~/.claude/agents/` | User (all projects) | Lowest |

Project-level overrides user-level on name conflict.

## File Format

Markdown with YAML frontmatter:

```yaml
---
name: agent-identifier
description: When this agent should be invoked
tools: Read, Grep, Glob, Bash
model: sonnet
permissionMode: default
skills: skill1, skill2
---

System prompt defining agent role, approach, constraints.
```

## Configuration Fields

| Field | Required | Values |
|-------|----------|--------|
| `name` | Yes | Lowercase, hyphens allowed |
| `description` | Yes | Natural language - triggers auto-delegation |
| `tools` | No | Comma-separated; omit = inherit all |
| `model` | No | `sonnet`, `opus`, `haiku`, `'inherit'` |
| `permissionMode` | No | `default`, `acceptEdits`, `bypassPermissions`, `plan`, `ignore` |
| `skills` | No | Auto-load skills into context |

## Model Selection

| Value | Behavior |
|-------|----------|
| `sonnet` | Default if omitted |
| `opus` | Most capable |
| `haiku` | Fast, low-latency |
| `'inherit'` | Match main conversation model |

## Built-in Subagents

| Agent | Model | Tools | Use Case |
|-------|-------|-------|----------|
| `general-purpose` | Sonnet | All | Multi-step read/write ops |
| `plan` | Sonnet | Read, Glob, Grep, Bash (explore) | Plan mode research |
| `explore` | Haiku | Glob, Grep, Read, Bash (read-only) | Fast search/analysis |

### Explore Thoroughness Levels
- `quick` - Basic searches
- `medium` - Moderate exploration
- `very thorough` - Comprehensive analysis

## Invocation

### Automatic
Claude delegates based on task + agent `description` fields.

Trigger proactive use:
```yaml
description: Code reviewer - use PROACTIVELY after significant changes
```

### Explicit
```
> Use the code-reviewer subagent to check my changes
> Have the debugger subagent investigate this error
```

### Via /agents Command
```
/agents
```
Interactive interface to create, edit, delete, manage permissions.

## CLI Flag

```bash
claude --agents '{
  "code-reviewer": {
    "description": "Expert code reviewer",
    "tools": ["Read", "Grep", "Glob"],
    "model": "sonnet"
  }
}'
```

CLI agents: lower priority than project, higher than user.

## Resumable Agents

Agents get unique `agentId`, maintain transcripts at `agent-{agentId}.jsonl`.

Resume previous conversation:
```
Use resume parameter with agentId to continue with full context
```

## Example: Code Reviewer

```yaml
---
name: code-reviewer
description: Reviews code for quality, security, maintainability - use PROACTIVELY
tools: Read, Grep, Glob, Bash
model: sonnet
---

Review checklist:
- Simplicity and readability
- Naming conventions
- Code duplication
- Error handling
- Secrets/credentials exposure
- Input validation
- Test coverage
- Performance concerns

Run git diff, categorize feedback by priority (critical/major/minor).
```

## Example: Debugger

```yaml
---
name: debugger
description: Root cause analysis and minimal fixes
tools: Read, Grep, Glob, Bash
model: sonnet
---

Process:
1. Capture error messages
2. Identify reproduction steps
3. Isolate failure location
4. Implement minimal fix

Output: explanation, evidence, code fix, test approach, prevention.
```

## Tool Access

| Config | Behavior |
|--------|----------|
| Omit `tools` | Inherit all from main thread (incl MCP) |
| Specify list | Only those tools available |

## Chaining Agents

```
First use analyzer agent, then use optimizer agent on the results
```

## Best Practices

- Start with `/agents` → "Generate with Claude"
- Single clear responsibility per agent
- Detailed system prompts with examples
- Limit tools to necessary only
- Version control `.claude/agents/` for team sharing
