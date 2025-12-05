# Implementation Guide

This guide provides a sprint-by-sprint breakdown for implementing the enhanced Claudius schema. Each sprint builds on the previous one and includes specific files to modify, code changes, and testing strategies.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Sprint 1: Foundation](#sprint-1-foundation)
3. [Sprint 2: Task Abstraction](#sprint-2-task-abstraction)
4. [Sprint 3: Error Learning](#sprint-3-error-learning)
5. [Sprint 4: Capabilities & Patterns](#sprint-4-capabilities--patterns)
6. [Sprint 5: Context & Concepts](#sprint-5-context--concepts)
7. [Sprint 6: Similarity & Search](#sprint-6-similarity--search)
8. [Testing Strategies](#testing-strategies)

---

## Architecture Overview

### Current File Structure
```
.claude/hooks/
├── core/
│   ├── models.py       # Data models (dataclasses)
│   └── helpers.py      # Utility functions
├── sqlite/
│   ├── config.py       # SQLite configuration
│   └── writer.py       # SQLite write operations
├── graph/
│   ├── writer.py       # Neo4j write operations
│   └── sync.py         # SQLite → Neo4j sync
├── entrypoints/
│   ├── prompt_hooks.py
│   ├── session_hooks.py
│   └── tool_hooks.py
└── data/
    └── claude_hooks.db # SQLite database
```

### Data Flow
```
Hook Event → SQLite (immediate) → Neo4j (on session end via sync.py)
```

### Key Principle
- SQLite is the primary data store (fast, local)
- Neo4j is populated via sync for graph queries
- All new fields must be captured in both stores

---

## Sprint 1: Foundation

**Goal**: Add sequence tracking and enhanced properties to existing nodes.

### Files to Modify

#### 1. `.claude/hooks/core/models.py`

Add new fields to existing dataclasses:

```python
# Add to CLIToolCallEvent dataclass
@dataclass
class CLIToolCallEvent:
    session_id: str
    tool_name: str
    tool_input: dict
    timestamp: str
    call_id: str
    # NEW FIELDS
    sequence_index: int = 0
    context_type: str = "implementation"  # exploration, implementation, verification
    triggered_by_prompt_id: Optional[str] = None

# Add to CLIPromptEvent dataclass
@dataclass
class CLIPromptEvent:
    session_id: str
    prompt_text: str
    timestamp: str
    # NEW FIELDS
    sequence_index: int = 0
    intent_type: str = "implement"  # implement, debug, refactor, search, explain
    keywords: List[str] = field(default_factory=list)
```

#### 2. `.claude/hooks/core/helpers.py`

Add intent classification and keyword extraction:

```python
def classify_intent(prompt_text: str) -> str:
    """Classify prompt intent based on keywords."""
    text = prompt_text.lower()

    if any(kw in text for kw in ['fix', 'bug', 'error', 'broken', 'issue']):
        return 'debug'
    elif any(kw in text for kw in ['refactor', 'clean', 'reorganize', 'restructure']):
        return 'refactor'
    elif any(kw in text for kw in ['find', 'search', 'where', 'locate', 'which']):
        return 'search'
    elif any(kw in text for kw in ['explain', 'what', 'how does', 'why']):
        return 'explain'
    elif any(kw in text for kw in ['review', 'check', 'look at']):
        return 'review'
    else:
        return 'implement'

def classify_tool_context(tool_name: str, tool_input: dict) -> str:
    """Classify tool call context type."""
    if tool_name in ['Read', 'Glob', 'Grep']:
        return 'exploration'
    elif tool_name in ['Write', 'Edit', 'MultiEdit', 'NotebookEdit']:
        return 'implementation'
    elif tool_name == 'Bash':
        cmd = tool_input.get('command', '').lower()
        if any(kw in cmd for kw in ['test', 'pytest', 'jest', 'npm test']):
            return 'verification'
        if any(kw in cmd for kw in ['build', 'compile', 'npm run']):
            return 'verification'
    return 'implementation'

def extract_keywords(text: str) -> List[str]:
    """Extract meaningful keywords from text."""
    import re
    # Remove common stop words, keep meaningful terms
    stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                  'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                  'would', 'could', 'should', 'may', 'might', 'can', 'to', 'of',
                  'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
                  'through', 'during', 'before', 'after', 'above', 'below',
                  'between', 'under', 'again', 'further', 'then', 'once', 'here',
                  'there', 'when', 'where', 'why', 'how', 'all', 'each', 'few',
                  'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
                  'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just',
                  'and', 'but', 'if', 'or', 'because', 'until', 'while', 'this',
                  'that', 'these', 'those', 'am', 'it', 'its', 'i', 'me', 'my',
                  'you', 'your', 'he', 'him', 'his', 'she', 'her', 'we', 'they',
                  'them', 'what', 'which', 'who', 'whom', 'please', 'help'}

    # Extract words, filter stop words, keep unique
    words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', text.lower())
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    return list(dict.fromkeys(keywords))[:20]  # Dedupe, limit to 20
```

#### 3. `.claude/hooks/sqlite/writer.py`

Add new columns to SQLite schema:

```python
# Add to schema creation (version 5)
SCHEMA_VERSION = 5

# Add to CREATE TABLE events:
#   sequence_index INTEGER,
#   context_type TEXT,
#   intent_type TEXT,
#   keywords TEXT,  -- JSON array
#   triggered_by_prompt_id TEXT,

# Add migration for existing data:
def migrate_v4_to_v5(conn):
    """Add sequence tracking columns."""
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE events ADD COLUMN sequence_index INTEGER")
    cursor.execute("ALTER TABLE events ADD COLUMN context_type TEXT")
    cursor.execute("ALTER TABLE events ADD COLUMN intent_type TEXT")
    cursor.execute("ALTER TABLE events ADD COLUMN keywords TEXT")
    cursor.execute("ALTER TABLE events ADD COLUMN triggered_by_prompt_id TEXT")
    conn.commit()
```

#### 4. `.claude/hooks/graph/writer.py`

Add sequence properties to Neo4j writes:

```python
def create_tool_call(self, event: CLIToolResultEvent) -> None:
    """Create CLIToolCall node with enhanced properties."""
    query = """
    MERGE (t:CLIToolCall {id: $id})
    SET t.session_id = $session_id,
        t.tool_name = $tool_name,
        t.timestamp = datetime($timestamp),
        t.inputs = $inputs,
        t.outputs = $outputs,
        t.duration_ms = $duration_ms,
        t.success = $success,
        t.error = $error,
        t.file_path = $file_path,
        t.sequence_index = $sequence_index,
        t.context_type = $context_type

    WITH t
    MATCH (s:ClaudeCodeSession {session_id: $session_id})
    MERGE (t)-[:PART_OF_SESSION]->(s)
    """
    # ... execute query with new parameters
```

#### 5. `.claude/hooks/graph/sync.py`

Add FOLLOWED_BY relationship creation:

```python
def create_sequence_relationships(self, session_id: str) -> None:
    """Create FOLLOWED_BY relationships between sequential tools."""
    query = """
    MATCH (s:ClaudeCodeSession {session_id: $session_id})
    MATCH (t1:CLIToolCall)-[:PART_OF_SESSION]->(s)
    MATCH (t2:CLIToolCall)-[:PART_OF_SESSION]->(s)
    WHERE t1.sequence_index = t2.sequence_index - 1
    MERGE (t1)-[:FOLLOWED_BY {
        gap_ms: duration.between(t1.timestamp, t2.timestamp).milliseconds,
        same_file: t1.file_path = t2.file_path
    }]->(t2)
    """
    self._execute(query, {'session_id': session_id})
```

### Testing Sprint 1

```bash
# Test intent classification
python -c "
from .claude.hooks.core.helpers import classify_intent
assert classify_intent('fix the bug in login') == 'debug'
assert classify_intent('add new feature') == 'implement'
assert classify_intent('find the config file') == 'search'
print('Intent classification tests passed')
"

# Test keyword extraction
python -c "
from .claude.hooks.core.helpers import extract_keywords
kws = extract_keywords('implement user authentication with OAuth')
assert 'implement' in kws
assert 'authentication' in kws
print('Keyword extraction tests passed')
"

# Test hook with new fields
echo '{"sessionId": "test-123", "prompt": "fix the login bug"}' | python .claude/hooks/entrypoints/prompt_hooks.py
```

---

## Sprint 2: Task Abstraction

**Goal**: Implement CLITask nodes and task detection.

### Files to Modify

#### 1. `.claude/hooks/core/models.py`

Add CLITask dataclass:

```python
@dataclass
class CLITaskEvent:
    """Represents a coherent user task (group of related prompts/tools)."""
    id: str
    session_id: str
    task_type: str  # implement, debug, refactor, search, review, explain
    description: str = ""
    keywords: List[str] = field(default_factory=list)
    status: str = "active"  # active, completed, failed, abandoned
    started_at: str = ""
    completed_at: Optional[str] = None
    prompt_count: int = 0
    tool_count: int = 0
    success: bool = True
    complexity_score: float = 0.0
```

#### 2. `.claude/hooks/core/helpers.py`

Add task detection logic:

```python
# Task detection thresholds
TASK_GAP_THRESHOLD_MS = 300000  # 5 minutes between prompts = new task
TASK_TOPIC_SHIFT_THRESHOLD = 0.3  # Keyword overlap below this = new task

def should_start_new_task(
    current_prompt: CLIPromptEvent,
    last_prompt: Optional[CLIPromptEvent],
    last_task: Optional[CLITaskEvent]
) -> bool:
    """Determine if a new task should be started."""
    if last_prompt is None or last_task is None:
        return True

    # Time-based detection
    current_time = datetime.fromisoformat(current_prompt.timestamp)
    last_time = datetime.fromisoformat(last_prompt.timestamp)
    gap_ms = (current_time - last_time).total_seconds() * 1000

    if gap_ms > TASK_GAP_THRESHOLD_MS:
        return True

    # Intent shift detection
    if current_prompt.intent_type != last_prompt.intent_type:
        # Major intent shift (e.g., implement -> debug)
        return True

    # Keyword overlap detection
    if last_task.keywords and current_prompt.keywords:
        overlap = len(set(last_task.keywords) & set(current_prompt.keywords))
        max_keywords = max(len(last_task.keywords), len(current_prompt.keywords))
        if overlap / max_keywords < TASK_TOPIC_SHIFT_THRESHOLD:
            return True

    return False

def generate_task_description(prompts: List[CLIPromptEvent]) -> str:
    """Generate a summary description from task prompts."""
    if not prompts:
        return ""
    # Use first prompt as base, truncate to 500 chars
    first_prompt = prompts[0].prompt_text[:500]
    return first_prompt

def calculate_complexity_score(
    tool_count: int,
    duration_ms: int,
    error_count: int
) -> float:
    """Calculate task complexity score (0-1)."""
    # Normalize each factor
    tool_factor = min(tool_count / 50, 1.0) * 0.4
    duration_factor = min(duration_ms / 1800000, 1.0) * 0.4  # 30 min max
    error_factor = min(error_count / 10, 1.0) * 0.2
    return tool_factor + duration_factor + error_factor
```

#### 3. `.claude/hooks/sqlite/writer.py`

Add tasks table:

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    task_type TEXT,
    description TEXT,
    keywords TEXT,  -- JSON array
    status TEXT DEFAULT 'active',
    started_at TEXT,
    completed_at TEXT,
    prompt_count INTEGER DEFAULT 0,
    tool_count INTEGER DEFAULT 0,
    success INTEGER DEFAULT 1,
    complexity_score REAL DEFAULT 0.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE INDEX idx_tasks_session ON tasks(session_id);
CREATE INDEX idx_tasks_type ON tasks(task_type);
CREATE INDEX idx_tasks_status ON tasks(status);
```

#### 4. `.claude/hooks/graph/writer.py`

Add CLITask node creation:

```python
def create_task(self, task: CLITaskEvent) -> None:
    """Create CLITask node."""
    query = """
    MERGE (t:CLITask {id: $id})
    SET t.session_id = $session_id,
        t.task_type = $task_type,
        t.description = $description,
        t.keywords = $keywords,
        t.status = $status,
        t.started_at = datetime($started_at),
        t.completed_at = CASE WHEN $completed_at IS NOT NULL
                              THEN datetime($completed_at) ELSE null END,
        t.prompt_count = $prompt_count,
        t.tool_count = $tool_count,
        t.success = $success,
        t.complexity_score = $complexity_score

    WITH t
    MATCH (s:ClaudeCodeSession {session_id: $session_id})
    MERGE (t)-[:PART_OF_SESSION]->(s)
    """
    self._execute(query, asdict(task))

def link_prompt_to_task(self, prompt_id: str, task_id: str, sequence_index: int) -> None:
    """Link prompt to task."""
    query = """
    MATCH (p:CLIPrompt {id: $prompt_id})
    MATCH (t:CLITask {id: $task_id})
    MERGE (p)-[:PART_OF_TASK {sequence_index: $sequence_index}]->(t)
    """
    self._execute(query, {
        'prompt_id': prompt_id,
        'task_id': task_id,
        'sequence_index': sequence_index
    })
```

#### 5. `.claude/hooks/entrypoints/prompt_hooks.py`

Add task detection on prompt submission:

```python
def handle_prompt(event_data: dict) -> None:
    """Handle UserPromptSubmit event with task detection."""
    session_id = event_data.get('sessionId')
    prompt_text = event_data.get('prompt', '')

    # Get last prompt and current task from cache
    last_prompt = get_cached_last_prompt(session_id)
    current_task = get_cached_current_task(session_id)

    # Create prompt event with new fields
    prompt = CLIPromptEvent(
        session_id=session_id,
        prompt_text=prompt_text[:1000],
        timestamp=datetime.utcnow().isoformat(),
        sequence_index=get_next_prompt_index(session_id),
        intent_type=classify_intent(prompt_text),
        keywords=extract_keywords(prompt_text)
    )

    # Check if new task should start
    if should_start_new_task(prompt, last_prompt, current_task):
        # Complete previous task if exists
        if current_task:
            complete_task(current_task)

        # Start new task
        new_task = CLITaskEvent(
            id=f"cli_task:{session_id}:{get_next_task_index(session_id)}",
            session_id=session_id,
            task_type=prompt.intent_type,
            started_at=prompt.timestamp,
            keywords=prompt.keywords
        )
        save_task(new_task)
        cache_current_task(session_id, new_task)

    # Link prompt to current task
    prompt.task_id = get_current_task_id(session_id)
    save_prompt(prompt)
    cache_last_prompt(session_id, prompt)
```

### Testing Sprint 2

```bash
# Test task detection
python -c "
from .claude.hooks.core.helpers import should_start_new_task
from .claude.hooks.core.models import CLIPromptEvent, CLITaskEvent

p1 = CLIPromptEvent(session_id='test', prompt_text='fix bug', timestamp='2024-01-01T10:00:00', intent_type='debug')
p2 = CLIPromptEvent(session_id='test', prompt_text='fix same bug', timestamp='2024-01-01T10:01:00', intent_type='debug')
task = CLITaskEvent(id='t1', session_id='test', task_type='debug', keywords=['fix', 'bug'])

# Same task (close in time, same intent)
assert not should_start_new_task(p2, p1, task)

# New task (large time gap)
p3 = CLIPromptEvent(session_id='test', prompt_text='add feature', timestamp='2024-01-01T10:10:00', intent_type='implement')
assert should_start_new_task(p3, p1, task)
print('Task detection tests passed')
"
```

---

## Sprint 3: Error Learning

**Goal**: Implement CLIErrorInstance and CLISolution nodes.

### Files to Modify

#### 1. `.claude/hooks/core/models.py`

```python
@dataclass
class CLIErrorInstance:
    """Represents an error occurrence."""
    id: str
    session_id: str
    error_type: str  # syntax, runtime, permission, not_found, timeout, validation
    error_signature: str  # Normalized pattern for matching
    error_message: str
    tool_name: str
    file_path: Optional[str] = None
    context_summary: str = ""
    resolved: bool = False
    resolution_tool: Optional[str] = None
    resolution_summary: str = ""
    time_to_resolution_ms: Optional[int] = None
    created_at: str = ""

@dataclass
class CLISolution:
    """Represents a successful resolution pattern."""
    id: str
    solution_type: str  # code_fix, command, configuration, refactor
    problem_signature: str
    solution_summary: str
    tool_sequence: List[str] = field(default_factory=list)
    success_count: int = 1
    failure_count: int = 0
    effectiveness_score: float = 1.0
    avg_time_to_apply_ms: float = 0.0
    last_used_at: str = ""
    created_at: str = ""
```

#### 2. `.claude/hooks/core/helpers.py`

```python
def classify_error_type(error_message: str) -> str:
    """Classify error type from message."""
    msg = error_message.lower()

    if 'permission denied' in msg or 'access denied' in msg:
        return 'permission'
    elif 'not found' in msg or 'no such file' in msg or 'does not exist' in msg:
        return 'not_found'
    elif 'timeout' in msg or 'timed out' in msg:
        return 'timeout'
    elif 'syntax' in msg or 'parse error' in msg:
        return 'syntax'
    elif 'validation' in msg or 'invalid' in msg:
        return 'validation'
    else:
        return 'runtime'

def normalize_error_signature(error_message: str, tool_name: str) -> str:
    """Create normalized signature for error matching."""
    import re

    # Remove specific file paths, line numbers, timestamps
    normalized = error_message.lower()
    normalized = re.sub(r'/[\w/.-]+', '<path>', normalized)
    normalized = re.sub(r'line \d+', 'line <n>', normalized)
    normalized = re.sub(r'\d{4}-\d{2}-\d{2}', '<date>', normalized)
    normalized = re.sub(r'\d+:\d+:\d+', '<time>', normalized)

    # Prefix with tool name for context
    return f"{tool_name}:{normalized[:100]}"

def generate_solution_id(problem_signature: str, tool_sequence: List[str]) -> str:
    """Generate unique solution ID."""
    import hashlib
    content = f"{problem_signature}:{','.join(tool_sequence)}"
    return f"solution:{hashlib.md5(content.encode()).hexdigest()[:12]}"
```

#### 3. `.claude/hooks/entrypoints/tool_hooks.py`

```python
def handle_post_tool(event_data: dict) -> None:
    """Handle PostToolUse with error detection."""
    # ... existing code ...

    # Error detection
    if not success:
        error_instance = CLIErrorInstance(
            id=f"cli_error:{session_id}:{timestamp}",
            session_id=session_id,
            error_type=classify_error_type(error_message),
            error_signature=normalize_error_signature(error_message, tool_name),
            error_message=error_message[:1000],
            tool_name=tool_name,
            file_path=file_path,
            context_summary=f"Running {tool_name} on {file_path or 'unknown'}",
            created_at=timestamp
        )
        save_error(error_instance)
        cache_pending_error(session_id, error_instance)

    # Resolution detection (check if we resolved a pending error)
    pending_error = get_cached_pending_error(session_id)
    if pending_error and success and pending_error.file_path == file_path:
        # This successful tool call likely resolved the error
        mark_error_resolved(
            error_id=pending_error.id,
            resolution_tool=tool_name,
            time_to_resolution_ms=calculate_time_diff(pending_error.created_at, timestamp)
        )

        # Create or update solution
        solution = find_or_create_solution(pending_error, tool_name)
        link_error_to_solution(pending_error.id, solution.id)
        clear_cached_pending_error(session_id)
```

### Testing Sprint 3

```bash
# Test error classification
python -c "
from .claude.hooks.core.helpers import classify_error_type, normalize_error_signature

assert classify_error_type('Permission denied: /etc/passwd') == 'permission'
assert classify_error_type('File not found: config.json') == 'not_found'
assert classify_error_type('SyntaxError: unexpected token') == 'syntax'

sig = normalize_error_signature('Error in /home/user/project/file.py line 42', 'Read')
assert '<path>' in sig
assert 'line <n>' in sig
print('Error classification tests passed')
"
```

---

## Sprint 4: Capabilities & Patterns

**Goal**: Implement CLIToolCapability and CLICodePattern nodes.

### Key Implementation Points

1. **CLIToolCapability**: Aggregated from historical tool usage
   - Run background job after session sync
   - Group by tool_name + context_type
   - Calculate success_rate, avg_duration_ms

2. **CLICodePattern**: Extract from successful Bash commands
   - Normalize commands (remove specific paths)
   - Track usage frequency and success rate

### Files to Modify
- `.claude/hooks/core/models.py` - Add dataclasses
- `.claude/hooks/graph/writer.py` - Add node creation methods
- `.claude/hooks/graph/sync.py` - Add capability aggregation

---

## Sprint 5: Context & Concepts

**Goal**: Implement CLIConcept and CLIProjectContext nodes.

### Key Implementation Points

1. **CLIConcept**: Extracted from prompts and tool inputs
   - Use keyword extraction + known technology list
   - Track co-occurrence for RELATED_CONCEPT

2. **CLIProjectContext**: Detect from working directory
   - Identify project type (package.json → node, setup.py → python)
   - Extract key files, test commands, build commands

### Files to Modify
- `.claude/hooks/core/models.py` - Add dataclasses
- `.claude/hooks/core/helpers.py` - Add project detection
- `.claude/hooks/entrypoints/session_hooks.py` - Create on session start

---

## Sprint 6: Similarity & Search

**Goal**: Implement task similarity and semantic search.

### Key Implementation Points

1. **Keyword-based SIMILAR_TASK**:
   - Calculate Jaccard similarity on keywords
   - Create relationship if similarity > 0.3

2. **Embedding-based similarity** (optional):
   - Integrate embedding model (e.g., sentence-transformers)
   - Store embeddings as node properties
   - Use vector similarity for deep matching

### Files to Modify
- `.claude/hooks/graph/sync.py` - Add similarity calculation
- `.claude/hooks/core/helpers.py` - Add embedding generation (optional)

---

## Testing Strategies

### Unit Tests

```python
# tests/test_helpers.py
import pytest
from .claude.hooks.core.helpers import (
    classify_intent, classify_tool_context, extract_keywords,
    should_start_new_task, classify_error_type
)

class TestIntentClassification:
    def test_debug_intent(self):
        assert classify_intent("fix the bug") == "debug"
        assert classify_intent("there's an error") == "debug"

    def test_implement_intent(self):
        assert classify_intent("add new feature") == "implement"
        assert classify_intent("create a function") == "implement"

class TestKeywordExtraction:
    def test_extracts_meaningful_words(self):
        kws = extract_keywords("implement OAuth authentication")
        assert "oauth" in kws
        assert "authentication" in kws
        assert "the" not in kws  # stop word
```

### Integration Tests

```python
# tests/test_hooks.py
import json
import subprocess

def test_prompt_hook_creates_task():
    """Test that prompt hook creates task on first prompt."""
    event = {
        "sessionId": "test-session-123",
        "prompt": "implement user login"
    }

    result = subprocess.run(
        ["python", ".claude/hooks/entrypoints/prompt_hooks.py"],
        input=json.dumps(event),
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    # Verify task was created in SQLite
    # ...
```

### Neo4j Verification

```cypher
// Verify schema after migration
// Run these queries and check expected counts

// Check all node types exist
CALL db.labels() YIELD label
WHERE label STARTS WITH 'CLI'
RETURN label, count(*) as count;

// Check all relationship types exist
CALL db.relationshipTypes() YIELD relationshipType
WHERE relationshipType IN ['PART_OF_TASK', 'FOLLOWED_BY', 'RESOLVED_BY', 'CAUSED_ERROR']
RETURN relationshipType;

// Verify data integrity
MATCH (t:CLIToolCall)
WHERE t.sequence_index IS NULL
RETURN count(t) as missing_sequence;  // Should be 0
```

### Performance Benchmarks

```python
# tests/test_performance.py
import time

def test_query_performance():
    """Ensure key queries complete within acceptable time."""

    # Find similar tasks query
    start = time.time()
    # ... run query ...
    duration = time.time() - start

    assert duration < 0.5, f"Similar tasks query too slow: {duration}s"
```
