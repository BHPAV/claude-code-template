# Agent Query Cookbook

This document provides Cypher query patterns for agents to gather context from the Claudius Neo4j database. All queries assume the database is selected with `USE claude_hooks`.

---

## Table of Contents

1. [Context Gathering](#context-gathering)
2. [Task Similarity](#task-similarity)
3. [Error Resolution](#error-resolution)
4. [Tool Capabilities](#tool-capabilities)
5. [Pattern Recognition](#pattern-recognition)
6. [Project Context](#project-context)
7. [Performance Tips](#performance-tips)

---

## Context Gathering

### Get Recent Session Context
Retrieve context from recent sessions for the current working directory.

```cypher
// Get last 5 sessions in this project with their tasks
MATCH (s:ClaudeCodeSession)
WHERE s.project_path = $project_path
  AND s.status = 'completed'
ORDER BY s.start_time DESC
LIMIT 5

OPTIONAL MATCH (t:CLITask)-[:PART_OF_SESSION]->(s)
WHERE t.success = true

RETURN s.session_id,
       s.primary_intent,
       s.start_time,
       collect({
         type: t.task_type,
         description: t.description,
         success: t.success
       }) as tasks
```

### Get File Context
Comprehensive context for working with a specific file.

```cypher
// All context for a file: recent ops, errors, related files
MATCH (f:File {path: $file_path})

// Recent tool operations (last 7 days)
OPTIONAL MATCH (tool:CLIToolCall)-[:ACCESSED_FILE]->(f)
WHERE tool.timestamp > datetime() - duration('P7D')
WITH f, collect(tool {
  .tool_name, .success, .duration_ms, .timestamp, .context_type
})[0..10] as recent_ops

// Errors on this file with solutions
OPTIONAL MATCH (err:CLIErrorInstance {file_path: f.path, resolved: true})
OPTIONAL MATCH (err)-[:RESOLVED_BY]->(sol:CLISolution)
WITH f, recent_ops, collect(DISTINCT {
  error_type: err.error_type,
  error_message: err.error_message,
  solution: sol.solution_summary,
  tool_sequence: sol.tool_sequence
})[0..5] as error_solutions

// Related files (frequently accessed together)
OPTIONAL MATCH (tool:CLIToolCall)-[:ACCESSED_FILE]->(f)
OPTIONAL MATCH (tool)-[:FOLLOWED_BY*1..2]-(related_tool:CLIToolCall)
OPTIONAL MATCH (related_tool)-[:ACCESSED_FILE]->(related:File)
WHERE related.path <> f.path
WITH f, recent_ops, error_solutions,
     collect(DISTINCT related.path)[0..5] as related_files

RETURN f.path,
       recent_ops,
       error_solutions,
       related_files
```

### Get Current Task Context
Context for the active task in a session.

```cypher
// Active task with all its prompts and tools
MATCH (task:CLITask {session_id: $session_id, status: 'active'})

OPTIONAL MATCH (p:CLIPrompt)-[:PART_OF_TASK]->(task)
OPTIONAL MATCH (t:CLIToolCall)-[:PART_OF_TASK]->(task)

WITH task,
     collect(DISTINCT p {.prompt_text, .intent_type, .timestamp}) as prompts,
     collect(DISTINCT t {.tool_name, .success, .file_path}) as tools

// Find similar completed tasks
OPTIONAL MATCH (similar:CLITask)
WHERE similar.status = 'completed'
  AND similar.success = true
  AND similar.id <> task.id
  AND (similar.task_type = task.task_type
       OR any(kw IN task.keywords WHERE kw IN similar.keywords))
WITH task, prompts, tools,
     collect(similar {.description, .task_type, .tool_count})[0..3] as similar_tasks

RETURN task.task_type,
       task.description,
       task.keywords,
       prompts,
       tools,
       similar_tasks
```

---

## Task Similarity

### Find Similar Past Tasks
Find tasks similar to the current one by keywords and type.

```cypher
// Keyword-based similarity
MATCH (current:CLITask {id: $current_task_id})
MATCH (past:CLITask)
WHERE past.id <> current.id
  AND past.status = 'completed'
  AND past.success = true

// Calculate keyword overlap
WITH current, past,
     [kw IN current.keywords WHERE kw IN past.keywords] as matching_keywords

WHERE size(matching_keywords) > 0
   OR past.task_type = current.task_type

// Get tools used in past task
OPTIONAL MATCH (tool:CLIToolCall)-[:PART_OF_TASK]->(past)
WHERE tool.success = true

RETURN past.id,
       past.task_type,
       past.description,
       matching_keywords,
       past.complexity_score,
       collect(DISTINCT tool.tool_name) as tools_used
ORDER BY size(matching_keywords) DESC, past.completed_at DESC
LIMIT 5
```

### Find Tasks by Full-Text Search
Search task descriptions semantically.

```cypher
// Full-text search on task descriptions
CALL db.index.fulltext.queryNodes('cli_task_search', $search_query)
YIELD node as task, score
WHERE task.status = 'completed' AND task.success = true

OPTIONAL MATCH (tool:CLIToolCall)-[:PART_OF_TASK]->(task)
WHERE tool.success = true

RETURN task.id,
       task.description,
       task.task_type,
       score,
       collect(DISTINCT tool.tool_name) as tools_used
ORDER BY score DESC
LIMIT 10
```

### Find Tasks Involving Concept
Find tasks that worked with a specific technology/concept.

```cypher
// Tasks involving a concept
MATCH (task:CLITask)-[r:INVOLVES_CONCEPT]->(concept:CLIConcept {name: $concept_name})
WHERE task.status = 'completed'

WITH task, r.relevance as relevance
ORDER BY relevance DESC, task.completed_at DESC
LIMIT 10

OPTIONAL MATCH (tool:CLIToolCall)-[:PART_OF_TASK]->(task)
OPTIONAL MATCH (err:CLIErrorInstance)-[:CAUSED_ERROR]-(tool)
OPTIONAL MATCH (err)-[:RESOLVED_BY]->(sol:CLISolution)

RETURN task.description,
       task.task_type,
       task.success,
       relevance,
       collect(DISTINCT tool.tool_name) as tools,
       collect(DISTINCT sol.solution_summary)[0..2] as solutions_used
```

---

## Error Resolution

### Find Solutions for Error Type
Match errors by type and find solutions that worked.

```cypher
// Solutions for a specific error type
MATCH (err:CLIErrorInstance {error_type: $error_type})
WHERE err.resolved = true
MATCH (err)-[:RESOLVED_BY]->(sol:CLISolution)
WHERE sol.effectiveness_score > 0.6

RETURN sol.solution_type,
       sol.solution_summary,
       sol.tool_sequence,
       sol.effectiveness_score,
       sol.avg_time_to_apply_ms,
       count(err) as times_used
ORDER BY sol.effectiveness_score DESC, times_used DESC
LIMIT 5
```

### Find Solutions by Error Signature
Match errors by normalized signature pattern.

```cypher
// Exact signature match
MATCH (err:CLIErrorInstance)
WHERE err.error_signature = $error_signature
  AND err.resolved = true
MATCH (err)-[:RESOLVED_BY]->(sol:CLISolution)

RETURN sol.solution_summary,
       sol.tool_sequence,
       sol.effectiveness_score,
       err.resolution_summary
ORDER BY sol.effectiveness_score DESC
LIMIT 3

UNION

// Partial signature match (fallback)
MATCH (err:CLIErrorInstance)
WHERE err.error_signature CONTAINS $partial_signature
  AND err.resolved = true
MATCH (err)-[:RESOLVED_BY]->(sol:CLISolution)

RETURN sol.solution_summary,
       sol.tool_sequence,
       sol.effectiveness_score,
       err.resolution_summary
ORDER BY sol.effectiveness_score DESC
LIMIT 3
```

### Find Solutions by Full-Text Search
Search error messages and solutions semantically.

```cypher
// Search error messages
CALL db.index.fulltext.queryNodes('cli_error_search', $error_text)
YIELD node as err, score
WHERE err.resolved = true

MATCH (err)-[:RESOLVED_BY]->(sol:CLISolution)

RETURN err.error_type,
       err.error_message,
       sol.solution_summary,
       sol.tool_sequence,
       sol.effectiveness_score,
       score as match_score
ORDER BY match_score DESC, sol.effectiveness_score DESC
LIMIT 5
```

### Get Error Patterns for Tool
Common errors when using a specific tool.

```cypher
// Error patterns for a tool
MATCH (err:CLIErrorInstance {tool_name: $tool_name})

WITH err.error_type as error_type,
     err.error_signature as signature,
     count(*) as occurrence_count,
     sum(CASE WHEN err.resolved THEN 1 ELSE 0 END) as resolved_count

ORDER BY occurrence_count DESC
LIMIT 10

OPTIONAL MATCH (e:CLIErrorInstance {error_signature: signature, resolved: true})
OPTIONAL MATCH (e)-[:RESOLVED_BY]->(sol:CLISolution)

RETURN error_type,
       signature,
       occurrence_count,
       resolved_count,
       toFloat(resolved_count) / occurrence_count as resolution_rate,
       collect(DISTINCT sol.solution_summary)[0] as top_solution
```

---

## Tool Capabilities

### Get Tool Capability Summary
Overall capabilities and success patterns for a tool.

```cypher
// Tool capability summary
MATCH (cap:CLIToolCapability {tool_name: $tool_name})

RETURN cap.context_type,
       cap.description,
       cap.success_rate,
       cap.avg_duration_ms,
       cap.total_uses,
       cap.best_practices,
       cap.common_errors
ORDER BY cap.success_rate DESC
```

### Best Tool for Context
Find the best tool for a given context type.

```cypher
// Best tools for a context
MATCH (cap:CLIToolCapability {context_type: $context_type})
WHERE cap.total_uses >= 10  // Minimum sample size

RETURN cap.tool_name,
       cap.success_rate,
       cap.avg_duration_ms,
       cap.best_practices
ORDER BY cap.success_rate DESC, cap.avg_duration_ms ASC
LIMIT 5
```

### Tool Effectiveness for Concept
How well a tool works with a specific technology/concept.

```cypher
// Tool effectiveness for a concept
MATCH (cap:CLIToolCapability)-[r:EFFECTIVE_FOR]->(concept:CLIConcept {name: $concept_name})
WHERE r.sample_count >= 5

RETURN cap.tool_name,
       cap.context_type,
       r.effectiveness_score,
       r.sample_count,
       cap.best_practices
ORDER BY r.effectiveness_score DESC
```

### Predict Next Tool
Based on current tool, predict likely next tool.

```cypher
// Tool sequence prediction
MATCH (current:CLIToolCall {tool_name: $current_tool})
WHERE current.success = true
MATCH (current)-[:FOLLOWED_BY]->(next:CLIToolCall)
WHERE next.success = true

WITH next.tool_name as next_tool,
     count(*) as frequency,
     avg(CASE WHEN next.success THEN 1.0 ELSE 0.0 END) as success_rate
WHERE frequency >= 3

RETURN next_tool,
       frequency,
       success_rate
ORDER BY frequency DESC, success_rate DESC
LIMIT 5
```

### Common Tool Sequences
Find common successful tool sequences for a task type.

```cypher
// Common tool sequences for task type
MATCH (task:CLITask {task_type: $task_type, success: true})
MATCH (tool:CLIToolCall)-[:PART_OF_TASK]->(task)
WHERE tool.success = true

WITH task, tool
ORDER BY task.id, tool.sequence_index

WITH task, collect(tool.tool_name) as tool_sequence
WHERE size(tool_sequence) >= 2

WITH tool_sequence, count(*) as occurrences
WHERE occurrences >= 3

RETURN tool_sequence,
       occurrences
ORDER BY occurrences DESC
LIMIT 10
```

---

## Pattern Recognition

### Find Code Patterns
Search for reusable code patterns.

```cypher
// Patterns by language and type
MATCH (p:CLICodePattern)
WHERE p.language = $language
  AND p.pattern_type = $pattern_type
  AND p.success_rate > 0.7

RETURN p.pattern_text,
       p.description,
       p.use_count,
       p.success_rate,
       p.tags
ORDER BY p.use_count DESC, p.success_rate DESC
LIMIT 10
```

### Search Patterns by Tags
Find patterns with specific tags.

```cypher
// Patterns with matching tags
MATCH (p:CLICodePattern)
WHERE any(tag IN $tags WHERE tag IN p.tags)

RETURN p.pattern_type,
       p.language,
       p.pattern_text,
       p.description,
       p.success_rate,
       [tag IN $tags WHERE tag IN p.tags] as matching_tags
ORDER BY size(matching_tags) DESC, p.success_rate DESC
LIMIT 10
```

### Full-Text Pattern Search
Search pattern text semantically.

```cypher
// Full-text search on patterns
CALL db.index.fulltext.queryNodes('cli_pattern_search', $search_query)
YIELD node as pattern, score

RETURN pattern.pattern_type,
       pattern.language,
       pattern.pattern_text,
       pattern.description,
       pattern.success_rate,
       score
ORDER BY score DESC
LIMIT 10
```

---

## Project Context

### Get Project Overview
Comprehensive project context.

```cypher
// Project context with stats
MATCH (proj:CLIProjectContext {project_path: $project_path})

// Session stats
OPTIONAL MATCH (s:ClaudeCodeSession)-[:IN_PROJECT]->(proj)
WHERE s.status = 'completed'

WITH proj, count(s) as total_sessions,
     sum(s.tool_call_count) as total_tools,
     avg(s.resolution_rate) as avg_resolution_rate

// Common task types
OPTIONAL MATCH (task:CLITask)<-[:PART_OF_SESSION]-(sess:ClaudeCodeSession)-[:IN_PROJECT]->(proj)
WHERE task.success = true

WITH proj, total_sessions, total_tools, avg_resolution_rate,
     collect(task.task_type) as task_types

RETURN proj.project_name,
       proj.project_type,
       proj.tech_stack,
       proj.key_files,
       proj.test_commands,
       proj.build_commands,
       proj.conventions,
       total_sessions,
       total_tools,
       avg_resolution_rate,
       apoc.coll.frequencies(task_types)[0..5] as common_task_types
```

### Get Related Concepts for Project
Concepts frequently used in this project.

```cypher
// Concepts in this project
MATCH (sess:ClaudeCodeSession)-[:IN_PROJECT]->(proj:CLIProjectContext {project_path: $project_path})
MATCH (task:CLITask)-[:PART_OF_SESSION]->(sess)
MATCH (task)-[r:INVOLVES_CONCEPT]->(concept:CLIConcept)

WITH concept, sum(r.relevance) as total_relevance, count(DISTINCT task) as task_count

RETURN concept.name,
       concept.category,
       total_relevance,
       task_count
ORDER BY total_relevance DESC
LIMIT 15
```

---

## Performance Tips

### Use Parameters
Always use parameters instead of string interpolation to enable query caching:

```cypher
// Good - uses parameter
MATCH (t:CLITask {task_type: $task_type})
RETURN t

// Bad - string interpolation prevents caching
// MATCH (t:CLITask {task_type: 'implement'})
```

### Limit Early
Apply LIMIT early in multi-match queries:

```cypher
// Good - limits before expensive operations
MATCH (task:CLITask {status: 'completed'})
ORDER BY task.completed_at DESC
LIMIT 10

OPTIONAL MATCH (tool:CLIToolCall)-[:PART_OF_TASK]->(task)
RETURN task, collect(tool)

// Bad - collects everything before limiting
// MATCH (task:CLITask {status: 'completed'})
// OPTIONAL MATCH (tool:CLIToolCall)-[:PART_OF_TASK]->(task)
// RETURN task, collect(tool)
// ORDER BY task.completed_at DESC
// LIMIT 10
```

### Use Indexed Properties in WHERE
Filter on indexed properties first:

```cypher
// Good - filters on indexed properties
MATCH (t:CLIToolCall)
WHERE t.tool_name = $tool_name  // indexed
  AND t.success = true          // indexed
  AND t.duration_ms > 1000      // not indexed (applied after)

// Bad - non-indexed filter first
// WHERE t.duration_ms > 1000
//   AND t.tool_name = $tool_name
```

### Avoid Cartesian Products
Be explicit about relationships:

```cypher
// Good - explicit relationship
MATCH (task:CLITask)-[:PART_OF_SESSION]->(session:ClaudeCodeSession)

// Bad - can create cartesian product
// MATCH (task:CLITask), (session:ClaudeCodeSession)
// WHERE task.session_id = session.session_id
```

### Use OPTIONAL MATCH for Nullable Paths
Prevent query failure when paths don't exist:

```cypher
// Good - returns task even without errors
MATCH (task:CLITask {id: $task_id})
OPTIONAL MATCH (err:CLIErrorInstance)-[:CAUSED_ERROR]-(:CLIToolCall)-[:PART_OF_TASK]->(task)
RETURN task, collect(err)

// Bad - returns nothing if no errors
// MATCH (task:CLITask {id: $task_id})
// MATCH (err:CLIErrorInstance)-[:CAUSED_ERROR]-(:CLIToolCall)-[:PART_OF_TASK]->(task)
```

### Profile Slow Queries
Use PROFILE to analyze query plans:

```cypher
PROFILE
MATCH (t:CLITask)-[:INVOLVES_CONCEPT]->(c:CLIConcept)
WHERE t.task_type = 'implement'
RETURN t, c
```

### Index Hints
Force index usage when the planner chooses poorly:

```cypher
MATCH (t:CLIToolCall)
USING INDEX t:CLIToolCall(tool_name)
WHERE t.tool_name = $tool_name
RETURN t
```
