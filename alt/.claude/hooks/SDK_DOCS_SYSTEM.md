# Agent SDK Documentation Graph System

## Overview

This system stores Claude Agent SDK documentation (TypeScript and Python) as a Neo4j knowledge graph, enabling semantic queries about SDK types, functions, tools, and their relationships.

## Quick Reference

### Files

| File | Purpose |
|------|---------|
| `sdk_docs_writer.py` | Neo4j writer class for SDK documentation nodes |
| `sdk_docs_models.py` | Data models (informational, not required at runtime) |
| `populate_sdk_docs.py` | Populates TypeScript SDK documentation |
| `populate_python_sdk_docs.py` | Populates Python SDK documentation |

### Node Labels

| Label | Description | Key Properties |
|-------|-------------|----------------|
| `SDKFunction` | SDK functions (query, tool, etc.) | `name`, `sdk`, `signature`, `parameters`, `returns` |
| `SDKType` | Types/interfaces | `name`, `sdk`, `category`, `definition`, `properties` |
| `SDKClass` | Python classes | `name`, `sdk`, `definition`, `methods` |
| `SDKTool` | Built-in tools (Bash, Read, etc.) | `name`, `sdk`, `input_schema`, `output_description` |
| `SDKMessage` | Message types | `name`, `sdk`, `message_type`, `definition` |
| `SDKHookEvent` | Hook events | `name`, `sdk`, `input_type_name`, `input_fields` |
| `SDKConfig` | Config types (MCP, sandbox) | `name`, `sdk`, `config_type`, `definition` |
| `SDKError` | Exception classes | `name`, `sdk`, `parent_class`, `definition` |
| `SDKEnumValue` | Enum/union values | `parent_type`, `value`, `sdk` |

### Relationships

| Relationship | From | To | Meaning |
|--------------|------|-----|---------|
| `RETURNS` | SDKFunction | SDKType | Function returns this type |
| `ACCEPTS` | SDKFunction | SDKType | Function accepts this type |
| `REFERENCES` | SDKType | SDKType | Type references another type |
| `EXTENDS` | SDKType | SDKType | Type extends another type |
| `INCLUDES` | SDKType | SDKType | Union includes member type |
| `MEMBER_OF` | SDKMessage | SDKType | Message belongs to union |
| `VALUE_OF` | SDKEnumValue | SDKType | Enum value belongs to type |

### SDK Identifiers

All nodes have an `sdk` property:
- `"typescript"` - TypeScript SDK (`@anthropic-ai/claude-agent-sdk`)
- `"python"` - Python SDK (`claude-agent-sdk`)

---

## Schema Details

### SDKFunction

Represents SDK functions like `query()`, `tool()`, `create_sdk_mcp_server()`.

```python
# Node properties
{
    "id": "sdk_function:{sdk}:{name}",
    "name": str,           # Function name
    "description": str,    # What the function does
    "signature": str,      # Full function signature
    "parameters": str,     # JSON array of parameter dicts
    "returns": str,        # Return type description
    "example_code": str,   # Optional example
    "sdk": str,            # "typescript" or "python"
    "package": str         # Package name
}
```

**Parameters JSON structure:**
```json
[
    {"name": "prompt", "type": "string", "description": "...", "required": true},
    {"name": "options", "type": "Options", "description": "...", "required": false}
]
```

### SDKType

Represents types, interfaces, type aliases, and dataclasses.

```python
{
    "id": "sdk_type:{sdk}:{name}",
    "name": str,           # Type name
    "description": str,    # What the type represents
    "definition": str,     # Full type definition code
    "category": str,       # One of: options, query, message, hook, permission,
                           #         tool_input, tool_output, mcp, sandbox, other
    "properties": str,     # JSON array of property dicts
    "sdk": str,
    "package": str
}
```

**Properties JSON structure:**
```json
[
    {"name": "model", "type": "string", "default": "null", "description": "..."},
    {"name": "maxTurns", "type": "number", "required": false}
]
```

### SDKClass (Python only)

Represents Python classes like `ClaudeSDKClient`.

```python
{
    "id": "sdk_class:{sdk}:{name}",
    "name": str,
    "description": str,
    "definition": str,     # Class definition with method signatures
    "methods": str,        # JSON array of method dicts
    "properties": str,     # JSON array of property dicts
    "sdk": str,
    "package": str
}
```

**Methods JSON structure:**
```json
[
    {"name": "connect", "description": "Connect to Claude"},
    {"name": "query", "description": "Send a query"},
    {"name": "interrupt", "description": "Interrupt current operation"}
]
```

### SDKTool

Represents built-in Claude Code tools.

```python
{
    "id": "sdk_tool:{sdk}:{name}",
    "name": str,              # Tool name (Bash, Read, Write, etc.)
    "description": str,
    "input_schema": str,      # JSON array of input properties
    "output_schema": str,     # JSON array of output properties
    "output_description": str,
    "sdk": str,
    "package": str
}
```

**Input schema JSON structure:**
```json
[
    {"name": "command", "type": "string", "required": true, "description": "..."},
    {"name": "timeout", "type": "number", "required": false}
]
```

### SDKMessage

Represents message types returned by SDK queries.

```python
{
    "id": "sdk_message:{sdk}:{name}",
    "name": str,           # e.g., "AssistantMessage", "ResultMessage"
    "description": str,
    "message_type": str,   # "assistant", "user", "system", "result", "stream"
    "definition": str,     # Full type definition
    "sdk": str,
    "package": str
}
```

### SDKHookEvent

Represents hook event types.

```python
{
    "id": "sdk_hook_event:{sdk}:{name}",
    "name": str,              # e.g., "PreToolUse", "PostToolUse"
    "description": str,
    "input_type_name": str,   # Name of input type
    "input_fields": str,      # JSON array of input fields
    "sdk": str,
    "package": str
}
```

### SDKConfig

Represents configuration types (MCP, sandbox, etc.).

```python
{
    "id": "sdk_config:{sdk}:{name}",
    "name": str,
    "description": str,
    "config_type": str,    # "mcp", "sandbox", "permission"
    "definition": str,
    "properties": str,     # JSON
    "sdk": str,
    "package": str
}
```

### SDKError (Python only)

Represents exception classes.

```python
{
    "id": "sdk_error:{sdk}:{name}",
    "name": str,
    "description": str,
    "definition": str,
    "parent_class": str,   # Parent exception class name
    "sdk": str,
    "package": str
}
```

### SDKEnumValue

Represents values in union types or enums.

```python
{
    "id": "sdk_enum:{sdk}:{parent_type}:{value}",
    "parent_type": str,    # Parent type name
    "value": str,          # The enum/union value
    "description": str,
    "sdk": str
}
```

---

## Common Queries

### Find SDK Components

```cypher
// All functions for a specific SDK
MATCH (f:SDKFunction {sdk: 'python'})
RETURN f.name, f.signature, f.description

// All types in a category
MATCH (t:SDKType {sdk: 'typescript', category: 'options'})
RETURN t.name, t.definition

// All built-in tools
MATCH (t:SDKTool {sdk: 'python'})
RETURN t.name, t.description, t.input_schema

// All message types
MATCH (m:SDKMessage {sdk: 'typescript'})
RETURN m.name, m.message_type, m.definition

// All hook events
MATCH (h:SDKHookEvent {sdk: 'python'})
RETURN h.name, h.input_fields

// Python classes
MATCH (c:SDKClass)
RETURN c.name, c.methods

// Python exceptions
MATCH (e:SDKError)
RETURN e.name, e.parent_class, e.description
```

### Find Relationships

```cypher
// What does query() return?
MATCH (f:SDKFunction {name: 'query'})-[:RETURNS]->(t)
RETURN f.sdk, t.name, t.description

// What types does Options reference?
MATCH (o:SDKType {name: 'Options'})-[:REFERENCES]->(t)
RETURN t.name, t.category

// What messages are in the Message union?
MATCH (m:SDKMessage)-[:MEMBER_OF]->(u:SDKType {name: 'Message'})
RETURN m.name, m.message_type

// What values does PermissionMode have?
MATCH (e:SDKEnumValue)-[:VALUE_OF]->(t:SDKType {name: 'PermissionMode'})
RETURN e.value, e.description
```

### Cross-SDK Comparison

```cypher
// Find equivalent types between SDKs
MATCH (ts:SDKType {sdk: 'typescript'})
MATCH (py:SDKType {sdk: 'python'})
WHERE ts.name = py.name OR
      (ts.name = 'Options' AND py.name = 'ClaudeAgentOptions')
RETURN ts.name AS typescript, py.name AS python, ts.category

// Compare tools between SDKs
MATCH (ts:SDKTool {sdk: 'typescript'})
MATCH (py:SDKTool {sdk: 'python'})
WHERE ts.name = py.name
RETURN ts.name, ts.input_schema AS ts_schema, py.input_schema AS py_schema

// Find Python-only features
MATCH (c:SDKClass {sdk: 'python'})
RETURN c.name, c.description

// Find Python exception types
MATCH (e:SDKError {sdk: 'python'})
RETURN e.name, e.parent_class
```

### Search by Description

```cypher
// Find types related to permissions
MATCH (t:SDKType)
WHERE t.name CONTAINS 'Permission' OR t.description CONTAINS 'permission'
RETURN t.name, t.sdk, t.category

// Find tools that work with files
MATCH (t:SDKTool)
WHERE t.description CONTAINS 'file' OR t.name IN ['Read', 'Write', 'Edit']
RETURN t.name, t.sdk, t.description
```

---

## Writer API Reference

### SDKDocsNeo4jWriter

Context manager for writing SDK documentation to Neo4j.

```python
from sdk_docs_writer import SDKDocsNeo4jWriter

with SDKDocsNeo4jWriter() as writer:
    # Create nodes and relationships
    pass
```

### Methods

#### `create_sdk_function(name, description, signature, parameters=None, returns=None, example_code=None, sdk="typescript", package="@anthropic-ai/claude-agent-sdk")`

Creates an SDKFunction node.

```python
writer.create_sdk_function(
    name="query",
    description="Execute a query against Claude",
    signature="async def query(prompt, options=None) -> AsyncIterator[Message]",
    parameters=[
        {"name": "prompt", "type": "str", "description": "The prompt"},
        {"name": "options", "type": "ClaudeAgentOptions", "required": False}
    ],
    returns="AsyncIterator[Message]",
    sdk="python",
    package="claude-agent-sdk"
)
```

#### `create_sdk_type(name, description, definition, category, properties=None, sdk="typescript", package="...")`

Creates an SDKType node.

```python
writer.create_sdk_type(
    name="PermissionMode",
    description="Permission modes for tool execution",
    definition='PermissionMode = Literal["default", "acceptEdits", "plan", "bypassPermissions"]',
    category="permission",
    properties=[
        {"name": '"default"', "description": "Standard behavior"},
        {"name": '"acceptEdits"', "description": "Auto-accept edits"}
    ],
    sdk="python"
)
```

#### `create_sdk_class(name, description, definition, methods=None, properties=None, sdk="python", package="claude-agent-sdk")`

Creates an SDKClass node (Python SDK).

```python
writer.create_sdk_class(
    name="ClaudeSDKClient",
    description="Client for continuous conversations",
    definition="class ClaudeSDKClient: ...",
    methods=[
        {"name": "connect", "description": "Connect to Claude"},
        {"name": "query", "description": "Send a query"}
    ]
)
```

#### `create_sdk_tool(tool_name, description, input_schema, output_schema=None, output_description=None, sdk="typescript", package="...")`

Creates an SDKTool node.

```python
writer.create_sdk_tool(
    tool_name="Bash",
    description="Execute bash commands",
    input_schema=[
        {"name": "command", "type": "str", "required": True},
        {"name": "timeout", "type": "int", "required": False}
    ],
    output_description="Returns command output with exit code",
    sdk="python"
)
```

#### `create_sdk_message(name, description, message_type, definition, sdk="typescript", package="...")`

Creates an SDKMessage node.

```python
writer.create_sdk_message(
    name="ResultMessage",
    description="Final result message",
    message_type="result",
    definition="@dataclass\nclass ResultMessage: ...",
    sdk="python"
)
```

#### `create_sdk_hook_event(name, description, input_type_name, input_fields, sdk="typescript", package="...")`

Creates an SDKHookEvent node.

```python
writer.create_sdk_hook_event(
    name="PreToolUse",
    description="Called before tool execution",
    input_type_name="PreToolUseHookInput",
    input_fields=[
        {"name": "tool_name", "type": "str"},
        {"name": "tool_input", "type": "dict"}
    ],
    sdk="python"
)
```

#### `create_sdk_config(name, description, config_type, definition, properties=None, sdk="typescript", package="...")`

Creates an SDKConfig node.

```python
writer.create_sdk_config(
    name="SandboxSettings",
    description="Sandbox configuration",
    config_type="sandbox",
    definition="class SandboxSettings(TypedDict): ...",
    properties=[
        {"name": "enabled", "type": "bool", "default": "False"}
    ],
    sdk="python"
)
```

#### `create_sdk_error(name, description, definition, parent_class=None, sdk="python", package="claude-agent-sdk")`

Creates an SDKError node (Python SDK).

```python
writer.create_sdk_error(
    name="CLINotFoundError",
    description="Raised when CLI not found",
    definition="class CLINotFoundError(CLIConnectionError): ...",
    parent_class="CLIConnectionError"
)
```

#### `create_enum_value(parent_type, value, description=None, sdk="typescript")`

Creates an SDKEnumValue node.

```python
writer.create_enum_value(
    parent_type="HookEvent",
    value="PreToolUse",
    description="Called before tool execution",
    sdk="python"
)
```

### Relationship Methods

#### `create_type_reference(from_type, to_type, relationship="REFERENCES", sdk="typescript")`

Creates a relationship between types.

```python
writer.create_type_reference("Options", "PermissionMode", "REFERENCES", sdk="typescript")
```

#### `create_function_returns(function_name, type_name, sdk="typescript")`

Links function to return type.

```python
writer.create_function_returns("query", "Query", sdk="typescript")
```

#### `create_function_accepts(function_name, type_name, sdk="typescript")`

Links function to parameter type.

```python
writer.create_function_accepts("query", "Options", sdk="typescript")
```

#### `create_message_in_union(message_name, union_name, sdk="typescript")`

Links message to union type.

```python
writer.create_message_in_union("AssistantMessage", "Message", sdk="python")
```

### Utility Methods

#### `create_index_constraints()`

Creates database indexes for efficient queries.

#### `clear_sdk_docs(sdk=None)`

Clears SDK documentation nodes. If `sdk` is provided, only clears that SDK's nodes.

```python
writer.clear_sdk_docs(sdk="python")  # Clear only Python docs
writer.clear_sdk_docs()               # Clear all SDK docs
```

---

## Population Scripts

### Running Population Scripts

```bash
# Populate TypeScript SDK docs
python .claude/hooks/populate_sdk_docs.py

# Populate Python SDK docs
python .claude/hooks/populate_python_sdk_docs.py
```

### Adding New Documentation

To add new SDK types or functions:

1. Open the appropriate population script
2. Add to the relevant `populate_*` function
3. Run the script (it clears existing docs for that SDK first)

Example adding a new type:

```python
def populate_my_types(writer: SDKDocsNeo4jWriter):
    writer.create_sdk_type(
        name="MyNewType",
        description="Description of the new type",
        definition="type MyNewType = { ... }",
        category="options",
        properties=[
            {"name": "prop1", "type": "string", "description": "..."}
        ],
        sdk="typescript"  # or "python"
    )
```

---

## Type Categories

| Category | Description | Examples |
|----------|-------------|----------|
| `options` | Configuration options | Options, ClaudeAgentOptions, AgentDefinition |
| `query` | Query interface types | Query |
| `message` | Message types | Message, ContentBlock, TextBlock |
| `hook` | Hook event types | HookEvent, HookCallback, HookMatcher |
| `permission` | Permission types | PermissionMode, PermissionResult |
| `tool_input` | Tool input schemas | (stored in SDKTool.input_schema) |
| `tool_output` | Tool output schemas | (stored in SDKTool.output_schema) |
| `mcp` | MCP configuration | McpServerConfig, McpStdioServerConfig |
| `sandbox` | Sandbox configuration | SandboxSettings, SandboxNetworkConfig |
| `other` | Utility types | ApiKeySource, ModelInfo, Usage |

---

## SDK Comparison Summary

### TypeScript SDK

- Package: `@anthropic-ai/claude-agent-sdk`
- Main function: `query()` returns `Query` (AsyncGenerator)
- Options type: `Options`
- Main types: interfaces and type aliases

### Python SDK

- Package: `claude-agent-sdk`
- Main function: `query()` returns `AsyncIterator[Message]`
- Main class: `ClaudeSDKClient` for continuous conversations
- Options type: `ClaudeAgentOptions` (dataclass)
- Main types: dataclasses and TypedDicts
- Additional: Exception classes (SDKError hierarchy)

### Key Differences

| Feature | TypeScript | Python |
|---------|------------|--------|
| Options type name | `Options` | `ClaudeAgentOptions` |
| Client class | (internal) | `ClaudeSDKClient` |
| Hooks supported | All 12 events | 6 events (no Session*, Notification) |
| Error types | (standard JS) | Custom exception hierarchy |
| Type system | Interfaces, type aliases | Dataclasses, TypedDicts |
