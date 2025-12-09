# Migration Guide

This guide details how to migrate from the current Claudius schema to the enhanced schema. The migration is designed to be non-breaking and can be executed incrementally.

---

## Table of Contents

1. [Pre-Migration Checklist](#pre-migration-checklist)
2. [Phase 1: Schema Extension](#phase-1-schema-extension)
3. [Phase 2: Data Transformation](#phase-2-data-transformation)
4. [Phase 3: Relationship Creation](#phase-3-relationship-creation)
5. [Phase 4: Analytics Population](#phase-4-analytics-population)
6. [Rollback Procedures](#rollback-procedures)
7. [Verification Queries](#verification-queries)

---

## Pre-Migration Checklist

### Backup Current Data
```cypher
// Export current schema to JSON (run in Neo4j Browser or via APOC)
CALL apoc.export.json.all('claudius_backup.json', {useTypes: true})
```

### Verify Current State
```cypher
// Count existing nodes
MATCH (s:ClaudeCodeSession) RETURN 'ClaudeCodeSession' as label, count(s) as count
UNION ALL
MATCH (t:CLIToolCall) RETURN 'CLIToolCall' as label, count(t) as count
UNION ALL
MATCH (p:CLIPrompt) RETURN 'CLIPrompt' as label, count(p) as count
UNION ALL
MATCH (m:CLIMetrics) RETURN 'CLIMetrics' as label, count(m) as count;

// Record counts for verification
```

### Check Indexes
```cypher
SHOW INDEXES;
```

---

## Phase 1: Schema Extension

### 1.1 Create New Constraints
Create unique constraints for new node types.

```cypher
// Run these in order
CREATE CONSTRAINT cli_task_id IF NOT EXISTS FOR (t:CLITask) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT cli_error_id IF NOT EXISTS FOR (e:CLIErrorInstance) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT cli_solution_id IF NOT EXISTS FOR (s:CLISolution) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT cli_capability_id IF NOT EXISTS FOR (c:CLIToolCapability) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT cli_pattern_id IF NOT EXISTS FOR (p:CLICodePattern) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT cli_concept_id IF NOT EXISTS FOR (c:CLIConcept) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT cli_project_id IF NOT EXISTS FOR (p:CLIProjectContext) REQUIRE p.id IS UNIQUE;
```

### 1.2 Create New Indexes
```cypher
// Task indexes
CREATE INDEX cli_task_session IF NOT EXISTS FOR (t:CLITask) ON (t.session_id);
CREATE INDEX cli_task_type IF NOT EXISTS FOR (t:CLITask) ON (t.task_type);
CREATE INDEX cli_task_status IF NOT EXISTS FOR (t:CLITask) ON (t.status);
CREATE INDEX cli_task_success IF NOT EXISTS FOR (t:CLITask) ON (t.success);
CREATE INDEX cli_task_started IF NOT EXISTS FOR (t:CLITask) ON (t.started_at);

// Error indexes
CREATE INDEX cli_error_type IF NOT EXISTS FOR (e:CLIErrorInstance) ON (e.error_type);
CREATE INDEX cli_error_signature IF NOT EXISTS FOR (e:CLIErrorInstance) ON (e.error_signature);
CREATE INDEX cli_error_tool IF NOT EXISTS FOR (e:CLIErrorInstance) ON (e.tool_name);
CREATE INDEX cli_error_resolved IF NOT EXISTS FOR (e:CLIErrorInstance) ON (e.resolved);
CREATE INDEX cli_error_file IF NOT EXISTS FOR (e:CLIErrorInstance) ON (e.file_path);

// Solution indexes
CREATE INDEX cli_solution_type IF NOT EXISTS FOR (s:CLISolution) ON (s.solution_type);
CREATE INDEX cli_solution_signature IF NOT EXISTS FOR (s:CLISolution) ON (s.problem_signature);
CREATE INDEX cli_solution_effectiveness IF NOT EXISTS FOR (s:CLISolution) ON (s.effectiveness_score);

// Capability indexes
CREATE INDEX cli_capability_tool IF NOT EXISTS FOR (c:CLIToolCapability) ON (c.tool_name);
CREATE INDEX cli_capability_context IF NOT EXISTS FOR (c:CLIToolCapability) ON (c.context_type);

// Pattern indexes
CREATE INDEX cli_pattern_type IF NOT EXISTS FOR (p:CLICodePattern) ON (p.pattern_type);
CREATE INDEX cli_pattern_language IF NOT EXISTS FOR (p:CLICodePattern) ON (p.language);

// Concept indexes
CREATE INDEX cli_concept_name IF NOT EXISTS FOR (c:CLIConcept) ON (c.name);
CREATE INDEX cli_concept_category IF NOT EXISTS FOR (c:CLIConcept) ON (c.category);

// Project indexes
CREATE INDEX cli_project_path IF NOT EXISTS FOR (p:CLIProjectContext) ON (p.project_path);
CREATE INDEX cli_project_type IF NOT EXISTS FOR (p:CLIProjectContext) ON (p.project_type);

// Enhanced existing indexes
CREATE INDEX cli_prompt_intent IF NOT EXISTS FOR (p:CLIPrompt) ON (p.intent_type);
CREATE INDEX cli_tool_context IF NOT EXISTS FOR (t:CLIToolCall) ON (t.context_type);
CREATE INDEX cli_tool_sequence IF NOT EXISTS FOR (t:CLIToolCall) ON (t.sequence_index);
CREATE INDEX cli_tool_task IF NOT EXISTS FOR (t:CLIToolCall) ON (t.parent_task_id);
```

### 1.3 Create Full-Text Indexes
```cypher
CREATE FULLTEXT INDEX cli_task_search IF NOT EXISTS
FOR (t:CLITask) ON EACH [t.description];

CREATE FULLTEXT INDEX cli_error_search IF NOT EXISTS
FOR (e:CLIErrorInstance) ON EACH [e.error_message, e.context_summary];

CREATE FULLTEXT INDEX cli_solution_search IF NOT EXISTS
FOR (s:CLISolution) ON EACH [s.solution_summary, s.problem_signature];

CREATE FULLTEXT INDEX cli_prompt_search IF NOT EXISTS
FOR (p:CLIPrompt) ON EACH [p.prompt_text];

CREATE FULLTEXT INDEX cli_pattern_search IF NOT EXISTS
FOR (p:CLICodePattern) ON EACH [p.pattern_text, p.description];
```

---

## Phase 2: Data Transformation

### 2.1 Add Sequence Index to Tool Calls
Add ordering information to existing tool calls.

```cypher
// Add sequence_index to CLIToolCall nodes
MATCH (s:ClaudeCodeSession)
MATCH (t:CLIToolCall)-[:PART_OF_SESSION]->(s)
WITH s, t
ORDER BY t.timestamp

WITH s, collect(t) as tools
UNWIND range(0, size(tools)-1) as idx
WITH tools[idx] as tool, idx
SET tool.sequence_index = idx;
```

### 2.2 Add Sequence Index to Prompts
```cypher
// Add sequence_index to CLIPrompt nodes
MATCH (s:ClaudeCodeSession)
MATCH (p:CLIPrompt)-[:PART_OF_SESSION]->(s)
WITH s, p
ORDER BY p.timestamp

WITH s, collect(p) as prompts
UNWIND range(0, size(prompts)-1) as idx
WITH prompts[idx] as prompt, idx
SET prompt.sequence_index = idx;
```

### 2.3 Classify Tool Context Types
Add context classification to existing tools.

```cypher
// Classify tool context types based on tool name
MATCH (t:CLIToolCall)
WHERE t.context_type IS NULL
SET t.context_type = CASE
  WHEN t.tool_name IN ['Read', 'Glob', 'Grep'] THEN 'exploration'
  WHEN t.tool_name IN ['Write', 'Edit', 'MultiEdit', 'NotebookEdit'] THEN 'implementation'
  WHEN t.tool_name IN ['Bash'] AND t.inputs CONTAINS 'test' THEN 'verification'
  WHEN t.tool_name IN ['Bash'] AND t.inputs CONTAINS 'build' THEN 'verification'
  ELSE 'implementation'
END;
```

### 2.4 Extract Project Paths
Normalize and extract project paths from sessions.

```cypher
// Extract project path from working directory
MATCH (s:ClaudeCodeSession)
WHERE s.project_path IS NULL AND s.working_dir IS NOT NULL
SET s.project_path = replace(s.working_dir, '\\', '/');
```

### 2.5 Detect Intent Types for Prompts
Classify prompt intents based on keywords.

```cypher
// Classify prompt intent types (basic keyword matching)
MATCH (p:CLIPrompt)
WHERE p.intent_type IS NULL AND p.prompt_text IS NOT NULL
SET p.intent_type = CASE
  WHEN toLower(p.prompt_text) CONTAINS 'fix' OR toLower(p.prompt_text) CONTAINS 'bug' OR toLower(p.prompt_text) CONTAINS 'error' THEN 'debug'
  WHEN toLower(p.prompt_text) CONTAINS 'add' OR toLower(p.prompt_text) CONTAINS 'create' OR toLower(p.prompt_text) CONTAINS 'implement' THEN 'implement'
  WHEN toLower(p.prompt_text) CONTAINS 'refactor' OR toLower(p.prompt_text) CONTAINS 'clean' OR toLower(p.prompt_text) CONTAINS 'reorganize' THEN 'refactor'
  WHEN toLower(p.prompt_text) CONTAINS 'find' OR toLower(p.prompt_text) CONTAINS 'search' OR toLower(p.prompt_text) CONTAINS 'where' THEN 'search'
  WHEN toLower(p.prompt_text) CONTAINS 'explain' OR toLower(p.prompt_text) CONTAINS 'what' OR toLower(p.prompt_text) CONTAINS 'how' THEN 'explain'
  ELSE 'implement'
END;
```

---

## Phase 3: Relationship Creation

### 3.1 Create FOLLOWED_BY Relationships
Link sequential tool calls.

```cypher
// Create FOLLOWED_BY relationships between sequential tools
MATCH (s:ClaudeCodeSession)
MATCH (t1:CLIToolCall)-[:PART_OF_SESSION]->(s)
MATCH (t2:CLIToolCall)-[:PART_OF_SESSION]->(s)
WHERE t1.sequence_index = t2.sequence_index - 1
  AND NOT exists((t1)-[:FOLLOWED_BY]->(t2))

CREATE (t1)-[:FOLLOWED_BY {
  gap_ms: duration.between(t1.timestamp, t2.timestamp).milliseconds,
  same_file: CASE WHEN t1.file_path = t2.file_path THEN true ELSE false END
}]->(t2);
```

### 3.2 Create NEXT_PROMPT Relationships
Link sequential prompts.

```cypher
// Create NEXT_PROMPT relationships
MATCH (s:ClaudeCodeSession)
MATCH (p1:CLIPrompt)-[:PART_OF_SESSION]->(s)
MATCH (p2:CLIPrompt)-[:PART_OF_SESSION]->(s)
WHERE p1.sequence_index = p2.sequence_index - 1
  AND NOT exists((p1)-[:NEXT_PROMPT]->(p2))

CREATE (p1)-[:NEXT_PROMPT {
  gap_ms: duration.between(p1.timestamp, p2.timestamp).milliseconds
}]->(p2);
```

### 3.3 Create TRIGGERED Relationships
Link prompts to the tools they triggered.

```cypher
// Create TRIGGERED relationships (prompt -> first tool after it)
MATCH (s:ClaudeCodeSession)
MATCH (p:CLIPrompt)-[:PART_OF_SESSION]->(s)
MATCH (t:CLIToolCall)-[:PART_OF_SESSION]->(s)
WHERE t.timestamp > p.timestamp
WITH s, p, t
ORDER BY t.timestamp
WITH s, p, collect(t)[0] as first_tool
WHERE first_tool IS NOT NULL
  AND NOT exists((p)-[:TRIGGERED]->(first_tool))

CREATE (p)-[:TRIGGERED {
  confidence: 0.8
}]->(first_tool);
```

### 3.4 Create Project Context Nodes
```cypher
// Create CLIProjectContext nodes from sessions
MATCH (s:ClaudeCodeSession)
WHERE s.project_path IS NOT NULL
WITH s.project_path as path, collect(s) as sessions
WITH path, sessions, sessions[0] as first_session

MERGE (proj:CLIProjectContext {
  id: 'project:' + apoc.util.md5([path])
})
ON CREATE SET
  proj.project_path = path,
  proj.project_name = split(path, '/')[-1],
  proj.session_count = size(sessions),
  proj.created_at = datetime(),
  proj.last_accessed_at = datetime()
ON MATCH SET
  proj.session_count = size(sessions),
  proj.last_accessed_at = datetime();
```

### 3.5 Create IN_PROJECT Relationships
```cypher
// Link sessions to projects
MATCH (s:ClaudeCodeSession)
WHERE s.project_path IS NOT NULL
MATCH (proj:CLIProjectContext {project_path: s.project_path})
WHERE NOT exists((s)-[:IN_PROJECT]->(proj))
CREATE (s)-[:IN_PROJECT]->(proj);
```

---

## Phase 4: Analytics Population

### 4.1 Create CLITask Nodes (Auto-Detection)
Group prompts and tools into tasks based on time gaps.

```cypher
// Create tasks from sessions (gap-based detection)
// A new task starts when there's a gap > 5 minutes between prompts
MATCH (s:ClaudeCodeSession {status: 'completed'})
MATCH (p:CLIPrompt)-[:PART_OF_SESSION]->(s)
WITH s, p
ORDER BY p.timestamp

WITH s, collect(p) as prompts
WHERE size(prompts) > 0

// For now, create one task per session (can be refined later)
MERGE (task:CLITask {
  id: 'cli_task:' + s.session_id + ':0'
})
ON CREATE SET
  task.session_id = s.session_id,
  task.task_type = prompts[0].intent_type,
  task.status = 'completed',
  task.started_at = prompts[0].timestamp,
  task.completed_at = prompts[-1].timestamp,
  task.prompt_count = size(prompts),
  task.success = true,
  task.created_at = datetime();
```

### 4.2 Link Prompts and Tools to Tasks
```cypher
// Link prompts to tasks
MATCH (task:CLITask)
MATCH (p:CLIPrompt {session_id: task.session_id})
WHERE NOT exists((p)-[:PART_OF_TASK]->(task))
CREATE (p)-[:PART_OF_TASK {
  sequence_index: p.sequence_index
}]->(task);

// Link tools to tasks
MATCH (task:CLITask)
MATCH (t:CLIToolCall {session_id: task.session_id})
WHERE NOT exists((t)-[:PART_OF_TASK]->(task))
CREATE (t)-[:PART_OF_TASK {
  sequence_index: t.sequence_index
}]->(task);

// Update task tool count
MATCH (task:CLITask)
OPTIONAL MATCH (t:CLIToolCall)-[:PART_OF_TASK]->(task)
WITH task, count(t) as tool_count
SET task.tool_count = tool_count;
```

### 4.3 Create CLIErrorInstance Nodes
Extract errors from failed tool calls.

```cypher
// Create error instances from failed tools
MATCH (t:CLIToolCall)
WHERE t.success = false AND t.error IS NOT NULL

MERGE (err:CLIErrorInstance {
  id: 'cli_error:' + t.session_id + ':' + toString(t.timestamp)
})
ON CREATE SET
  err.session_id = t.session_id,
  err.error_type = CASE
    WHEN toLower(t.error) CONTAINS 'permission' THEN 'permission'
    WHEN toLower(t.error) CONTAINS 'not found' OR toLower(t.error) CONTAINS 'no such' THEN 'not_found'
    WHEN toLower(t.error) CONTAINS 'timeout' THEN 'timeout'
    WHEN toLower(t.error) CONTAINS 'syntax' THEN 'syntax'
    ELSE 'runtime'
  END,
  err.error_signature = left(t.error, 100),
  err.error_message = left(t.error, 1000),
  err.tool_name = t.tool_name,
  err.file_path = t.file_path,
  err.resolved = false,
  err.created_at = t.timestamp

// Create CAUSED_ERROR relationship
MERGE (t)-[:CAUSED_ERROR]->(err);
```

### 4.4 Detect Resolved Errors
Mark errors as resolved if followed by successful tool call on same file.

```cypher
// Mark errors as resolved if same file was successfully accessed later
MATCH (err:CLIErrorInstance {resolved: false})
MATCH (t:CLIToolCall)-[:CAUSED_ERROR]->(err)
MATCH (later:CLIToolCall)
WHERE later.session_id = t.session_id
  AND later.file_path = t.file_path
  AND later.timestamp > t.timestamp
  AND later.success = true

WITH err, later
ORDER BY later.timestamp
LIMIT 1

SET err.resolved = true,
    err.resolution_tool = later.tool_name,
    err.time_to_resolution_ms = duration.between(err.created_at, later.timestamp).milliseconds;
```

### 4.5 Create CLIToolCapability Nodes
Aggregate tool statistics by context.

```cypher
// Create capability nodes from tool usage
MATCH (t:CLIToolCall)
WHERE t.context_type IS NOT NULL

WITH t.tool_name as tool_name,
     t.context_type as context_type,
     count(*) as total_uses,
     avg(t.duration_ms) as avg_duration,
     sum(CASE WHEN t.success THEN 1 ELSE 0 END) as success_count

WHERE total_uses >= 3

MERGE (cap:CLIToolCapability {
  id: 'capability:' + tool_name + ':' + context_type
})
SET cap.tool_name = tool_name,
    cap.context_type = context_type,
    cap.total_uses = total_uses,
    cap.avg_duration_ms = avg_duration,
    cap.success_rate = toFloat(success_count) / total_uses,
    cap.updated_at = datetime();
```

---

## Rollback Procedures

### Remove New Relationships
```cypher
// Remove FOLLOWED_BY
MATCH ()-[r:FOLLOWED_BY]->()
DELETE r;

// Remove NEXT_PROMPT
MATCH ()-[r:NEXT_PROMPT]->()
DELETE r;

// Remove TRIGGERED
MATCH ()-[r:TRIGGERED]->()
DELETE r;

// Remove PART_OF_TASK
MATCH ()-[r:PART_OF_TASK]->()
DELETE r;

// Remove IN_PROJECT
MATCH ()-[r:IN_PROJECT]->()
DELETE r;

// Remove CAUSED_ERROR
MATCH ()-[r:CAUSED_ERROR]->()
DELETE r;
```

### Remove New Nodes
```cypher
// Remove CLITask nodes
MATCH (n:CLITask) DETACH DELETE n;

// Remove CLIErrorInstance nodes
MATCH (n:CLIErrorInstance) DETACH DELETE n;

// Remove CLISolution nodes
MATCH (n:CLISolution) DETACH DELETE n;

// Remove CLIToolCapability nodes
MATCH (n:CLIToolCapability) DETACH DELETE n;

// Remove CLICodePattern nodes
MATCH (n:CLICodePattern) DETACH DELETE n;

// Remove CLIConcept nodes
MATCH (n:CLIConcept) DETACH DELETE n;

// Remove CLIProjectContext nodes
MATCH (n:CLIProjectContext) DETACH DELETE n;
```

### Remove New Properties
```cypher
// Remove added properties from CLIToolCall
MATCH (t:CLIToolCall)
REMOVE t.sequence_index, t.context_type, t.parent_task_id;

// Remove added properties from CLIPrompt
MATCH (p:CLIPrompt)
REMOVE p.sequence_index, p.intent_type, p.task_id;

// Remove added properties from ClaudeCodeSession
MATCH (s:ClaudeCodeSession)
REMOVE s.project_path;
```

### Remove New Indexes
```cypher
DROP INDEX cli_task_session IF EXISTS;
DROP INDEX cli_task_type IF EXISTS;
DROP INDEX cli_task_status IF EXISTS;
DROP INDEX cli_task_success IF EXISTS;
DROP INDEX cli_task_started IF EXISTS;
// ... (continue for all new indexes)
```

---

## Verification Queries

### Verify Node Counts
```cypher
// Count all nodes by label
CALL db.labels() YIELD label
CALL apoc.cypher.run('MATCH (n:`' + label + '`) RETURN count(n) as count', {})
YIELD value
RETURN label, value.count as count
ORDER BY count DESC;
```

### Verify Relationship Counts
```cypher
// Count all relationships by type
CALL db.relationshipTypes() YIELD relationshipType
CALL apoc.cypher.run('MATCH ()-[r:`' + relationshipType + '`]->() RETURN count(r) as count', {})
YIELD value
RETURN relationshipType, value.count as count
ORDER BY count DESC;
```

### Verify Data Integrity
```cypher
// Verify all tools have sequence_index
MATCH (t:CLIToolCall)
WHERE t.sequence_index IS NULL
RETURN 'Tools missing sequence_index' as issue, count(t) as count;

// Verify all tasks have at least one prompt
MATCH (task:CLITask)
WHERE NOT exists((task)<-[:PART_OF_TASK]-(:CLIPrompt))
RETURN 'Tasks without prompts' as issue, count(task) as count;

// Verify FOLLOWED_BY chain integrity
MATCH (t1:CLIToolCall)-[:FOLLOWED_BY]->(t2:CLIToolCall)
WHERE t1.sequence_index >= t2.sequence_index
RETURN 'Invalid FOLLOWED_BY order' as issue, count(*) as count;
```

### Verify Index Usage
```cypher
// Profile a common query to verify indexes are used
PROFILE
MATCH (t:CLIToolCall {tool_name: 'Read'})
WHERE t.success = true
RETURN count(t);
```
