#!/usr/bin/env python3
"""
Populate Neo4j with Agent SDK Python documentation.

Run this script to import all Python SDK types, functions, classes, and tools
into the graph database.

Usage:
    python populate_python_sdk_docs.py
"""

import sys
from pathlib import Path

# Add hooks directory to path
sys.path.insert(0, str(Path(__file__).parent))

from sdk_docs_writer import SDKDocsNeo4jWriter

SDK = "python"
PACKAGE = "claude-agent-sdk"


def populate_functions(writer: SDKDocsNeo4jWriter):
    """Create SDK function nodes."""

    # query() function
    writer.create_sdk_function(
        name="query",
        description="Creates a new session for each interaction with Claude Code. Returns an async iterator that yields messages as they arrive. Each call to query() starts fresh with no memory of previous interactions.",
        signature="async def query(*, prompt: str | AsyncIterable[dict[str, Any]], options: ClaudeAgentOptions | None = None) -> AsyncIterator[Message]",
        parameters=[
            {
                "name": "prompt",
                "type": "str | AsyncIterable[dict[str, Any]]",
                "description": "The input prompt as a string or async iterable for streaming mode",
            },
            {
                "name": "options",
                "type": "ClaudeAgentOptions | None",
                "description": "Optional configuration object (defaults to ClaudeAgentOptions() if None)",
                "required": False,
            },
        ],
        returns="AsyncIterator[Message] that yields messages from the conversation",
        sdk=SDK,
        package=PACKAGE,
    )

    # tool() decorator
    writer.create_sdk_function(
        name="tool",
        description="Decorator for defining MCP tools with type safety.",
        signature="def tool(name: str, description: str, input_schema: type | dict[str, Any]) -> Callable[[Callable[[Any], Awaitable[dict[str, Any]]]], SdkMcpTool[Any]]",
        parameters=[
            {"name": "name", "type": "str", "description": "Unique identifier for the tool"},
            {"name": "description", "type": "str", "description": "Human-readable description of what the tool does"},
            {"name": "input_schema", "type": "type | dict[str, Any]", "description": "Schema defining the tool's input parameters"},
        ],
        returns="A decorator function that wraps the tool implementation and returns an SdkMcpTool instance",
        sdk=SDK,
        package=PACKAGE,
    )

    # create_sdk_mcp_server() function
    writer.create_sdk_function(
        name="create_sdk_mcp_server",
        description="Create an in-process MCP server that runs within your Python application.",
        signature="def create_sdk_mcp_server(name: str, version: str = '1.0.0', tools: list[SdkMcpTool[Any]] | None = None) -> McpSdkServerConfig",
        parameters=[
            {"name": "name", "type": "str", "description": "Unique identifier for the server"},
            {"name": "version", "type": "str", "default": "'1.0.0'", "description": "Server version string"},
            {"name": "tools", "type": "list[SdkMcpTool[Any]] | None", "default": "None", "description": "List of tool functions created with @tool decorator"},
        ],
        returns="McpSdkServerConfig object that can be passed to ClaudeAgentOptions.mcp_servers",
        sdk=SDK,
        package=PACKAGE,
    )


def populate_classes(writer: SDKDocsNeo4jWriter):
    """Create SDK class nodes."""

    # ClaudeSDKClient
    writer.create_sdk_class(
        name="ClaudeSDKClient",
        description="Maintains a conversation session across multiple exchanges. This is the Python equivalent of how the TypeScript SDK's query() function works internally - it creates a client object that can continue conversations.",
        definition="""class ClaudeSDKClient:
    def __init__(self, options: ClaudeAgentOptions | None = None)
    async def connect(self, prompt: str | AsyncIterable[dict] | None = None) -> None
    async def query(self, prompt: str | AsyncIterable[dict], session_id: str = "default") -> None
    async def receive_messages(self) -> AsyncIterator[Message]
    async def receive_response(self) -> AsyncIterator[Message]
    async def interrupt(self) -> None
    async def disconnect(self) -> None""",
        methods=[
            {"name": "__init__", "description": "Initialize the client with optional configuration"},
            {"name": "connect", "description": "Connect to Claude with an optional initial prompt or message stream"},
            {"name": "query", "description": "Send a new request in streaming mode"},
            {"name": "receive_messages", "description": "Receive all messages from Claude as an async iterator"},
            {"name": "receive_response", "description": "Receive messages until and including a ResultMessage"},
            {"name": "interrupt", "description": "Send interrupt signal (only works in streaming mode)"},
            {"name": "disconnect", "description": "Disconnect from Claude"},
        ],
        sdk=SDK,
        package=PACKAGE,
    )


def populate_options_type(writer: SDKDocsNeo4jWriter):
    """Create the ClaudeAgentOptions type and its properties."""

    options_properties = [
        {"name": "allowed_tools", "type": "list[str]", "default": "[]", "description": "List of allowed tool names"},
        {"name": "system_prompt", "type": "str | SystemPromptPreset | None", "default": "None", "description": "System prompt configuration"},
        {"name": "mcp_servers", "type": "dict[str, McpServerConfig] | str | Path", "default": "{}", "description": "MCP server configurations or path to config file"},
        {"name": "permission_mode", "type": "PermissionMode | None", "default": "None", "description": "Permission mode for tool usage"},
        {"name": "continue_conversation", "type": "bool", "default": "False", "description": "Continue the most recent conversation"},
        {"name": "resume", "type": "str | None", "default": "None", "description": "Session ID to resume"},
        {"name": "max_turns", "type": "int | None", "default": "None", "description": "Maximum conversation turns"},
        {"name": "disallowed_tools", "type": "list[str]", "default": "[]", "description": "List of disallowed tool names"},
        {"name": "model", "type": "str | None", "default": "None", "description": "Claude model to use"},
        {"name": "output_format", "type": "OutputFormat | None", "default": "None", "description": "Define output format for agent results (structured outputs)"},
        {"name": "permission_prompt_tool_name", "type": "str | None", "default": "None", "description": "MCP tool name for permission prompts"},
        {"name": "cwd", "type": "str | Path | None", "default": "None", "description": "Current working directory"},
        {"name": "settings", "type": "str | None", "default": "None", "description": "Path to settings file"},
        {"name": "add_dirs", "type": "list[str | Path]", "default": "[]", "description": "Additional directories Claude can access"},
        {"name": "env", "type": "dict[str, str]", "default": "{}", "description": "Environment variables"},
        {"name": "extra_args", "type": "dict[str, str | None]", "default": "{}", "description": "Additional CLI arguments"},
        {"name": "max_buffer_size", "type": "int | None", "default": "None", "description": "Maximum bytes when buffering CLI stdout"},
        {"name": "stderr", "type": "Callable[[str], None] | None", "default": "None", "description": "Callback function for stderr output from CLI"},
        {"name": "can_use_tool", "type": "CanUseTool | None", "default": "None", "description": "Tool permission callback function"},
        {"name": "hooks", "type": "dict[HookEvent, list[HookMatcher]] | None", "default": "None", "description": "Hook configurations for intercepting events"},
        {"name": "user", "type": "str | None", "default": "None", "description": "User identifier"},
        {"name": "include_partial_messages", "type": "bool", "default": "False", "description": "Include partial message streaming events"},
        {"name": "fork_session", "type": "bool", "default": "False", "description": "When resuming, fork to a new session ID instead of continuing the original"},
        {"name": "agents", "type": "dict[str, AgentDefinition] | None", "default": "None", "description": "Programmatically defined subagents"},
        {"name": "plugins", "type": "list[SdkPluginConfig]", "default": "[]", "description": "Load custom plugins from local paths"},
        {"name": "sandbox", "type": "SandboxSettings | None", "default": "None", "description": "Configure sandbox behavior programmatically"},
        {"name": "setting_sources", "type": "list[SettingSource] | None", "default": "None", "description": "Control which filesystem settings to load"},
    ]

    writer.create_sdk_type(
        name="ClaudeAgentOptions",
        description="Configuration dataclass for Claude Code queries.",
        definition="@dataclass\nclass ClaudeAgentOptions: ...",
        category="options",
        properties=options_properties,
        sdk=SDK,
        package=PACKAGE,
    )


def populate_sdk_mcp_tool(writer: SDKDocsNeo4jWriter):
    """Create SdkMcpTool type."""

    writer.create_sdk_type(
        name="SdkMcpTool",
        description="Definition for an SDK MCP tool created with the @tool decorator.",
        definition="""@dataclass
class SdkMcpTool(Generic[T]):
    name: str
    description: str
    input_schema: type[T] | dict[str, Any]
    handler: Callable[[T], Awaitable[dict[str, Any]]]""",
        category="tool",
        properties=[
            {"name": "name", "type": "str", "description": "Unique identifier for the tool"},
            {"name": "description", "type": "str", "description": "Human-readable description"},
            {"name": "input_schema", "type": "type[T] | dict[str, Any]", "description": "Schema for input validation"},
            {"name": "handler", "type": "Callable[[T], Awaitable[dict[str, Any]]]", "description": "Async function that handles tool execution"},
        ],
        sdk=SDK,
        package=PACKAGE,
    )


def populate_output_format(writer: SDKDocsNeo4jWriter):
    """Create OutputFormat type."""

    writer.create_sdk_type(
        name="OutputFormat",
        description="Configuration for structured output validation.",
        definition="""class OutputFormat(TypedDict):
    type: Literal["json_schema"]
    schema: dict[str, Any]""",
        category="options",
        properties=[
            {"name": "type", "type": 'Literal["json_schema"]', "required": True, "description": "Must be 'json_schema' for JSON Schema validation"},
            {"name": "schema", "type": "dict[str, Any]", "required": True, "description": "JSON Schema definition for output validation"},
        ],
        sdk=SDK,
        package=PACKAGE,
    )


def populate_system_prompt_preset(writer: SDKDocsNeo4jWriter):
    """Create SystemPromptPreset type."""

    writer.create_sdk_type(
        name="SystemPromptPreset",
        description="Configuration for using Claude Code's preset system prompt with optional additions.",
        definition="""class SystemPromptPreset(TypedDict):
    type: Literal["preset"]
    preset: Literal["claude_code"]
    append: NotRequired[str]""",
        category="options",
        properties=[
            {"name": "type", "type": 'Literal["preset"]', "required": True, "description": "Must be 'preset' to use a preset system prompt"},
            {"name": "preset", "type": 'Literal["claude_code"]', "required": True, "description": "Must be 'claude_code' to use Claude Code's system prompt"},
            {"name": "append", "type": "str", "required": False, "description": "Additional instructions to append to the preset"},
        ],
        sdk=SDK,
        package=PACKAGE,
    )


def populate_setting_source(writer: SDKDocsNeo4jWriter):
    """Create SettingSource type."""

    writer.create_sdk_type(
        name="SettingSource",
        description="Controls which filesystem-based configuration sources the SDK loads settings from.",
        definition='SettingSource = Literal["user", "project", "local"]',
        category="options",
        properties=[
            {"name": '"user"', "description": "Global user settings (~/.claude/settings.json)"},
            {"name": '"project"', "description": "Shared project settings, version controlled (.claude/settings.json)"},
            {"name": '"local"', "description": "Local project settings, gitignored (.claude/settings.local.json)"},
        ],
        sdk=SDK,
        package=PACKAGE,
    )


def populate_agent_definition(writer: SDKDocsNeo4jWriter):
    """Create AgentDefinition type."""

    writer.create_sdk_type(
        name="AgentDefinition",
        description="Configuration for a subagent defined programmatically.",
        definition="""@dataclass
class AgentDefinition:
    description: str
    prompt: str
    tools: list[str] | None = None
    model: Literal["sonnet", "opus", "haiku", "inherit"] | None = None""",
        category="options",
        properties=[
            {"name": "description", "type": "str", "required": True, "description": "Natural language description of when to use this agent"},
            {"name": "prompt", "type": "str", "required": True, "description": "The agent's system prompt"},
            {"name": "tools", "type": "list[str] | None", "required": False, "description": "Array of allowed tool names. If omitted, inherits all tools"},
            {"name": "model", "type": 'Literal["sonnet", "opus", "haiku", "inherit"] | None', "required": False, "description": "Model override for this agent"},
        ],
        sdk=SDK,
        package=PACKAGE,
    )


def populate_permission_mode(writer: SDKDocsNeo4jWriter):
    """Create PermissionMode type."""

    writer.create_sdk_type(
        name="PermissionMode",
        description="Permission modes for controlling tool execution.",
        definition='PermissionMode = Literal["default", "acceptEdits", "plan", "bypassPermissions"]',
        category="permission",
        properties=[
            {"name": '"default"', "description": "Standard permission behavior"},
            {"name": '"acceptEdits"', "description": "Auto-accept file edits"},
            {"name": '"plan"', "description": "Planning mode - no execution"},
            {"name": '"bypassPermissions"', "description": "Bypass all permission checks (use with caution)"},
        ],
        sdk=SDK,
        package=PACKAGE,
    )


def populate_mcp_types(writer: SDKDocsNeo4jWriter):
    """Create MCP server configuration types."""

    # McpServerConfig union
    writer.create_sdk_type(
        name="McpServerConfig",
        description="Union type for MCP server configurations.",
        definition="McpServerConfig = McpStdioServerConfig | McpSSEServerConfig | McpHttpServerConfig | McpSdkServerConfig",
        category="mcp",
        properties=[],
        sdk=SDK,
        package=PACKAGE,
    )

    # McpSdkServerConfig
    writer.create_sdk_config(
        name="McpSdkServerConfig",
        description="Configuration for SDK MCP servers created with create_sdk_mcp_server().",
        config_type="mcp",
        definition="""class McpSdkServerConfig(TypedDict):
    type: Literal["sdk"]
    name: str
    instance: Any  # MCP Server instance""",
        properties=[
            {"name": "type", "type": 'Literal["sdk"]', "required": True},
            {"name": "name", "type": "str", "required": True},
            {"name": "instance", "type": "Any", "required": True, "description": "MCP Server instance"},
        ],
        sdk=SDK,
        package=PACKAGE,
    )

    # McpStdioServerConfig
    writer.create_sdk_config(
        name="McpStdioServerConfig",
        description="STDIO-based MCP server configuration.",
        config_type="mcp",
        definition="""class McpStdioServerConfig(TypedDict):
    type: NotRequired[Literal["stdio"]]
    command: str
    args: NotRequired[list[str]]
    env: NotRequired[dict[str, str]]""",
        properties=[
            {"name": "type", "type": 'Literal["stdio"]', "required": False},
            {"name": "command", "type": "str", "required": True},
            {"name": "args", "type": "list[str]", "required": False},
            {"name": "env", "type": "dict[str, str]", "required": False},
        ],
        sdk=SDK,
        package=PACKAGE,
    )

    # McpSSEServerConfig
    writer.create_sdk_config(
        name="McpSSEServerConfig",
        description="SSE-based MCP server configuration.",
        config_type="mcp",
        definition="""class McpSSEServerConfig(TypedDict):
    type: Literal["sse"]
    url: str
    headers: NotRequired[dict[str, str]]""",
        properties=[
            {"name": "type", "type": 'Literal["sse"]', "required": True},
            {"name": "url", "type": "str", "required": True},
            {"name": "headers", "type": "dict[str, str]", "required": False},
        ],
        sdk=SDK,
        package=PACKAGE,
    )

    # McpHttpServerConfig
    writer.create_sdk_config(
        name="McpHttpServerConfig",
        description="HTTP-based MCP server configuration.",
        config_type="mcp",
        definition="""class McpHttpServerConfig(TypedDict):
    type: Literal["http"]
    url: str
    headers: NotRequired[dict[str, str]]""",
        properties=[
            {"name": "type", "type": 'Literal["http"]', "required": True},
            {"name": "url", "type": "str", "required": True},
            {"name": "headers", "type": "dict[str, str]", "required": False},
        ],
        sdk=SDK,
        package=PACKAGE,
    )


def populate_sandbox_types(writer: SDKDocsNeo4jWriter):
    """Create sandbox configuration types."""

    # SandboxSettings
    writer.create_sdk_config(
        name="SandboxSettings",
        description="Configuration for sandbox behavior. Use this to enable command sandboxing and configure network restrictions programmatically.",
        config_type="sandbox",
        definition="""class SandboxSettings(TypedDict, total=False):
    enabled: bool
    autoAllowBashIfSandboxed: bool
    excludedCommands: list[str]
    allowUnsandboxedCommands: bool
    network: SandboxNetworkConfig
    ignoreViolations: SandboxIgnoreViolations
    enableWeakerNestedSandbox: bool""",
        properties=[
            {"name": "enabled", "type": "bool", "default": "False", "description": "Enable sandbox mode for command execution"},
            {"name": "autoAllowBashIfSandboxed", "type": "bool", "default": "False", "description": "Auto-approve bash commands when sandbox is enabled"},
            {"name": "excludedCommands", "type": "list[str]", "default": "[]", "description": "Commands that always bypass sandbox restrictions"},
            {"name": "allowUnsandboxedCommands", "type": "bool", "default": "False", "description": "Allow the model to request running commands outside the sandbox"},
            {"name": "network", "type": "SandboxNetworkConfig", "required": False, "description": "Network-specific sandbox configuration"},
            {"name": "ignoreViolations", "type": "SandboxIgnoreViolations", "required": False, "description": "Configure which sandbox violations to ignore"},
            {"name": "enableWeakerNestedSandbox", "type": "bool", "default": "False", "description": "Enable a weaker nested sandbox for compatibility"},
        ],
        sdk=SDK,
        package=PACKAGE,
    )

    # SandboxNetworkConfig
    writer.create_sdk_config(
        name="SandboxNetworkConfig",
        description="Network-specific configuration for sandbox mode.",
        config_type="sandbox",
        definition="""class SandboxNetworkConfig(TypedDict, total=False):
    allowLocalBinding: bool
    allowUnixSockets: list[str]
    allowAllUnixSockets: bool
    httpProxyPort: int
    socksProxyPort: int""",
        properties=[
            {"name": "allowLocalBinding", "type": "bool", "default": "False", "description": "Allow processes to bind to local ports"},
            {"name": "allowUnixSockets", "type": "list[str]", "default": "[]", "description": "Unix socket paths that processes can access"},
            {"name": "allowAllUnixSockets", "type": "bool", "default": "False", "description": "Allow access to all Unix sockets"},
            {"name": "httpProxyPort", "type": "int", "required": False, "description": "HTTP proxy port for network requests"},
            {"name": "socksProxyPort", "type": "int", "required": False, "description": "SOCKS proxy port for network requests"},
        ],
        sdk=SDK,
        package=PACKAGE,
    )

    # SandboxIgnoreViolations
    writer.create_sdk_config(
        name="SandboxIgnoreViolations",
        description="Configuration for ignoring specific sandbox violations.",
        config_type="sandbox",
        definition="""class SandboxIgnoreViolations(TypedDict, total=False):
    file: list[str]
    network: list[str]""",
        properties=[
            {"name": "file", "type": "list[str]", "default": "[]", "description": "File path patterns to ignore violations for"},
            {"name": "network", "type": "list[str]", "default": "[]", "description": "Network patterns to ignore violations for"},
        ],
        sdk=SDK,
        package=PACKAGE,
    )


def populate_plugin_config(writer: SDKDocsNeo4jWriter):
    """Create SdkPluginConfig type."""

    writer.create_sdk_type(
        name="SdkPluginConfig",
        description="Configuration for loading plugins in the SDK.",
        definition="""class SdkPluginConfig(TypedDict):
    type: Literal["local"]
    path: str""",
        category="options",
        properties=[
            {"name": "type", "type": 'Literal["local"]', "required": True, "description": "Must be 'local' (only local plugins currently supported)"},
            {"name": "path", "type": "str", "required": True, "description": "Absolute or relative path to the plugin directory"},
        ],
        sdk=SDK,
        package=PACKAGE,
    )


def populate_message_types(writer: SDKDocsNeo4jWriter):
    """Create SDK message types."""

    # Message union
    writer.create_sdk_type(
        name="Message",
        description="Union type of all possible messages.",
        definition="Message = UserMessage | AssistantMessage | SystemMessage | ResultMessage",
        category="message",
        properties=[],
        sdk=SDK,
        package=PACKAGE,
    )

    # UserMessage
    writer.create_sdk_message(
        name="UserMessage",
        description="User input message.",
        message_type="user",
        definition="""@dataclass
class UserMessage:
    content: str | list[ContentBlock]""",
        sdk=SDK,
        package=PACKAGE,
    )

    # AssistantMessage
    writer.create_sdk_message(
        name="AssistantMessage",
        description="Assistant response message with content blocks.",
        message_type="assistant",
        definition="""@dataclass
class AssistantMessage:
    content: list[ContentBlock]
    model: str""",
        sdk=SDK,
        package=PACKAGE,
    )

    # SystemMessage
    writer.create_sdk_message(
        name="SystemMessage",
        description="System message with metadata.",
        message_type="system",
        definition="""@dataclass
class SystemMessage:
    subtype: str
    data: dict[str, Any]""",
        sdk=SDK,
        package=PACKAGE,
    )

    # ResultMessage
    writer.create_sdk_message(
        name="ResultMessage",
        description="Final result message with cost and usage information.",
        message_type="result",
        definition="""@dataclass
class ResultMessage:
    subtype: str
    duration_ms: int
    duration_api_ms: int
    is_error: bool
    num_turns: int
    session_id: str
    total_cost_usd: float | None = None
    usage: dict[str, Any] | None = None
    result: str | None = None""",
        sdk=SDK,
        package=PACKAGE,
    )


def populate_content_blocks(writer: SDKDocsNeo4jWriter):
    """Create content block types."""

    # ContentBlock union
    writer.create_sdk_type(
        name="ContentBlock",
        description="Union type of all content blocks.",
        definition="ContentBlock = TextBlock | ThinkingBlock | ToolUseBlock | ToolResultBlock",
        category="message",
        properties=[],
        sdk=SDK,
        package=PACKAGE,
    )

    # TextBlock
    writer.create_sdk_type(
        name="TextBlock",
        description="Text content block.",
        definition="""@dataclass
class TextBlock:
    text: str""",
        category="message",
        properties=[{"name": "text", "type": "str"}],
        sdk=SDK,
        package=PACKAGE,
    )

    # ThinkingBlock
    writer.create_sdk_type(
        name="ThinkingBlock",
        description="Thinking content block (for models with thinking capability).",
        definition="""@dataclass
class ThinkingBlock:
    thinking: str
    signature: str""",
        category="message",
        properties=[
            {"name": "thinking", "type": "str"},
            {"name": "signature", "type": "str"},
        ],
        sdk=SDK,
        package=PACKAGE,
    )

    # ToolUseBlock
    writer.create_sdk_type(
        name="ToolUseBlock",
        description="Tool use request block.",
        definition="""@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]""",
        category="message",
        properties=[
            {"name": "id", "type": "str"},
            {"name": "name", "type": "str"},
            {"name": "input", "type": "dict[str, Any]"},
        ],
        sdk=SDK,
        package=PACKAGE,
    )

    # ToolResultBlock
    writer.create_sdk_type(
        name="ToolResultBlock",
        description="Tool execution result block.",
        definition="""@dataclass
class ToolResultBlock:
    tool_use_id: str
    content: str | list[dict[str, Any]] | None = None
    is_error: bool | None = None""",
        category="message",
        properties=[
            {"name": "tool_use_id", "type": "str"},
            {"name": "content", "type": "str | list[dict[str, Any]] | None", "required": False},
            {"name": "is_error", "type": "bool | None", "required": False},
        ],
        sdk=SDK,
        package=PACKAGE,
    )


def populate_error_types(writer: SDKDocsNeo4jWriter):
    """Create error types."""

    # ClaudeSDKError
    writer.create_sdk_error(
        name="ClaudeSDKError",
        description="Base exception class for all SDK errors.",
        definition='class ClaudeSDKError(Exception):\n    """Base error for Claude SDK."""',
        parent_class="Exception",
        sdk=SDK,
        package=PACKAGE,
    )

    # CLINotFoundError
    writer.create_sdk_error(
        name="CLINotFoundError",
        description="Raised when Claude Code CLI is not installed or not found.",
        definition="""class CLINotFoundError(CLIConnectionError):
    def __init__(self, message: str = "Claude Code not found", cli_path: str | None = None):
        self.cli_path = cli_path""",
        parent_class="CLIConnectionError",
        sdk=SDK,
        package=PACKAGE,
    )

    # CLIConnectionError
    writer.create_sdk_error(
        name="CLIConnectionError",
        description="Raised when connection to Claude Code fails.",
        definition='class CLIConnectionError(ClaudeSDKError):\n    """Failed to connect to Claude Code."""',
        parent_class="ClaudeSDKError",
        sdk=SDK,
        package=PACKAGE,
    )

    # ProcessError
    writer.create_sdk_error(
        name="ProcessError",
        description="Raised when the Claude Code process fails.",
        definition="""class ProcessError(ClaudeSDKError):
    def __init__(self, message: str, exit_code: int | None = None, stderr: str | None = None):
        self.exit_code = exit_code
        self.stderr = stderr""",
        parent_class="ClaudeSDKError",
        sdk=SDK,
        package=PACKAGE,
    )

    # CLIJSONDecodeError
    writer.create_sdk_error(
        name="CLIJSONDecodeError",
        description="Raised when JSON parsing fails.",
        definition="""class CLIJSONDecodeError(ClaudeSDKError):
    def __init__(self, line: str, original_error: Exception):
        self.line = line
        self.original_error = original_error""",
        parent_class="ClaudeSDKError",
        sdk=SDK,
        package=PACKAGE,
    )


def populate_hook_types(writer: SDKDocsNeo4jWriter):
    """Create hook event types."""

    # HookEvent
    writer.create_sdk_type(
        name="HookEvent",
        description="Supported hook event types. Note that due to setup limitations, the Python SDK does not support SessionStart, SessionEnd, and Notification hooks.",
        definition="""HookEvent = Literal[
    "PreToolUse",
    "PostToolUse",
    "UserPromptSubmit",
    "Stop",
    "SubagentStop",
    "PreCompact"
]""",
        category="hook",
        properties=[],
        sdk=SDK,
        package=PACKAGE,
    )

    # HookCallback
    writer.create_sdk_type(
        name="HookCallback",
        description="Type definition for hook callback functions.",
        definition="""HookCallback = Callable[
    [dict[str, Any], str | None, HookContext],
    Awaitable[dict[str, Any]]
]""",
        category="hook",
        properties=[],
        sdk=SDK,
        package=PACKAGE,
    )

    # HookContext
    writer.create_sdk_type(
        name="HookContext",
        description="Context information passed to hook callbacks.",
        definition="""@dataclass
class HookContext:
    signal: Any | None = None  # Future: abort signal support""",
        category="hook",
        properties=[
            {"name": "signal", "type": "Any | None", "required": False, "description": "Future: abort signal support"},
        ],
        sdk=SDK,
        package=PACKAGE,
    )

    # HookMatcher
    writer.create_sdk_type(
        name="HookMatcher",
        description="Configuration for matching hooks to specific events or tools.",
        definition="""@dataclass
class HookMatcher:
    matcher: str | None = None
    hooks: list[HookCallback] = field(default_factory=list)
    timeout: float | None = None""",
        category="hook",
        properties=[
            {"name": "matcher", "type": "str | None", "required": False, "description": 'Tool name or pattern to match (e.g., "Bash", "Write|Edit")'},
            {"name": "hooks", "type": "list[HookCallback]", "required": True, "description": "List of callbacks to execute"},
            {"name": "timeout", "type": "float | None", "required": False, "description": "Timeout in seconds (default: 60)"},
        ],
        sdk=SDK,
        package=PACKAGE,
    )


def populate_tools(writer: SDKDocsNeo4jWriter):
    """Create SDK built-in tool definitions (same as TypeScript but with Python types)."""

    tools = [
        {
            "name": "Task",
            "description": "Launches a new agent to handle complex, multi-step tasks autonomously.",
            "input_schema": [
                {"name": "description", "type": "str", "required": True, "description": "A short (3-5 word) description of the task"},
                {"name": "prompt", "type": "str", "required": True, "description": "The task for the agent to perform"},
                {"name": "subagent_type", "type": "str", "required": True, "description": "The type of specialized agent to use"},
            ],
            "output_description": "Returns the final result from the subagent after completing the delegated task.",
        },
        {
            "name": "Bash",
            "description": "Executes bash commands in a persistent shell session with optional timeout and background execution.",
            "input_schema": [
                {"name": "command", "type": "str", "required": True, "description": "The command to execute"},
                {"name": "timeout", "type": "int | None", "required": False, "description": "Optional timeout in milliseconds (max 600000)"},
                {"name": "description", "type": "str | None", "required": False, "description": "Clear, concise description (5-10 words)"},
                {"name": "run_in_background", "type": "bool | None", "required": False, "description": "Set to true to run in background"},
            ],
            "output_description": "Returns command output with exit status. Background commands return immediately with a shellId.",
        },
        {
            "name": "Edit",
            "description": "Performs exact string replacements in files.",
            "input_schema": [
                {"name": "file_path", "type": "str", "required": True, "description": "The absolute path to the file to modify"},
                {"name": "old_string", "type": "str", "required": True, "description": "The text to replace"},
                {"name": "new_string", "type": "str", "required": True, "description": "The text to replace it with"},
                {"name": "replace_all", "type": "bool | None", "required": False, "description": "Replace all occurrences (default False)"},
            ],
            "output_description": "Returns confirmation of successful edits with replacement count.",
        },
        {
            "name": "Read",
            "description": "Reads files from the local filesystem, including text, images, PDFs, and Jupyter notebooks.",
            "input_schema": [
                {"name": "file_path", "type": "str", "required": True, "description": "The absolute path to the file to read"},
                {"name": "offset", "type": "int | None", "required": False, "description": "The line number to start reading from"},
                {"name": "limit", "type": "int | None", "required": False, "description": "The number of lines to read"},
            ],
            "output_description": "Returns file contents in format appropriate to file type.",
        },
        {
            "name": "Write",
            "description": "Writes a file to the local filesystem, overwriting if it exists.",
            "input_schema": [
                {"name": "file_path", "type": "str", "required": True, "description": "The absolute path to the file to write"},
                {"name": "content", "type": "str", "required": True, "description": "The content to write to the file"},
            ],
            "output_description": "Returns confirmation after successfully writing the file.",
        },
        {
            "name": "Glob",
            "description": "Fast file pattern matching that works with any codebase size.",
            "input_schema": [
                {"name": "pattern", "type": "str", "required": True, "description": "The glob pattern to match files against"},
                {"name": "path", "type": "str | None", "required": False, "description": "The directory to search in (defaults to cwd)"},
            ],
            "output_description": "Returns file paths matching the glob pattern, sorted by modification time.",
        },
        {
            "name": "Grep",
            "description": "Powerful search tool built on ripgrep with regex support.",
            "input_schema": [
                {"name": "pattern", "type": "str", "required": True, "description": "The regular expression pattern"},
                {"name": "path", "type": "str | None", "required": False, "description": "File or directory to search in"},
                {"name": "glob", "type": "str | None", "required": False, "description": "Glob pattern to filter files"},
                {"name": "type", "type": "str | None", "required": False, "description": "File type to search"},
                {"name": "output_mode", "type": "str | None", "required": False, "description": "'content', 'files_with_matches', or 'count'"},
            ],
            "output_description": "Returns search results in the format specified by output_mode.",
        },
        {
            "name": "NotebookEdit",
            "description": "Edits cells in Jupyter notebook files.",
            "input_schema": [
                {"name": "notebook_path", "type": "str", "required": True, "description": "Absolute path to the Jupyter notebook"},
                {"name": "cell_id", "type": "str | None", "required": False, "description": "The ID of the cell to edit"},
                {"name": "new_source", "type": "str", "required": True, "description": "The new source for the cell"},
                {"name": "cell_type", "type": "'code' | 'markdown' | None", "required": False, "description": "The type of the cell"},
                {"name": "edit_mode", "type": "'replace' | 'insert' | 'delete' | None", "required": False, "description": "Edit operation type"},
            ],
            "output_description": "Returns confirmation after modifying the Jupyter notebook.",
        },
        {
            "name": "WebFetch",
            "description": "Fetches content from a URL and processes it with an AI model.",
            "input_schema": [
                {"name": "url", "type": "str", "required": True, "description": "The URL to fetch content from"},
                {"name": "prompt", "type": "str", "required": True, "description": "The prompt to run on the fetched content"},
            ],
            "output_description": "Returns the AI's analysis of the fetched web content.",
        },
        {
            "name": "WebSearch",
            "description": "Searches the web and returns formatted results.",
            "input_schema": [
                {"name": "query", "type": "str", "required": True, "description": "The search query to use"},
                {"name": "allowed_domains", "type": "list[str] | None", "required": False, "description": "Only include results from these domains"},
                {"name": "blocked_domains", "type": "list[str] | None", "required": False, "description": "Never include results from these domains"},
            ],
            "output_description": "Returns formatted search results from the web.",
        },
        {
            "name": "TodoWrite",
            "description": "Creates and manages a structured task list for tracking progress.",
            "input_schema": [
                {"name": "todos", "type": "list[dict]", "required": True, "description": "The updated todo list with content, status, activeForm"},
            ],
            "output_description": "Returns confirmation with current task statistics.",
        },
        {
            "name": "BashOutput",
            "description": "Retrieves output from a running or completed background bash shell.",
            "input_schema": [
                {"name": "bash_id", "type": "str", "required": True, "description": "The ID of the background shell"},
                {"name": "filter", "type": "str | None", "required": False, "description": "Optional regex to filter output lines"},
            ],
            "output_description": "Returns incremental output from background shells.",
        },
        {
            "name": "KillBash",
            "description": "Kills a running background bash shell by its ID.",
            "input_schema": [
                {"name": "shell_id", "type": "str", "required": True, "description": "The ID of the background shell to kill"},
            ],
            "output_description": "Returns confirmation after terminating the background shell.",
        },
        {
            "name": "ExitPlanMode",
            "description": "Exits planning mode and prompts the user to approve the plan.",
            "input_schema": [
                {"name": "plan", "type": "str", "required": True, "description": "The plan to run by the user for approval"},
            ],
            "output_description": "Returns confirmation after exiting plan mode.",
        },
        {
            "name": "ListMcpResources",
            "description": "Lists available MCP resources from connected servers.",
            "input_schema": [
                {"name": "server", "type": "str | None", "required": False, "description": "Optional server name to filter resources by"},
            ],
            "output_description": "Returns list of available MCP resources.",
        },
        {
            "name": "ReadMcpResource",
            "description": "Reads a specific MCP resource from a server.",
            "input_schema": [
                {"name": "server", "type": "str", "required": True, "description": "The MCP server name"},
                {"name": "uri", "type": "str", "required": True, "description": "The resource URI to read"},
            ],
            "output_description": "Returns the contents of the requested MCP resource.",
        },
    ]

    for tool in tools:
        writer.create_sdk_tool(
            tool_name=tool["name"],
            description=tool["description"],
            input_schema=tool["input_schema"],
            output_description=tool.get("output_description"),
            sdk=SDK,
            package=PACKAGE,
        )


def create_relationships(writer: SDKDocsNeo4jWriter):
    """Create relationships between SDK components."""

    # Function relationships
    writer.create_function_accepts("query", "ClaudeAgentOptions", sdk=SDK)
    writer.create_function_returns("query", "Message", sdk=SDK)

    # Type references
    type_references = [
        ("ClaudeAgentOptions", "AgentDefinition", "REFERENCES"),
        ("ClaudeAgentOptions", "HookEvent", "REFERENCES"),
        ("ClaudeAgentOptions", "HookMatcher", "REFERENCES"),
        ("ClaudeAgentOptions", "McpServerConfig", "REFERENCES"),
        ("ClaudeAgentOptions", "PermissionMode", "REFERENCES"),
        ("ClaudeAgentOptions", "SandboxSettings", "REFERENCES"),
        ("ClaudeAgentOptions", "SettingSource", "REFERENCES"),
        ("ClaudeAgentOptions", "SdkPluginConfig", "REFERENCES"),
        ("ClaudeAgentOptions", "OutputFormat", "REFERENCES"),
        ("ClaudeAgentOptions", "SystemPromptPreset", "REFERENCES"),
        ("Message", "UserMessage", "INCLUDES"),
        ("Message", "AssistantMessage", "INCLUDES"),
        ("Message", "SystemMessage", "INCLUDES"),
        ("Message", "ResultMessage", "INCLUDES"),
        ("ContentBlock", "TextBlock", "INCLUDES"),
        ("ContentBlock", "ThinkingBlock", "INCLUDES"),
        ("ContentBlock", "ToolUseBlock", "INCLUDES"),
        ("ContentBlock", "ToolResultBlock", "INCLUDES"),
        ("McpServerConfig", "McpStdioServerConfig", "INCLUDES"),
        ("McpServerConfig", "McpSSEServerConfig", "INCLUDES"),
        ("McpServerConfig", "McpHttpServerConfig", "INCLUDES"),
        ("McpServerConfig", "McpSdkServerConfig", "INCLUDES"),
        ("SandboxSettings", "SandboxNetworkConfig", "REFERENCES"),
        ("SandboxSettings", "SandboxIgnoreViolations", "REFERENCES"),
    ]

    for from_type, to_type, rel in type_references:
        writer.create_type_reference(from_type, to_type, rel, sdk=SDK)

    # Message union members
    message_members = ["UserMessage", "AssistantMessage", "SystemMessage", "ResultMessage"]
    for msg in message_members:
        writer.create_message_in_union(msg, "Message", sdk=SDK)


def main():
    """Main function to populate Python SDK documentation."""
    print("Connecting to Neo4j...")

    try:
        with SDKDocsNeo4jWriter() as writer:
            print("Creating indexes...")
            writer.create_index_constraints()

            print("Clearing existing Python SDK documentation...")
            writer.clear_sdk_docs(sdk="python")

            print("Populating functions...")
            populate_functions(writer)

            print("Populating classes...")
            populate_classes(writer)

            print("Populating ClaudeAgentOptions type...")
            populate_options_type(writer)

            print("Populating SdkMcpTool type...")
            populate_sdk_mcp_tool(writer)

            print("Populating OutputFormat type...")
            populate_output_format(writer)

            print("Populating SystemPromptPreset type...")
            populate_system_prompt_preset(writer)

            print("Populating SettingSource type...")
            populate_setting_source(writer)

            print("Populating AgentDefinition type...")
            populate_agent_definition(writer)

            print("Populating PermissionMode type...")
            populate_permission_mode(writer)

            print("Populating MCP types...")
            populate_mcp_types(writer)

            print("Populating sandbox types...")
            populate_sandbox_types(writer)

            print("Populating plugin config...")
            populate_plugin_config(writer)

            print("Populating message types...")
            populate_message_types(writer)

            print("Populating content blocks...")
            populate_content_blocks(writer)

            print("Populating error types...")
            populate_error_types(writer)

            print("Populating hook types...")
            populate_hook_types(writer)

            print("Populating tools...")
            populate_tools(writer)

            print("Creating relationships...")
            create_relationships(writer)

            print("\nPython SDK documentation successfully imported to Neo4j!")
            print("\nExample queries:")
            print("  // Find all Python SDK functions")
            print("  MATCH (f:SDKFunction {sdk: 'python'}) RETURN f.name, f.description")
            print("")
            print("  // Find Python SDK classes")
            print("  MATCH (c:SDKClass {sdk: 'python'}) RETURN c.name, c.description")
            print("")
            print("  // Find Python-specific error types")
            print("  MATCH (e:SDKError {sdk: 'python'}) RETURN e.name, e.parent_class")
            print("")
            print("  // Compare types between TypeScript and Python SDKs")
            print("  MATCH (t:SDKType) WHERE t.name = 'ClaudeAgentOptions' OR t.name = 'Options'")
            print("  RETURN t.name, t.sdk, t.category")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
