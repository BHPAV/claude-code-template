# Agent Review & Test Prompt for Claudius Hooks System

Use this prompt to guide a Claude Code agent through reviewing and testing the Claudius logging system.

---

## Prompt

```
Review and test the Claudius hooks system to verify agent actions are being logged correctly to Neo4j.

## Tasks

### 1. Verify Hook Configuration
Check `.claude/settings.local.json` and confirm ALL these hooks are registered:
- UserPromptSubmit → prompt_hooks.py
- SessionStart → session_hooks.py start
- SessionEnd → session_hooks.py end
- PreToolUse → tool_hooks.py (matcher: *)
- PostToolUse → tool_hooks.py (matcher: *)

### 2. Test Neo4j Connectivity
Run from `.claude/hooks/` directory:
```python
from config import is_neo4j_available
print('Neo4j available:', is_neo4j_available())
```

If False, check environment variables:
- NEO4J_URI (default: bolt://localhost:7687)
- NEO4J_USER (default: neo4j)
- NEO4J_PASSWORD
- NEO4J_DATABASE

### 3. Query Current Session Data
Query Neo4j to verify THIS session is being logged:
```cypher
// Check recent sessions
MATCH (s:ClaudeCodeSession)
RETURN s.session_id, s.start_time, s.prompt_count, s.tool_count
ORDER BY s.start_time DESC LIMIT 5;

// Check recent tool calls
MATCH (t:CLIToolCall)-[:PART_OF_SESSION]->(s:ClaudeCodeSession)
RETURN s.session_id, t.tool_name, t.duration_ms, t.success, t.timestamp
ORDER BY t.timestamp DESC LIMIT 10;

// Check recent prompts
MATCH (p:CLIPrompt)-[:PART_OF_SESSION]->(s:ClaudeCodeSession)
RETURN s.session_id, left(p.prompt_text, 50) as prompt_preview, p.timestamp
ORDER BY p.timestamp DESC LIMIT 5;
```

### 4. Verify Tool Call Logging
Perform a few tool operations (Read, Glob, Bash) then query:
```cypher
MATCH (t:CLIToolCall)
WHERE t.timestamp > datetime() - duration('PT5M')
RETURN t.tool_name, t.duration_ms, t.success
ORDER BY t.timestamp DESC;
```

Expected: You should see YOUR tool calls from this session appearing.

### 5. Check for Common Issues

**Issue: Tool calls not appearing**
- Verify PostToolUse hook is registered (not just PreToolUse)
- Check `.tool_call_cache.json` - if entries accumulate but aren't cleared, PostToolUse isn't firing

**Issue: Sessions not appearing**
- Check if `.session_cache.json` exists and has current session
- Verify SessionStart hook is registered

**Issue: Neo4j connection errors**
- Check stderr output from hooks: `[CLI Hook]` prefix indicates hook errors
- Verify database exists: the configured NEO4J_DATABASE must exist

### 6. Test Individual Hooks Manually
```bash
# Test prompt hook
echo '{"sessionId":"test-manual","prompt":"test prompt"}' | python .claude/hooks/prompt_hooks.py

# Test session start
echo '{"event":"SessionStart","sessionId":"test-manual"}' | python .claude/hooks/session_hooks.py start

# Test tool pre/post
echo '{"event":"PreToolUse","sessionId":"test-manual","toolName":"Read","toolInput":{"file_path":"/test"}}' | python .claude/hooks/tool_hooks.py

echo '{"event":"PostToolUse","sessionId":"test-manual","toolName":"Read","toolInput":{"file_path":"/test"},"toolOutput":"file contents"}' | python .claude/hooks/tool_hooks.py
```

### 7. Report Findings
Summarize:
- [ ] All hooks registered correctly
- [ ] Neo4j connectivity working
- [ ] Current session appearing in database
- [ ] Tool calls being logged with timing
- [ ] Prompts being captured
- [ ] File relationships created (ACCESSED_FILE)
- [ ] Any errors or issues found

## Expected Healthy State
- Session node created on SessionStart
- Each prompt creates CLIPrompt node linked to session
- Each tool use creates CLIToolCall node with duration_ms > 0
- Tool calls with file_path input have ACCESSED_FILE relationship
- Session counters (prompt_count, tool_count) increment
- SessionEnd creates CLIMetrics summary node
```

---

## Quick Health Check Query

```cypher
// Run this single query to check system health
MATCH (s:ClaudeCodeSession)
WHERE s.start_time > datetime() - duration('PT1H')
OPTIONAL MATCH (t:CLIToolCall)-[:PART_OF_SESSION]->(s)
OPTIONAL MATCH (p:CLIPrompt)-[:PART_OF_SESSION]->(s)
RETURN
  s.session_id,
  s.start_time,
  count(DISTINCT t) as tool_calls,
  count(DISTINCT p) as prompts
ORDER BY s.start_time DESC;
```
