# Claudius Neo4j Schema Reference

This document defines the complete Neo4j graph schema for the Claudius Claude Code hooks system, optimized for agent context gathering and capability discovery.

---

## Table of Contents

1. [Node Types](#node-types)
2. [Relationships](#relationships)
3. [Indexes](#indexes)
4. [Schema Diagram](#schema-diagram)

---

## Node Types

### Core Session Nodes (Existing)

#### ClaudeCodeSession
Represents a single Claude Code CLI session.

| Property | Type | Indexed | Description |
|----------|------|---------|-------------|
| `id` | STRING | Yes (unique) | `"cli_session:{session_id}"` |
| `session_id` | STRING | Yes | Unique session identifier |
| `start_time` | DATETIME | Yes | Session start timestamp |
| `end_time` | DATETIME | No | Session end timestamp (null if active) |
| `working_dir` | STRING | No | Initial working directory |
| `status` | STRING | Yes | `'active'` or `'completed'` |
| `tool_call_count` | INTEGER | No | Total tools executed |
| `prompt_count` | INTEGER | No | Total prompts submitted |
| `metadata` | STRING | No | JSON with platform/git/python info |
| `total_duration_seconds` | FLOAT | No | Total session duration |
| `project_path` | STRING | Yes | Normalized project root path |
| `primary_intent` | STRING | No | Overall session intent |
| `task_count` | INTEGER | No | Number of distinct tasks |
| `error_count` | INTEGER | No | Number of errors encountered |
| `resolution_rate` | FLOAT | No | Errors resolved / total errors |
| `git_branch` | STRING | No | Git branch at session start |
| `platform` | STRING | No | OS platform |

#### CLIToolCall
Represents a single tool invocation.

| Property | Type | Indexed | Description |
|----------|------|---------|-------------|
| `id` | STRING | Yes (unique) | `"cli_tool:{session_id}:{timestamp}:{tool_name}"` |
| `session_id` | STRING | Yes | Parent session ID |
| `tool_name` | STRING | Yes | Tool name (Read, Write, Bash, etc.) |
| `timestamp` | DATETIME | Yes | Execution timestamp |
| `inputs` | STRING | No | JSON of sanitized tool parameters (max 2000 chars) |
| `outputs` | STRING | No | Tool result (max 5000 chars) |
| `duration_ms` | INTEGER | No | Execution time in milliseconds |
| `success` | BOOLEAN | Yes | Whether tool succeeded |
| `error` | STRING | No | Error message if failed |
| `file_path` | STRING | Yes | Normalized file path (if applicable) |
| `sequence_index` | INTEGER | Yes | Order within session |
| `parent_task_id` | STRING | Yes | Associated CLITask ID |
| `triggered_by_prompt_id` | STRING | No | Prompt that triggered this tool |
| `context_type` | STRING | Yes | `'exploration'`, `'implementation'`, `'verification'` |
| `input_complexity` | STRING | No | `'simple'`, `'moderate'`, `'complex'` |
| `output_category` | STRING | No | `'success'`, `'partial'`, `'error'`, `'empty'` |
| `retry_of` | STRING | No | ID of failed tool call being retried |
| `retry_count` | INTEGER | No | Number of retry attempts |

#### CLIPrompt
Represents a user prompt submission.

| Property | Type | Indexed | Description |
|----------|------|---------|-------------|
| `id` | STRING | Yes (unique) | `"cli_prompt:{session_id}:{timestamp}"` |
| `session_id` | STRING | Yes | Parent session ID |
| `prompt_text` | STRING | No | First 1000 chars of prompt |
| `full_prompt_hash` | STRING | Yes | SHA256 hash for deduplication |
| `timestamp` | DATETIME | Yes | Submission timestamp |
| `prompt_length` | INTEGER | No | Full prompt character count |
| `sequence_index` | INTEGER | Yes | Order within session |
| `task_id` | STRING | Yes | Associated CLITask ID |
| `intent_type` | STRING | Yes | `'implement'`, `'debug'`, `'search'`, `'explain'`, `'refactor'` |
| `complexity` | STRING | No | `'simple'`, `'moderate'`, `'complex'` |
| `keywords` | LIST<STRING> | No | Extracted keywords |
| `entities` | LIST<STRING> | No | Extracted entities (files, functions) |
| `is_follow_up` | BOOLEAN | No | Continues previous prompt |
| `references_error` | BOOLEAN | No | References an error |

#### CLIMetrics
Aggregated session statistics.

| Property | Type | Indexed | Description |
|----------|------|---------|-------------|
| `id` | STRING | Yes (unique) | `"cli_metrics:{session_id}"` |
| `session_id` | STRING | Yes | Parent session ID |
| `tool_usage_summary` | STRING | No | JSON dict of tool counts |
| `most_used_tool` | STRING | No | Most frequently used tool |
| `avg_tool_duration_ms` | FLOAT | No | Average tool duration |
| `total_prompts` | INTEGER | No | Total prompts in session |
| `total_tools` | INTEGER | No | Total tool calls |
| `calculated_at` | DATETIME | No | When metrics were calculated |

---

### Task & Intent Nodes (New)

#### CLITask
Groups related prompts and tool calls into coherent user tasks.

| Property | Type | Indexed | Description |
|----------|------|---------|-------------|
| `id` | STRING | Yes (unique) | `"cli_task:{session_id}:{sequence}"` |
| `session_id` | STRING | Yes | Parent session ID |
| `task_type` | STRING | Yes | `'implement'`, `'debug'`, `'refactor'`, `'search'`, `'review'`, `'explain'` |
| `description` | STRING | No | LLM-generated summary (max 500 chars) |
| `keywords` | LIST<STRING> | No | Extracted keywords for similarity |
| `status` | STRING | Yes | `'active'`, `'completed'`, `'failed'`, `'abandoned'` |
| `started_at` | DATETIME | Yes | Task start timestamp |
| `completed_at` | DATETIME | No | Task completion timestamp |
| `prompt_count` | INTEGER | No | Prompts in this task |
| `tool_count` | INTEGER | No | Tools in this task |
| `success` | BOOLEAN | Yes | Whether task succeeded |
| `complexity_score` | FLOAT | No | 0-1 based on tool count, duration, retries |
| `created_at` | DATETIME | No | Node creation timestamp |

**Task Type Classification:**
- `implement` - Adding new functionality
- `debug` - Finding and fixing bugs
- `refactor` - Restructuring existing code
- `search` - Finding information in codebase
- `review` - Reviewing or explaining code
- `explain` - Understanding concepts or code

---

### Error & Solution Nodes (New)

#### CLIErrorInstance
Captures individual error occurrences with context.

| Property | Type | Indexed | Description |
|----------|------|---------|-------------|
| `id` | STRING | Yes (unique) | `"cli_error:{session_id}:{timestamp}"` |
| `session_id` | STRING | Yes | Parent session ID |
| `error_type` | STRING | Yes | `'syntax'`, `'runtime'`, `'permission'`, `'not_found'`, `'timeout'`, `'validation'` |
| `error_signature` | STRING | Yes | Normalized pattern for matching |
| `error_message` | STRING | No | Actual error (max 1000 chars) |
| `tool_name` | STRING | Yes | Tool that caused error |
| `file_path` | STRING | Yes | File involved (if applicable) |
| `context_summary` | STRING | No | What was being attempted |
| `resolved` | BOOLEAN | Yes | Whether error was resolved |
| `resolution_tool` | STRING | No | Tool that fixed it |
| `resolution_summary` | STRING | No | How it was fixed |
| `time_to_resolution_ms` | INTEGER | No | Time to resolve |
| `created_at` | DATETIME | Yes | Error occurrence timestamp |

**Error Type Classification:**
- `syntax` - Code syntax errors
- `runtime` - Runtime exceptions
- `permission` - Access denied errors
- `not_found` - File/resource not found
- `timeout` - Operation timeouts
- `validation` - Input validation failures

#### CLISolution
Captures successful resolution patterns.

| Property | Type | Indexed | Description |
|----------|------|---------|-------------|
| `id` | STRING | Yes (unique) | `"solution:{hash}"` |
| `solution_type` | STRING | Yes | `'code_fix'`, `'command'`, `'configuration'`, `'refactor'` |
| `problem_signature` | STRING | Yes | Normalized problem pattern |
| `solution_summary` | STRING | No | Description of the fix |
| `tool_sequence` | LIST<STRING> | No | Tools used in sequence |
| `success_count` | INTEGER | No | Times this solution worked |
| `failure_count` | INTEGER | No | Times this solution failed |
| `effectiveness_score` | FLOAT | Yes | success / (success + failure) |
| `avg_time_to_apply_ms` | FLOAT | No | Average application time |
| `last_used_at` | DATETIME | No | Last successful use |
| `created_at` | DATETIME | No | First discovered |

---

### Capability & Pattern Nodes (New)

#### CLIToolCapability
Models tool success patterns by context.

| Property | Type | Indexed | Description |
|----------|------|---------|-------------|
| `id` | STRING | Yes (unique) | `"capability:{tool_name}:{context_type}"` |
| `tool_name` | STRING | Yes | Tool name |
| `context_type` | STRING | Yes | `'file_read'`, `'file_write'`, `'search'`, `'edit'`, `'create'`, `'delete'`, `'git_op'`, `'web'` |
| `description` | STRING | No | What this capability does |
| `success_rate` | FLOAT | Yes | Historical success rate |
| `avg_duration_ms` | FLOAT | No | Average execution time |
| `total_uses` | INTEGER | No | Total invocations |
| `common_inputs` | STRING | No | JSON of typical input patterns |
| `common_errors` | LIST<STRING> | No | Frequent error types |
| `best_practices` | LIST<STRING> | No | Learned recommendations |
| `updated_at` | DATETIME | No | Last statistics update |

#### CLICodePattern
Stores reusable code/command patterns.

| Property | Type | Indexed | Description |
|----------|------|---------|-------------|
| `id` | STRING | Yes (unique) | `"pattern:{hash}"` |
| `pattern_type` | STRING | Yes | `'bash_command'`, `'cypher_query'`, `'code_snippet'`, `'file_template'` |
| `language` | STRING | Yes | `'bash'`, `'python'`, `'cypher'`, `'typescript'`, `'json'` |
| `pattern_text` | STRING | No | The actual pattern (max 2000 chars) |
| `description` | STRING | No | What this pattern does |
| `use_count` | INTEGER | No | Times pattern was used |
| `success_rate` | FLOAT | No | Success rate when used |
| `tags` | LIST<STRING> | No | Classification tags |
| `created_at` | DATETIME | No | First discovered |
| `last_used_at` | DATETIME | No | Last used |

---

### Context & Concept Nodes (New)

#### CLIConcept
Represents concepts, technologies, or domains.

| Property | Type | Indexed | Description |
|----------|------|---------|-------------|
| `id` | STRING | Yes (unique) | `"concept:{normalized_name}"` |
| `name` | STRING | Yes | e.g., "neo4j", "python-async", "git-workflow" |
| `category` | STRING | Yes | `'language'`, `'framework'`, `'tool'`, `'pattern'`, `'domain'` |
| `description` | STRING | No | Concept description |
| `occurrence_count` | INTEGER | No | Times encountered |
| `last_seen_at` | DATETIME | No | Last occurrence |
| `created_at` | DATETIME | No | First encountered |

#### CLIProjectContext
Captures project-level understanding.

| Property | Type | Indexed | Description |
|----------|------|---------|-------------|
| `id` | STRING | Yes (unique) | `"project:{path_hash}"` |
| `project_path` | STRING | Yes | Normalized project root |
| `project_name` | STRING | No | Project name |
| `project_type` | STRING | Yes | `'python'`, `'node'`, `'monorepo'`, `'documentation'` |
| `key_files` | LIST<STRING> | No | Important files discovered |
| `entry_points` | LIST<STRING> | No | Main scripts/entry points |
| `test_commands` | LIST<STRING> | No | How to run tests |
| `build_commands` | LIST<STRING> | No | How to build |
| `tech_stack` | LIST<STRING> | No | Technologies used |
| `conventions` | STRING | No | JSON of discovered conventions |
| `session_count` | INTEGER | No | Sessions in this project |
| `last_accessed_at` | DATETIME | No | Last session |
| `created_at` | DATETIME | No | First discovered |

---

## Relationships

### Session Relationships

| Relationship | From | To | Properties | Description |
|--------------|------|-----|------------|-------------|
| `PART_OF_SESSION` | CLIToolCall | ClaudeCodeSession | - | Tool belongs to session |
| `PART_OF_SESSION` | CLIPrompt | ClaudeCodeSession | - | Prompt belongs to session |
| `SUMMARIZES` | CLIMetrics | ClaudeCodeSession | - | Metrics summarize session |
| `IN_PROJECT` | ClaudeCodeSession | CLIProjectContext | - | Session is in project |

### Sequence Relationships

| Relationship | From | To | Properties | Description |
|--------------|------|-----|------------|-------------|
| `FOLLOWED_BY` | CLIToolCall | CLIToolCall | `gap_ms`, `same_file`, `same_task` | Tool temporal sequence |
| `NEXT_PROMPT` | CLIPrompt | CLIPrompt | `gap_ms`, `is_continuation`, `references_previous` | Prompt sequence |

### Causality Relationships

| Relationship | From | To | Properties | Description |
|--------------|------|-----|------------|-------------|
| `TRIGGERED` | CLIPrompt | CLIToolCall | `sequence_gap`, `confidence` | Prompt caused tool |
| `CAUSED_ERROR` | CLIToolCall | CLIErrorInstance | `error_position` | Tool caused error |

### Task Relationships

| Relationship | From | To | Properties | Description |
|--------------|------|-----|------------|-------------|
| `PART_OF_TASK` | CLIPrompt | CLITask | `sequence_index`, `role` | Prompt in task |
| `PART_OF_TASK` | CLIToolCall | CLITask | `sequence_index`, `role` | Tool in task |
| `SIMILAR_TASK` | CLITask | CLITask | `similarity_score`, `similarity_type`, `computed_at` | Similar tasks |

### Resolution Relationships

| Relationship | From | To | Properties | Description |
|--------------|------|-----|------------|-------------|
| `RESOLVED_BY` | CLIErrorInstance | CLISolution | `resolution_time_ms`, `confidence` | Error solved by |
| `RESOLVED_IN` | CLIErrorInstance | CLIToolCall | `steps_to_resolution` | Error fixed in tool |

### File Relationships

| Relationship | From | To | Properties | Description |
|--------------|------|-----|------------|-------------|
| `ACCESSED_FILE` | CLIToolCall | File | - | Tool accessed file |
| `USES_PATTERN` | CLIToolCall | CLICodePattern | `match_confidence` | Tool used pattern |

### Concept Relationships

| Relationship | From | To | Properties | Description |
|--------------|------|-----|------------|-------------|
| `INVOLVES_CONCEPT` | CLITask | CLIConcept | `relevance`, `mention_count` | Task involves concept |
| `RELATED_CONCEPT` | CLIConcept | CLIConcept | `co_occurrence_count`, `relationship_type` | Related concepts |
| `EFFECTIVE_FOR` | CLIToolCapability | CLIConcept | `effectiveness_score`, `sample_count` | Tool effective for concept |

---

## Indexes

### Unique Constraints

```cypher
CREATE CONSTRAINT cli_session_id IF NOT EXISTS FOR (s:ClaudeCodeSession) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT cli_toolcall_id IF NOT EXISTS FOR (t:CLIToolCall) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT cli_prompt_id IF NOT EXISTS FOR (p:CLIPrompt) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT cli_metrics_id IF NOT EXISTS FOR (m:CLIMetrics) REQUIRE m.id IS UNIQUE;
CREATE CONSTRAINT cli_task_id IF NOT EXISTS FOR (t:CLITask) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT cli_error_id IF NOT EXISTS FOR (e:CLIErrorInstance) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT cli_solution_id IF NOT EXISTS FOR (s:CLISolution) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT cli_capability_id IF NOT EXISTS FOR (c:CLIToolCapability) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT cli_pattern_id IF NOT EXISTS FOR (p:CLICodePattern) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT cli_concept_id IF NOT EXISTS FOR (c:CLIConcept) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT cli_project_id IF NOT EXISTS FOR (p:CLIProjectContext) REQUIRE p.id IS UNIQUE;
```

### Performance Indexes

```cypher
// Session indexes
CREATE INDEX cli_session_status IF NOT EXISTS FOR (s:ClaudeCodeSession) ON (s.status);
CREATE INDEX cli_session_start IF NOT EXISTS FOR (s:ClaudeCodeSession) ON (s.start_time);
CREATE INDEX cli_session_project IF NOT EXISTS FOR (s:ClaudeCodeSession) ON (s.project_path);

// Tool call indexes
CREATE INDEX cli_tool_session IF NOT EXISTS FOR (t:CLIToolCall) ON (t.session_id);
CREATE INDEX cli_tool_name IF NOT EXISTS FOR (t:CLIToolCall) ON (t.tool_name);
CREATE INDEX cli_tool_success IF NOT EXISTS FOR (t:CLIToolCall) ON (t.success);
CREATE INDEX cli_tool_file IF NOT EXISTS FOR (t:CLIToolCall) ON (t.file_path);
CREATE INDEX cli_tool_sequence IF NOT EXISTS FOR (t:CLIToolCall) ON (t.sequence_index);
CREATE INDEX cli_tool_context IF NOT EXISTS FOR (t:CLIToolCall) ON (t.context_type);
CREATE INDEX cli_tool_task IF NOT EXISTS FOR (t:CLIToolCall) ON (t.parent_task_id);

// Prompt indexes
CREATE INDEX cli_prompt_session IF NOT EXISTS FOR (p:CLIPrompt) ON (p.session_id);
CREATE INDEX cli_prompt_hash IF NOT EXISTS FOR (p:CLIPrompt) ON (p.full_prompt_hash);
CREATE INDEX cli_prompt_intent IF NOT EXISTS FOR (p:CLIPrompt) ON (p.intent_type);
CREATE INDEX cli_prompt_task IF NOT EXISTS FOR (p:CLIPrompt) ON (p.task_id);

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
CREATE INDEX cli_capability_success IF NOT EXISTS FOR (c:CLIToolCapability) ON (c.success_rate);

// Pattern indexes
CREATE INDEX cli_pattern_type IF NOT EXISTS FOR (p:CLICodePattern) ON (p.pattern_type);
CREATE INDEX cli_pattern_language IF NOT EXISTS FOR (p:CLICodePattern) ON (p.language);

// Concept indexes
CREATE INDEX cli_concept_name IF NOT EXISTS FOR (c:CLIConcept) ON (c.name);
CREATE INDEX cli_concept_category IF NOT EXISTS FOR (c:CLIConcept) ON (c.category);

// Project indexes
CREATE INDEX cli_project_path IF NOT EXISTS FOR (p:CLIProjectContext) ON (p.project_path);
CREATE INDEX cli_project_type IF NOT EXISTS FOR (p:CLIProjectContext) ON (p.project_type);
```

### Full-Text Search Indexes

```cypher
// For semantic search on text fields
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

## Schema Diagram

```
                                    ┌─────────────────────┐
                                    │  CLIProjectContext  │
                                    │  ───────────────    │
                                    │  project_path       │
                                    │  tech_stack         │
                                    │  key_files          │
                                    └─────────┬───────────┘
                                              │ IN_PROJECT
                                              ▼
┌─────────────┐  PART_OF_SESSION   ┌─────────────────────┐   SUMMARIZES   ┌─────────────┐
│  CLIPrompt  │ ─────────────────► │  ClaudeCodeSession  │ ◄───────────── │ CLIMetrics  │
│  ─────────  │                    │  ──────────────────  │                │ ──────────  │
│  prompt_text│                    │  session_id          │                │ tool_usage  │
│  intent_type│                    │  status              │                │ avg_duration│
└──────┬──────┘                    │  working_dir         │                └─────────────┘
       │                           └─────────┬────────────┘
       │ TRIGGERED                           │ PART_OF_SESSION
       │                                     ▼
       │                           ┌─────────────────────┐
       └─────────────────────────► │    CLIToolCall      │
                                   │    ───────────      │
┌─────────────┐  PART_OF_TASK      │    tool_name        │
│   CLITask   │ ◄────────────────  │    success          │
│   ────────  │                    │    file_path        │
│   task_type │                    └──────────┬──────────┘
│   status    │                               │
│   keywords  │                    ┌──────────┴──────────┐
└──────┬──────┘                    │                     │
       │                    FOLLOWED_BY           ACCESSED_FILE
       │ SIMILAR_TASK              │                     │
       ▼                           ▼                     ▼
┌─────────────┐            ┌─────────────┐       ┌─────────────┐
│   CLITask   │            │ CLIToolCall │       │    File     │
│   (other)   │            │   (next)    │       │   ────      │
└─────────────┘            └─────────────┘       │   path      │
                                                 └─────────────┘
                                   │
                            CAUSED_ERROR
                                   │
                                   ▼
┌─────────────────────┐    ┌─────────────────────┐
│    CLISolution      │◄───│   CLIErrorInstance  │
│    ────────────     │    │   ────────────────  │
│    solution_type    │    │   error_type        │
│    tool_sequence    │    │   error_signature   │
│    effectiveness    │    │   resolved          │
└─────────────────────┘    └─────────────────────┘
                                   RESOLVED_BY

┌─────────────────────┐    ┌─────────────────────┐
│  CLIToolCapability  │───►│     CLIConcept      │
│  ─────────────────  │    │     ──────────      │
│  tool_name          │    │     name            │
│  context_type       │    │     category        │
│  success_rate       │    │     occurrence_count│
└─────────────────────┘    └─────────────────────┘
       EFFECTIVE_FOR         INVOLVES_CONCEPT ▲
                                              │
                             ┌────────────────┘
                             │
                       ┌─────────────┐
                       │   CLITask   │
                       └─────────────┘

┌─────────────────────┐
│   CLICodePattern    │
│   ──────────────    │
│   pattern_type      │
│   language          │
│   pattern_text      │
│   success_rate      │
└─────────────────────┘
        ▲
        │ USES_PATTERN
        │
  ┌─────────────┐
  │ CLIToolCall │
  └─────────────┘
```

---

## Data Flow

```
User Prompt → CLIPrompt node
     │
     ├── Task Detection → CLITask node (groups related work)
     │
     └── Triggers → CLIToolCall nodes
                         │
                         ├── Success → CLIToolCapability updated
                         │              CLICodePattern extracted
                         │
                         └── Failure → CLIErrorInstance created
                                              │
                                              └── Resolution → CLISolution created/linked
```
