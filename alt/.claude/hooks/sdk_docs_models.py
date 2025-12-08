"""
Data models for Agent SDK documentation stored in Neo4j.

These models represent TypeScript SDK components as graph nodes.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SDKFunction:
    """Represents an SDK function like query() or tool()."""

    name: str
    description: str
    signature: str
    parameters: list[dict[str, Any]] = field(default_factory=list)
    returns: str | None = None
    example_code: str | None = None


@dataclass
class SDKType:
    """Represents a TypeScript type or interface."""

    name: str
    description: str
    definition: str  # Full TypeScript definition
    category: str  # e.g., 'options', 'message', 'hook', 'permission', 'tool', 'other'
    properties: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SDKTypeProperty:
    """Represents a property within a type/interface."""

    name: str
    type_str: str
    description: str
    required: bool = True
    default: str | None = None


@dataclass
class SDKToolInput:
    """Represents input schema for a built-in tool."""

    tool_name: str
    description: str
    properties: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SDKToolOutput:
    """Represents output schema for a built-in tool."""

    tool_name: str
    description: str
    properties: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SDKHookEvent:
    """Represents a hook event type."""

    name: str
    description: str
    input_type: str  # Name of the input type
    output_fields: list[str] = field(default_factory=list)


@dataclass
class SDKMessage:
    """Represents an SDK message type."""

    name: str
    description: str
    message_type: str  # e.g., 'assistant', 'user', 'result', 'system'
    definition: str


@dataclass
class SDKEnumValue:
    """Represents a value in a union/enum type."""

    parent_type: str
    value: str
    description: str | None = None


# Categories for organizing types
SDK_TYPE_CATEGORIES = {
    "options": "Configuration options for SDK functions",
    "query": "Query interface and related types",
    "message": "Message types returned by the SDK",
    "hook": "Hook events and callbacks",
    "permission": "Permission system types",
    "tool_input": "Tool input schemas",
    "tool_output": "Tool output schemas",
    "mcp": "MCP server configuration",
    "sandbox": "Sandbox configuration",
    "other": "Utility and miscellaneous types",
}
