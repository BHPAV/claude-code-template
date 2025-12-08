#!/usr/bin/env python3
"""
Populate Neo4j with Agent SDK TypeScript documentation.

Run this script to import all SDK types, functions, tools, and hooks
into the graph database.

Usage:
    python populate_sdk_docs.py
"""

import sys
from pathlib import Path

# Add hooks directory to path
sys.path.insert(0, str(Path(__file__).parent))

from sdk_docs_writer import SDKDocsNeo4jWriter


def populate_functions(writer: SDKDocsNeo4jWriter):
    """Create SDK function nodes."""

    # query() function
    writer.create_sdk_function(
        name="query",
        description="The primary function for interacting with Claude Code. Creates an async generator that streams messages as they arrive.",
        signature="function query({ prompt, options }: { prompt: string | AsyncIterable<SDKUserMessage>; options?: Options; }): Query",
        parameters=[
            {
                "name": "prompt",
                "type": "string | AsyncIterable<SDKUserMessage>",
                "description": "The input prompt as a string or async iterable for streaming mode",
            },
            {
                "name": "options",
                "type": "Options",
                "description": "Optional configuration object",
                "required": False,
            },
        ],
        returns="Query object that extends AsyncGenerator<SDKMessage, void> with additional methods",
    )

    # tool() function
    writer.create_sdk_function(
        name="tool",
        description="Creates a type-safe MCP tool definition for use with SDK MCP servers.",
        signature="function tool<Schema extends ZodRawShape>(name: string, description: string, inputSchema: Schema, handler: (args: z.infer<ZodObject<Schema>>, extra: unknown) => Promise<CallToolResult>): SdkMcpToolDefinition<Schema>",
        parameters=[
            {"name": "name", "type": "string", "description": "The name of the tool"},
            {
                "name": "description",
                "type": "string",
                "description": "A description of what the tool does",
            },
            {
                "name": "inputSchema",
                "type": "Schema extends ZodRawShape",
                "description": "Zod schema defining the tool's input parameters",
            },
            {
                "name": "handler",
                "type": "(args, extra) => Promise<CallToolResult>",
                "description": "Async function that executes the tool logic",
            },
        ],
        returns="SdkMcpToolDefinition<Schema>",
    )

    # createSdkMcpServer() function
    writer.create_sdk_function(
        name="createSdkMcpServer",
        description="Creates an MCP server instance that runs in the same process as your application.",
        signature="function createSdkMcpServer(options: { name: string; version?: string; tools?: Array<SdkMcpToolDefinition<any>>; }): McpSdkServerConfigWithInstance",
        parameters=[
            {
                "name": "options.name",
                "type": "string",
                "description": "The name of the MCP server",
            },
            {
                "name": "options.version",
                "type": "string",
                "description": "Optional version string",
                "required": False,
            },
            {
                "name": "options.tools",
                "type": "Array<SdkMcpToolDefinition>",
                "description": "Array of tool definitions created with tool()",
                "required": False,
            },
        ],
        returns="McpSdkServerConfigWithInstance",
    )


def populate_options_type(writer: SDKDocsNeo4jWriter):
    """Create the Options type and its properties."""

    options_properties = [
        {
            "name": "abortController",
            "type": "AbortController",
            "default": "new AbortController()",
            "description": "Controller for cancelling operations",
        },
        {
            "name": "additionalDirectories",
            "type": "string[]",
            "default": "[]",
            "description": "Additional directories Claude can access",
        },
        {
            "name": "agents",
            "type": "Record<string, AgentDefinition>",
            "default": "undefined",
            "description": "Programmatically define subagents",
        },
        {
            "name": "allowDangerouslySkipPermissions",
            "type": "boolean",
            "default": "false",
            "description": "Enable bypassing permissions. Required when using permissionMode: 'bypassPermissions'",
        },
        {
            "name": "allowedTools",
            "type": "string[]",
            "default": "All tools",
            "description": "List of allowed tool names",
        },
        {
            "name": "betas",
            "type": "SdkBeta[]",
            "default": "[]",
            "description": "Enable beta features (e.g., ['context-1m-2025-08-07'])",
        },
        {
            "name": "canUseTool",
            "type": "CanUseTool",
            "default": "undefined",
            "description": "Custom permission function for tool usage",
        },
        {
            "name": "continue",
            "type": "boolean",
            "default": "false",
            "description": "Continue the most recent conversation",
        },
        {
            "name": "cwd",
            "type": "string",
            "default": "process.cwd()",
            "description": "Current working directory",
        },
        {
            "name": "disallowedTools",
            "type": "string[]",
            "default": "[]",
            "description": "List of disallowed tool names",
        },
        {
            "name": "env",
            "type": "Dict<string>",
            "default": "process.env",
            "description": "Environment variables",
        },
        {
            "name": "executable",
            "type": "'bun' | 'deno' | 'node'",
            "default": "Auto-detected",
            "description": "JavaScript runtime to use",
        },
        {
            "name": "executableArgs",
            "type": "string[]",
            "default": "[]",
            "description": "Arguments to pass to the executable",
        },
        {
            "name": "extraArgs",
            "type": "Record<string, string | null>",
            "default": "{}",
            "description": "Additional arguments",
        },
        {
            "name": "fallbackModel",
            "type": "string",
            "default": "undefined",
            "description": "Model to use if primary fails",
        },
        {
            "name": "forkSession",
            "type": "boolean",
            "default": "false",
            "description": "When resuming with resume, fork to a new session ID instead of continuing the original session",
        },
        {
            "name": "hooks",
            "type": "Partial<Record<HookEvent, HookCallbackMatcher[]>>",
            "default": "{}",
            "description": "Hook callbacks for events",
        },
        {
            "name": "includePartialMessages",
            "type": "boolean",
            "default": "false",
            "description": "Include partial message events",
        },
        {
            "name": "maxBudgetUsd",
            "type": "number",
            "default": "undefined",
            "description": "Maximum budget in USD for the query",
        },
        {
            "name": "maxThinkingTokens",
            "type": "number",
            "default": "undefined",
            "description": "Maximum tokens for thinking process",
        },
        {
            "name": "maxTurns",
            "type": "number",
            "default": "undefined",
            "description": "Maximum conversation turns",
        },
        {
            "name": "mcpServers",
            "type": "Record<string, McpServerConfig>",
            "default": "{}",
            "description": "MCP server configurations",
        },
        {
            "name": "model",
            "type": "string",
            "default": "Default from CLI",
            "description": "Claude model to use",
        },
        {
            "name": "outputFormat",
            "type": "{ type: 'json_schema', schema: JSONSchema }",
            "default": "undefined",
            "description": "Define output format for agent results (structured outputs)",
        },
        {
            "name": "pathToClaudeCodeExecutable",
            "type": "string",
            "default": "Uses built-in executable",
            "description": "Path to Claude Code executable",
        },
        {
            "name": "permissionMode",
            "type": "PermissionMode",
            "default": "'default'",
            "description": "Permission mode for the session",
        },
        {
            "name": "permissionPromptToolName",
            "type": "string",
            "default": "undefined",
            "description": "MCP tool name for permission prompts",
        },
        {
            "name": "plugins",
            "type": "SdkPluginConfig[]",
            "default": "[]",
            "description": "Load custom plugins from local paths",
        },
        {
            "name": "resume",
            "type": "string",
            "default": "undefined",
            "description": "Session ID to resume",
        },
        {
            "name": "resumeSessionAt",
            "type": "string",
            "default": "undefined",
            "description": "Resume session at a specific message UUID",
        },
        {
            "name": "sandbox",
            "type": "SandboxSettings",
            "default": "undefined",
            "description": "Configure sandbox behavior programmatically",
        },
        {
            "name": "settingSources",
            "type": "SettingSource[]",
            "default": "[] (no settings)",
            "description": "Control which filesystem settings to load. Must include 'project' to load CLAUDE.md files",
        },
        {
            "name": "stderr",
            "type": "(data: string) => void",
            "default": "undefined",
            "description": "Callback for stderr output",
        },
        {
            "name": "strictMcpConfig",
            "type": "boolean",
            "default": "false",
            "description": "Enforce strict MCP validation",
        },
        {
            "name": "systemPrompt",
            "type": "string | { type: 'preset'; preset: 'claude_code'; append?: string }",
            "default": "undefined (empty prompt)",
            "description": "System prompt configuration. Pass a string for custom prompt, or use preset for Claude Code's system prompt",
        },
        {
            "name": "tools",
            "type": "string[] | { type: 'preset'; preset: 'claude_code' }",
            "default": "undefined",
            "description": "Tool configuration. Pass an array of tool names or use the preset for Claude Code's default tools",
        },
    ]

    writer.create_sdk_type(
        name="Options",
        description="Configuration object for the query() function.",
        definition="interface Options { ... }",
        category="options",
        properties=options_properties,
    )


def populate_query_type(writer: SDKDocsNeo4jWriter):
    """Create the Query interface type."""

    query_methods = [
        {"name": "interrupt", "description": "Interrupts the query (only available in streaming input mode)"},
        {"name": "setPermissionMode", "description": "Changes the permission mode (only available in streaming input mode)"},
        {"name": "setModel", "description": "Changes the model (only available in streaming input mode)"},
        {"name": "setMaxThinkingTokens", "description": "Changes the maximum thinking tokens (only available in streaming input mode)"},
        {"name": "supportedCommands", "description": "Returns available slash commands"},
        {"name": "supportedModels", "description": "Returns available models with display info"},
        {"name": "mcpServerStatus", "description": "Returns status of connected MCP servers"},
        {"name": "accountInfo", "description": "Returns account information"},
    ]

    writer.create_sdk_type(
        name="Query",
        description="Interface returned by the query() function. Extends AsyncGenerator<SDKMessage, void> with additional methods.",
        definition="""interface Query extends AsyncGenerator<SDKMessage, void> {
  interrupt(): Promise<void>;
  setPermissionMode(mode: PermissionMode): Promise<void>;
  setModel(model?: string): Promise<void>;
  setMaxThinkingTokens(maxThinkingTokens: number | null): Promise<void>;
  supportedCommands(): Promise<SlashCommand[]>;
  supportedModels(): Promise<ModelInfo[]>;
  mcpServerStatus(): Promise<McpServerStatus[]>;
  accountInfo(): Promise<AccountInfo>;
}""",
        category="query",
        properties=query_methods,
    )


def populate_agent_definition(writer: SDKDocsNeo4jWriter):
    """Create AgentDefinition type."""

    writer.create_sdk_type(
        name="AgentDefinition",
        description="Configuration for a subagent defined programmatically.",
        definition="""type AgentDefinition = {
  description: string;
  tools?: string[];
  prompt: string;
  model?: 'sonnet' | 'opus' | 'haiku' | 'inherit';
}""",
        category="options",
        properties=[
            {"name": "description", "type": "string", "required": True, "description": "Natural language description of when to use this agent"},
            {"name": "tools", "type": "string[]", "required": False, "description": "Array of allowed tool names. If omitted, inherits all tools"},
            {"name": "prompt", "type": "string", "required": True, "description": "The agent's system prompt"},
            {"name": "model", "type": "'sonnet' | 'opus' | 'haiku' | 'inherit'", "required": False, "description": "Model override for this agent. If omitted, uses the main model"},
        ],
    )


def populate_setting_source(writer: SDKDocsNeo4jWriter):
    """Create SettingSource type."""

    writer.create_sdk_type(
        name="SettingSource",
        description="Controls which filesystem-based configuration sources the SDK loads settings from.",
        definition="type SettingSource = 'user' | 'project' | 'local';",
        category="options",
        properties=[
            {"name": "'user'", "description": "Global user settings (~/.claude/settings.json)"},
            {"name": "'project'", "description": "Shared project settings, version controlled (.claude/settings.json)"},
            {"name": "'local'", "description": "Local project settings, gitignored (.claude/settings.local.json)"},
        ],
    )


def populate_permission_types(writer: SDKDocsNeo4jWriter):
    """Create permission-related types."""

    # PermissionMode
    writer.create_sdk_type(
        name="PermissionMode",
        description="Permission mode for the session.",
        definition="type PermissionMode = 'default' | 'acceptEdits' | 'bypassPermissions' | 'plan';",
        category="permission",
        properties=[
            {"name": "'default'", "description": "Standard permission behavior"},
            {"name": "'acceptEdits'", "description": "Auto-accept file edits"},
            {"name": "'bypassPermissions'", "description": "Bypass all permission checks"},
            {"name": "'plan'", "description": "Planning mode - no execution"},
        ],
    )

    # CanUseTool
    writer.create_sdk_type(
        name="CanUseTool",
        description="Custom permission function type for controlling tool usage.",
        definition="""type CanUseTool = (
  toolName: string,
  input: ToolInput,
  options: {
    signal: AbortSignal;
    suggestions?: PermissionUpdate[];
  }
) => Promise<PermissionResult>;""",
        category="permission",
        properties=[],
    )

    # PermissionResult
    writer.create_sdk_type(
        name="PermissionResult",
        description="Result of a permission check.",
        definition="""type PermissionResult =
  | { behavior: 'allow'; updatedInput: ToolInput; updatedPermissions?: PermissionUpdate[]; }
  | { behavior: 'deny'; message: string; interrupt?: boolean; }""",
        category="permission",
        properties=[],
    )

    # PermissionUpdate
    writer.create_sdk_type(
        name="PermissionUpdate",
        description="Operations for updating permissions.",
        definition="""type PermissionUpdate =
  | { type: 'addRules'; rules: PermissionRuleValue[]; behavior: PermissionBehavior; destination: PermissionUpdateDestination; }
  | { type: 'replaceRules'; rules: PermissionRuleValue[]; behavior: PermissionBehavior; destination: PermissionUpdateDestination; }
  | { type: 'removeRules'; rules: PermissionRuleValue[]; behavior: PermissionBehavior; destination: PermissionUpdateDestination; }
  | { type: 'setMode'; mode: PermissionMode; destination: PermissionUpdateDestination; }
  | { type: 'addDirectories'; directories: string[]; destination: PermissionUpdateDestination; }
  | { type: 'removeDirectories'; directories: string[]; destination: PermissionUpdateDestination; }""",
        category="permission",
        properties=[],
    )

    # PermissionBehavior
    writer.create_sdk_type(
        name="PermissionBehavior",
        description="Permission behavior type.",
        definition="type PermissionBehavior = 'allow' | 'deny' | 'ask';",
        category="permission",
        properties=[],
    )

    # PermissionUpdateDestination
    writer.create_sdk_type(
        name="PermissionUpdateDestination",
        description="Destination for permission updates.",
        definition="type PermissionUpdateDestination = 'userSettings' | 'projectSettings' | 'localSettings' | 'session';",
        category="permission",
        properties=[
            {"name": "'userSettings'", "description": "Global user settings"},
            {"name": "'projectSettings'", "description": "Per-directory project settings"},
            {"name": "'localSettings'", "description": "Gitignored local settings"},
            {"name": "'session'", "description": "Current session only"},
        ],
    )

    # PermissionRuleValue
    writer.create_sdk_type(
        name="PermissionRuleValue",
        description="A permission rule value.",
        definition="""type PermissionRuleValue = {
  toolName: string;
  ruleContent?: string;
}""",
        category="permission",
        properties=[
            {"name": "toolName", "type": "string", "required": True},
            {"name": "ruleContent", "type": "string", "required": False},
        ],
    )


def populate_mcp_types(writer: SDKDocsNeo4jWriter):
    """Create MCP server configuration types."""

    # McpServerConfig
    writer.create_sdk_type(
        name="McpServerConfig",
        description="Configuration for MCP servers.",
        definition="type McpServerConfig = McpStdioServerConfig | McpSSEServerConfig | McpHttpServerConfig | McpSdkServerConfigWithInstance;",
        category="mcp",
        properties=[],
    )

    # McpStdioServerConfig
    writer.create_sdk_config(
        name="McpStdioServerConfig",
        description="STDIO-based MCP server configuration.",
        config_type="mcp",
        definition="""type McpStdioServerConfig = {
  type?: 'stdio';
  command: string;
  args?: string[];
  env?: Record<string, string>;
}""",
        properties=[
            {"name": "type", "type": "'stdio'", "required": False},
            {"name": "command", "type": "string", "required": True, "description": "Command to execute"},
            {"name": "args", "type": "string[]", "required": False, "description": "Command arguments"},
            {"name": "env", "type": "Record<string, string>", "required": False, "description": "Environment variables"},
        ],
    )

    # McpSSEServerConfig
    writer.create_sdk_config(
        name="McpSSEServerConfig",
        description="SSE-based MCP server configuration.",
        config_type="mcp",
        definition="""type McpSSEServerConfig = {
  type: 'sse';
  url: string;
  headers?: Record<string, string>;
}""",
        properties=[
            {"name": "type", "type": "'sse'", "required": True},
            {"name": "url", "type": "string", "required": True, "description": "Server URL"},
            {"name": "headers", "type": "Record<string, string>", "required": False, "description": "HTTP headers"},
        ],
    )

    # McpHttpServerConfig
    writer.create_sdk_config(
        name="McpHttpServerConfig",
        description="HTTP-based MCP server configuration.",
        config_type="mcp",
        definition="""type McpHttpServerConfig = {
  type: 'http';
  url: string;
  headers?: Record<string, string>;
}""",
        properties=[
            {"name": "type", "type": "'http'", "required": True},
            {"name": "url", "type": "string", "required": True, "description": "Server URL"},
            {"name": "headers", "type": "Record<string, string>", "required": False, "description": "HTTP headers"},
        ],
    )

    # McpSdkServerConfigWithInstance
    writer.create_sdk_config(
        name="McpSdkServerConfigWithInstance",
        description="In-process SDK MCP server configuration.",
        config_type="mcp",
        definition="""type McpSdkServerConfigWithInstance = {
  type: 'sdk';
  name: string;
  instance: McpServer;
}""",
        properties=[
            {"name": "type", "type": "'sdk'", "required": True},
            {"name": "name", "type": "string", "required": True, "description": "Server name"},
            {"name": "instance", "type": "McpServer", "required": True, "description": "MCP server instance"},
        ],
    )


def populate_sandbox_types(writer: SDKDocsNeo4jWriter):
    """Create sandbox configuration types."""

    # SandboxSettings
    writer.create_sdk_config(
        name="SandboxSettings",
        description="Configuration for sandbox behavior. Use this to enable command sandboxing and configure network restrictions programmatically.",
        config_type="sandbox",
        definition="""type SandboxSettings = {
  enabled?: boolean;
  autoAllowBashIfSandboxed?: boolean;
  excludedCommands?: string[];
  allowUnsandboxedCommands?: boolean;
  network?: NetworkSandboxSettings;
  ignoreViolations?: SandboxIgnoreViolations;
  enableWeakerNestedSandbox?: boolean;
}""",
        properties=[
            {"name": "enabled", "type": "boolean", "default": "false", "description": "Enable sandbox mode for command execution"},
            {"name": "autoAllowBashIfSandboxed", "type": "boolean", "default": "false", "description": "Auto-approve bash commands when sandbox is enabled"},
            {"name": "excludedCommands", "type": "string[]", "default": "[]", "description": "Commands that always bypass sandbox restrictions"},
            {"name": "allowUnsandboxedCommands", "type": "boolean", "default": "false", "description": "Allow the model to request running commands outside the sandbox"},
            {"name": "network", "type": "NetworkSandboxSettings", "required": False, "description": "Network-specific sandbox configuration"},
            {"name": "ignoreViolations", "type": "SandboxIgnoreViolations", "required": False, "description": "Configure which sandbox violations to ignore"},
            {"name": "enableWeakerNestedSandbox", "type": "boolean", "default": "false", "description": "Enable a weaker nested sandbox for compatibility"},
        ],
    )

    # NetworkSandboxSettings
    writer.create_sdk_config(
        name="NetworkSandboxSettings",
        description="Network-specific configuration for sandbox mode.",
        config_type="sandbox",
        definition="""type NetworkSandboxSettings = {
  allowLocalBinding?: boolean;
  allowUnixSockets?: string[];
  allowAllUnixSockets?: boolean;
  httpProxyPort?: number;
  socksProxyPort?: number;
}""",
        properties=[
            {"name": "allowLocalBinding", "type": "boolean", "default": "false", "description": "Allow processes to bind to local ports"},
            {"name": "allowUnixSockets", "type": "string[]", "default": "[]", "description": "Unix socket paths that processes can access"},
            {"name": "allowAllUnixSockets", "type": "boolean", "default": "false", "description": "Allow access to all Unix sockets"},
            {"name": "httpProxyPort", "type": "number", "required": False, "description": "HTTP proxy port for network requests"},
            {"name": "socksProxyPort", "type": "number", "required": False, "description": "SOCKS proxy port for network requests"},
        ],
    )

    # SandboxIgnoreViolations
    writer.create_sdk_config(
        name="SandboxIgnoreViolations",
        description="Configuration for ignoring specific sandbox violations.",
        config_type="sandbox",
        definition="""type SandboxIgnoreViolations = {
  file?: string[];
  network?: string[];
}""",
        properties=[
            {"name": "file", "type": "string[]", "default": "[]", "description": "File path patterns to ignore violations for"},
            {"name": "network", "type": "string[]", "default": "[]", "description": "Network patterns to ignore violations for"},
        ],
    )


def populate_message_types(writer: SDKDocsNeo4jWriter):
    """Create SDK message types."""

    # SDKMessage union
    writer.create_sdk_type(
        name="SDKMessage",
        description="Union type of all possible messages returned by the query.",
        definition="""type SDKMessage =
  | SDKAssistantMessage
  | SDKUserMessage
  | SDKUserMessageReplay
  | SDKResultMessage
  | SDKSystemMessage
  | SDKPartialAssistantMessage
  | SDKCompactBoundaryMessage;""",
        category="message",
        properties=[],
    )

    # SDKAssistantMessage
    writer.create_sdk_message(
        name="SDKAssistantMessage",
        description="Assistant response message.",
        message_type="assistant",
        definition="""type SDKAssistantMessage = {
  type: 'assistant';
  uuid: UUID;
  session_id: string;
  message: APIAssistantMessage;
  parent_tool_use_id: string | null;
}""",
    )

    # SDKUserMessage
    writer.create_sdk_message(
        name="SDKUserMessage",
        description="User input message.",
        message_type="user",
        definition="""type SDKUserMessage = {
  type: 'user';
  uuid?: UUID;
  session_id: string;
  message: APIUserMessage;
  parent_tool_use_id: string | null;
}""",
    )

    # SDKUserMessageReplay
    writer.create_sdk_message(
        name="SDKUserMessageReplay",
        description="Replayed user message with required UUID.",
        message_type="user",
        definition="""type SDKUserMessageReplay = {
  type: 'user';
  uuid: UUID;
  session_id: string;
  message: APIUserMessage;
  parent_tool_use_id: string | null;
}""",
    )

    # SDKResultMessage
    writer.create_sdk_message(
        name="SDKResultMessage",
        description="Final result message with success or error information.",
        message_type="result",
        definition="""type SDKResultMessage =
  | {
      type: 'result';
      subtype: 'success';
      uuid: UUID;
      session_id: string;
      duration_ms: number;
      duration_api_ms: number;
      is_error: boolean;
      num_turns: number;
      result: string;
      total_cost_usd: number;
      usage: NonNullableUsage;
      modelUsage: { [modelName: string]: ModelUsage };
      permission_denials: SDKPermissionDenial[];
      structured_output?: unknown;
    }
  | {
      type: 'result';
      subtype: 'error_max_turns' | 'error_during_execution' | 'error_max_budget_usd' | 'error_max_structured_output_retries';
      uuid: UUID;
      session_id: string;
      duration_ms: number;
      duration_api_ms: number;
      is_error: boolean;
      num_turns: number;
      total_cost_usd: number;
      usage: NonNullableUsage;
      modelUsage: { [modelName: string]: ModelUsage };
      permission_denials: SDKPermissionDenial[];
      errors: string[];
    }""",
    )

    # SDKSystemMessage
    writer.create_sdk_message(
        name="SDKSystemMessage",
        description="System initialization message.",
        message_type="system",
        definition="""type SDKSystemMessage = {
  type: 'system';
  subtype: 'init';
  uuid: UUID;
  session_id: string;
  apiKeySource: ApiKeySource;
  cwd: string;
  tools: string[];
  mcp_servers: { name: string; status: string; }[];
  model: string;
  permissionMode: PermissionMode;
  slash_commands: string[];
  output_style: string;
}""",
    )

    # SDKPartialAssistantMessage
    writer.create_sdk_message(
        name="SDKPartialAssistantMessage",
        description="Streaming partial message (only when includePartialMessages is true).",
        message_type="stream",
        definition="""type SDKPartialAssistantMessage = {
  type: 'stream_event';
  event: RawMessageStreamEvent;
  parent_tool_use_id: string | null;
  uuid: UUID;
  session_id: string;
}""",
    )

    # SDKCompactBoundaryMessage
    writer.create_sdk_message(
        name="SDKCompactBoundaryMessage",
        description="Message indicating a conversation compaction boundary.",
        message_type="system",
        definition="""type SDKCompactBoundaryMessage = {
  type: 'system';
  subtype: 'compact_boundary';
  uuid: UUID;
  session_id: string;
  compact_metadata: {
    trigger: 'manual' | 'auto';
    pre_tokens: number;
  };
}""",
    )

    # SDKPermissionDenial
    writer.create_sdk_type(
        name="SDKPermissionDenial",
        description="Information about a denied tool use.",
        definition="""type SDKPermissionDenial = {
  tool_name: string;
  tool_use_id: string;
  tool_input: ToolInput;
}""",
        category="message",
        properties=[
            {"name": "tool_name", "type": "string"},
            {"name": "tool_use_id", "type": "string"},
            {"name": "tool_input", "type": "ToolInput"},
        ],
    )


def populate_hook_types(writer: SDKDocsNeo4jWriter):
    """Create hook event types."""

    # HookEvent enum
    writer.create_sdk_type(
        name="HookEvent",
        description="Available hook events.",
        definition="""type HookEvent =
  | 'PreToolUse'
  | 'PostToolUse'
  | 'PostToolUseFailure'
  | 'Notification'
  | 'UserPromptSubmit'
  | 'SessionStart'
  | 'SessionEnd'
  | 'Stop'
  | 'SubagentStart'
  | 'SubagentStop'
  | 'PreCompact'
  | 'PermissionRequest';""",
        category="hook",
        properties=[],
    )

    # Create enum values
    hook_events = [
        "PreToolUse", "PostToolUse", "PostToolUseFailure", "Notification",
        "UserPromptSubmit", "SessionStart", "SessionEnd", "Stop",
        "SubagentStart", "SubagentStop", "PreCompact", "PermissionRequest"
    ]
    for event in hook_events:
        writer.create_enum_value("HookEvent", event)

    # HookCallback
    writer.create_sdk_type(
        name="HookCallback",
        description="Hook callback function type.",
        definition="""type HookCallback = (
  input: HookInput,
  toolUseID: string | undefined,
  options: { signal: AbortSignal }
) => Promise<HookJSONOutput>;""",
        category="hook",
        properties=[],
    )

    # HookCallbackMatcher
    writer.create_sdk_type(
        name="HookCallbackMatcher",
        description="Hook configuration with optional matcher.",
        definition="""interface HookCallbackMatcher {
  matcher?: string;
  hooks: HookCallback[];
  timeout?: number;
}""",
        category="hook",
        properties=[
            {"name": "matcher", "type": "string", "required": False, "description": "Pattern to match"},
            {"name": "hooks", "type": "HookCallback[]", "required": True, "description": "Array of hook callbacks"},
            {"name": "timeout", "type": "number", "required": False, "description": "Timeout in seconds (default: 60)"},
        ],
    )

    # HookInput union
    writer.create_sdk_type(
        name="HookInput",
        description="Union type of all hook input types.",
        definition="""type HookInput =
  | PreToolUseHookInput
  | PostToolUseHookInput
  | PostToolUseFailureHookInput
  | NotificationHookInput
  | UserPromptSubmitHookInput
  | SessionStartHookInput
  | SessionEndHookInput
  | StopHookInput
  | SubagentStartHookInput
  | SubagentStopHookInput
  | PreCompactHookInput
  | PermissionRequestHookInput;""",
        category="hook",
        properties=[],
    )

    # BaseHookInput
    writer.create_sdk_type(
        name="BaseHookInput",
        description="Base interface that all hook input types extend.",
        definition="""type BaseHookInput = {
  session_id: string;
  transcript_path: string;
  cwd: string;
  permission_mode?: string;
}""",
        category="hook",
        properties=[
            {"name": "session_id", "type": "string"},
            {"name": "transcript_path", "type": "string"},
            {"name": "cwd", "type": "string"},
            {"name": "permission_mode", "type": "string", "required": False},
        ],
    )

    # Individual hook input types
    hook_input_types = [
        ("PreToolUseHookInput", "PreToolUse hook input.", [
            {"name": "hook_event_name", "type": "'PreToolUse'"},
            {"name": "tool_name", "type": "string"},
            {"name": "tool_input", "type": "ToolInput"},
        ]),
        ("PostToolUseHookInput", "PostToolUse hook input.", [
            {"name": "hook_event_name", "type": "'PostToolUse'"},
            {"name": "tool_name", "type": "string"},
            {"name": "tool_input", "type": "ToolInput"},
            {"name": "tool_response", "type": "ToolOutput"},
            {"name": "tool_use_id", "type": "string"},
        ]),
        ("PostToolUseFailureHookInput", "PostToolUseFailure hook input.", [
            {"name": "hook_event_name", "type": "'PostToolUseFailure'"},
            {"name": "tool_name", "type": "string"},
            {"name": "tool_input", "type": "unknown"},
            {"name": "tool_use_id", "type": "string"},
            {"name": "error", "type": "string"},
            {"name": "is_interrupt", "type": "boolean", "required": False},
        ]),
        ("NotificationHookInput", "Notification hook input.", [
            {"name": "hook_event_name", "type": "'Notification'"},
            {"name": "message", "type": "string"},
            {"name": "title", "type": "string", "required": False},
        ]),
        ("UserPromptSubmitHookInput", "UserPromptSubmit hook input.", [
            {"name": "hook_event_name", "type": "'UserPromptSubmit'"},
            {"name": "prompt", "type": "string"},
        ]),
        ("SessionStartHookInput", "SessionStart hook input.", [
            {"name": "hook_event_name", "type": "'SessionStart'"},
            {"name": "source", "type": "'startup' | 'resume' | 'clear' | 'compact'"},
        ]),
        ("SessionEndHookInput", "SessionEnd hook input.", [
            {"name": "hook_event_name", "type": "'SessionEnd'"},
            {"name": "reason", "type": "'clear' | 'logout' | 'prompt_input_exit' | 'other'"},
        ]),
        ("StopHookInput", "Stop hook input.", [
            {"name": "hook_event_name", "type": "'Stop'"},
            {"name": "stop_hook_active", "type": "boolean"},
        ]),
        ("SubagentStartHookInput", "SubagentStart hook input.", [
            {"name": "hook_event_name", "type": "'SubagentStart'"},
            {"name": "agent_id", "type": "string"},
            {"name": "agent_type", "type": "string"},
        ]),
        ("SubagentStopHookInput", "SubagentStop hook input.", [
            {"name": "hook_event_name", "type": "'SubagentStop'"},
            {"name": "stop_hook_active", "type": "boolean"},
            {"name": "agent_id", "type": "string"},
            {"name": "agent_transcript_path", "type": "string"},
        ]),
        ("PreCompactHookInput", "PreCompact hook input.", [
            {"name": "hook_event_name", "type": "'PreCompact'"},
            {"name": "trigger", "type": "'manual' | 'auto'"},
            {"name": "custom_instructions", "type": "string | null"},
        ]),
        ("PermissionRequestHookInput", "PermissionRequest hook input.", [
            {"name": "hook_event_name", "type": "'PermissionRequest'"},
            {"name": "tool_name", "type": "string"},
            {"name": "tool_input", "type": "unknown"},
            {"name": "permission_suggestions", "type": "PermissionUpdate[]", "required": False},
        ]),
    ]

    for name, description, properties in hook_input_types:
        writer.create_sdk_type(
            name=name,
            description=description,
            definition=f"type {name} = BaseHookInput & {{ ... }}",
            category="hook",
            properties=properties,
        )

    # HookJSONOutput
    writer.create_sdk_type(
        name="HookJSONOutput",
        description="Hook return value.",
        definition="type HookJSONOutput = AsyncHookJSONOutput | SyncHookJSONOutput;",
        category="hook",
        properties=[],
    )

    # AsyncHookJSONOutput
    writer.create_sdk_type(
        name="AsyncHookJSONOutput",
        description="Async hook output for long-running operations.",
        definition="""type AsyncHookJSONOutput = {
  async: true;
  asyncTimeout?: number;
}""",
        category="hook",
        properties=[
            {"name": "async", "type": "true", "required": True},
            {"name": "asyncTimeout", "type": "number", "required": False},
        ],
    )

    # SyncHookJSONOutput
    writer.create_sdk_type(
        name="SyncHookJSONOutput",
        description="Synchronous hook output with various control options.",
        definition="""type SyncHookJSONOutput = {
  continue?: boolean;
  suppressOutput?: boolean;
  stopReason?: string;
  decision?: 'approve' | 'block';
  systemMessage?: string;
  reason?: string;
  hookSpecificOutput?: { ... };
}""",
        category="hook",
        properties=[
            {"name": "continue", "type": "boolean", "required": False},
            {"name": "suppressOutput", "type": "boolean", "required": False},
            {"name": "stopReason", "type": "string", "required": False},
            {"name": "decision", "type": "'approve' | 'block'", "required": False},
            {"name": "systemMessage", "type": "string", "required": False},
            {"name": "reason", "type": "string", "required": False},
            {"name": "hookSpecificOutput", "type": "object", "required": False},
        ],
    )


def populate_tools(writer: SDKDocsNeo4jWriter):
    """Create SDK built-in tool definitions."""

    tools = [
        {
            "name": "Task",
            "description": "Launches a new agent to handle complex, multi-step tasks autonomously.",
            "input_schema": [
                {"name": "description", "type": "string", "required": True, "description": "A short (3-5 word) description of the task"},
                {"name": "prompt", "type": "string", "required": True, "description": "The task for the agent to perform"},
                {"name": "subagent_type", "type": "string", "required": True, "description": "The type of specialized agent to use for this task"},
            ],
            "output_description": "Returns the final result from the subagent after completing the delegated task.",
        },
        {
            "name": "Bash",
            "description": "Executes bash commands in a persistent shell session with optional timeout and background execution.",
            "input_schema": [
                {"name": "command", "type": "string", "required": True, "description": "The command to execute"},
                {"name": "timeout", "type": "number", "required": False, "description": "Optional timeout in milliseconds (max 600000)"},
                {"name": "description", "type": "string", "required": False, "description": "Clear, concise description of what this command does in 5-10 words"},
                {"name": "run_in_background", "type": "boolean", "required": False, "description": "Set to true to run this command in the background"},
            ],
            "output_description": "Returns command output with exit status. Background commands return immediately with a shellId.",
        },
        {
            "name": "BashOutput",
            "description": "Retrieves output from a running or completed background bash shell.",
            "input_schema": [
                {"name": "bash_id", "type": "string", "required": True, "description": "The ID of the background shell to retrieve output from"},
                {"name": "filter", "type": "string", "required": False, "description": "Optional regex to filter output lines"},
            ],
            "output_description": "Returns incremental output from background shells.",
        },
        {
            "name": "Edit",
            "description": "Performs exact string replacements in files.",
            "input_schema": [
                {"name": "file_path", "type": "string", "required": True, "description": "The absolute path to the file to modify"},
                {"name": "old_string", "type": "string", "required": True, "description": "The text to replace"},
                {"name": "new_string", "type": "string", "required": True, "description": "The text to replace it with (must be different from old_string)"},
                {"name": "replace_all", "type": "boolean", "required": False, "description": "Replace all occurrences of old_string (default false)"},
            ],
            "output_description": "Returns confirmation of successful edits with replacement count.",
        },
        {
            "name": "Read",
            "description": "Reads files from the local filesystem, including text, images, PDFs, and Jupyter notebooks.",
            "input_schema": [
                {"name": "file_path", "type": "string", "required": True, "description": "The absolute path to the file to read"},
                {"name": "offset", "type": "number", "required": False, "description": "The line number to start reading from"},
                {"name": "limit", "type": "number", "required": False, "description": "The number of lines to read"},
            ],
            "output_description": "Returns file contents in format appropriate to file type.",
        },
        {
            "name": "Write",
            "description": "Writes a file to the local filesystem, overwriting if it exists.",
            "input_schema": [
                {"name": "file_path", "type": "string", "required": True, "description": "The absolute path to the file to write"},
                {"name": "content", "type": "string", "required": True, "description": "The content to write to the file"},
            ],
            "output_description": "Returns confirmation after successfully writing the file.",
        },
        {
            "name": "Glob",
            "description": "Fast file pattern matching that works with any codebase size.",
            "input_schema": [
                {"name": "pattern", "type": "string", "required": True, "description": "The glob pattern to match files against"},
                {"name": "path", "type": "string", "required": False, "description": "The directory to search in (defaults to cwd)"},
            ],
            "output_description": "Returns file paths matching the glob pattern, sorted by modification time.",
        },
        {
            "name": "Grep",
            "description": "Powerful search tool built on ripgrep with regex support.",
            "input_schema": [
                {"name": "pattern", "type": "string", "required": True, "description": "The regular expression pattern to search for"},
                {"name": "path", "type": "string", "required": False, "description": "File or directory to search in (defaults to cwd)"},
                {"name": "glob", "type": "string", "required": False, "description": "Glob pattern to filter files (e.g. '*.js')"},
                {"name": "type", "type": "string", "required": False, "description": "File type to search (e.g. 'js', 'py', 'rust')"},
                {"name": "output_mode", "type": "'content' | 'files_with_matches' | 'count'", "required": False, "description": "Output mode"},
                {"name": "-i", "type": "boolean", "required": False, "description": "Case insensitive search"},
                {"name": "-n", "type": "boolean", "required": False, "description": "Show line numbers (for content mode)"},
                {"name": "-B", "type": "number", "required": False, "description": "Lines to show before each match"},
                {"name": "-A", "type": "number", "required": False, "description": "Lines to show after each match"},
                {"name": "-C", "type": "number", "required": False, "description": "Lines to show before and after each match"},
                {"name": "head_limit", "type": "number", "required": False, "description": "Limit output to first N lines/entries"},
                {"name": "multiline", "type": "boolean", "required": False, "description": "Enable multiline mode"},
            ],
            "output_description": "Returns search results in the format specified by output_mode.",
        },
        {
            "name": "KillBash",
            "description": "Kills a running background bash shell by its ID.",
            "input_schema": [
                {"name": "shell_id", "type": "string", "required": True, "description": "The ID of the background shell to kill"},
            ],
            "output_description": "Returns confirmation after terminating the background shell.",
        },
        {
            "name": "NotebookEdit",
            "description": "Edits cells in Jupyter notebook files.",
            "input_schema": [
                {"name": "notebook_path", "type": "string", "required": True, "description": "The absolute path to the Jupyter notebook file"},
                {"name": "cell_id", "type": "string", "required": False, "description": "The ID of the cell to edit"},
                {"name": "new_source", "type": "string", "required": True, "description": "The new source for the cell"},
                {"name": "cell_type", "type": "'code' | 'markdown'", "required": False, "description": "The type of the cell"},
                {"name": "edit_mode", "type": "'replace' | 'insert' | 'delete'", "required": False, "description": "The type of edit"},
            ],
            "output_description": "Returns confirmation after modifying the Jupyter notebook.",
        },
        {
            "name": "WebFetch",
            "description": "Fetches content from a URL and processes it with an AI model.",
            "input_schema": [
                {"name": "url", "type": "string", "required": True, "description": "The URL to fetch content from"},
                {"name": "prompt", "type": "string", "required": True, "description": "The prompt to run on the fetched content"},
            ],
            "output_description": "Returns the AI's analysis of the fetched web content.",
        },
        {
            "name": "WebSearch",
            "description": "Searches the web and returns formatted results.",
            "input_schema": [
                {"name": "query", "type": "string", "required": True, "description": "The search query to use"},
                {"name": "allowed_domains", "type": "string[]", "required": False, "description": "Only include results from these domains"},
                {"name": "blocked_domains", "type": "string[]", "required": False, "description": "Never include results from these domains"},
            ],
            "output_description": "Returns formatted search results from the web.",
        },
        {
            "name": "TodoWrite",
            "description": "Creates and manages a structured task list for tracking progress.",
            "input_schema": [
                {"name": "todos", "type": "Array<{content: string, status: 'pending'|'in_progress'|'completed', activeForm: string}>", "required": True, "description": "The updated todo list"},
            ],
            "output_description": "Returns confirmation with current task statistics.",
        },
        {
            "name": "ExitPlanMode",
            "description": "Exits planning mode and prompts the user to approve the plan.",
            "input_schema": [
                {"name": "plan", "type": "string", "required": True, "description": "The plan to run by the user for approval"},
            ],
            "output_description": "Returns confirmation after exiting plan mode.",
        },
        {
            "name": "ListMcpResources",
            "description": "Lists available MCP resources from connected servers.",
            "input_schema": [
                {"name": "server", "type": "string", "required": False, "description": "Optional server name to filter resources by"},
            ],
            "output_description": "Returns list of available MCP resources.",
        },
        {
            "name": "ReadMcpResource",
            "description": "Reads a specific MCP resource from a server.",
            "input_schema": [
                {"name": "server", "type": "string", "required": True, "description": "The MCP server name"},
                {"name": "uri", "type": "string", "required": True, "description": "The resource URI to read"},
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
        )


def populate_other_types(writer: SDKDocsNeo4jWriter):
    """Create miscellaneous utility types."""

    # ApiKeySource
    writer.create_sdk_type(
        name="ApiKeySource",
        description="Source of API key.",
        definition="type ApiKeySource = 'user' | 'project' | 'org' | 'temporary';",
        category="other",
        properties=[],
    )

    # SdkBeta
    writer.create_sdk_type(
        name="SdkBeta",
        description="Available beta features that can be enabled via the betas option.",
        definition="type SdkBeta = 'context-1m-2025-08-07';",
        category="other",
        properties=[
            {"name": "'context-1m-2025-08-07'", "description": "Enables 1 million token context window (Claude Sonnet 4, Claude Sonnet 4.5)"},
        ],
    )

    # SlashCommand
    writer.create_sdk_type(
        name="SlashCommand",
        description="Information about an available slash command.",
        definition="""type SlashCommand = {
  name: string;
  description: string;
  argumentHint: string;
}""",
        category="other",
        properties=[
            {"name": "name", "type": "string"},
            {"name": "description", "type": "string"},
            {"name": "argumentHint", "type": "string"},
        ],
    )

    # ModelInfo
    writer.create_sdk_type(
        name="ModelInfo",
        description="Information about an available model.",
        definition="""type ModelInfo = {
  value: string;
  displayName: string;
  description: string;
}""",
        category="other",
        properties=[
            {"name": "value", "type": "string"},
            {"name": "displayName", "type": "string"},
            {"name": "description", "type": "string"},
        ],
    )

    # McpServerStatus
    writer.create_sdk_type(
        name="McpServerStatus",
        description="Status of a connected MCP server.",
        definition="""type McpServerStatus = {
  name: string;
  status: 'connected' | 'failed' | 'needs-auth' | 'pending';
  serverInfo?: { name: string; version: string; };
}""",
        category="other",
        properties=[
            {"name": "name", "type": "string"},
            {"name": "status", "type": "'connected' | 'failed' | 'needs-auth' | 'pending'"},
            {"name": "serverInfo", "type": "{ name: string; version: string; }", "required": False},
        ],
    )

    # AccountInfo
    writer.create_sdk_type(
        name="AccountInfo",
        description="Account information for the authenticated user.",
        definition="""type AccountInfo = {
  email?: string;
  organization?: string;
  subscriptionType?: string;
  tokenSource?: string;
  apiKeySource?: string;
}""",
        category="other",
        properties=[
            {"name": "email", "type": "string", "required": False},
            {"name": "organization", "type": "string", "required": False},
            {"name": "subscriptionType", "type": "string", "required": False},
            {"name": "tokenSource", "type": "string", "required": False},
            {"name": "apiKeySource", "type": "string", "required": False},
        ],
    )

    # ModelUsage
    writer.create_sdk_type(
        name="ModelUsage",
        description="Per-model usage statistics returned in result messages.",
        definition="""type ModelUsage = {
  inputTokens: number;
  outputTokens: number;
  cacheReadInputTokens: number;
  cacheCreationInputTokens: number;
  webSearchRequests: number;
  costUSD: number;
  contextWindow: number;
}""",
        category="other",
        properties=[
            {"name": "inputTokens", "type": "number"},
            {"name": "outputTokens", "type": "number"},
            {"name": "cacheReadInputTokens", "type": "number"},
            {"name": "cacheCreationInputTokens", "type": "number"},
            {"name": "webSearchRequests", "type": "number"},
            {"name": "costUSD", "type": "number"},
            {"name": "contextWindow", "type": "number"},
        ],
    )

    # ConfigScope
    writer.create_sdk_type(
        name="ConfigScope",
        description="Configuration scope.",
        definition="type ConfigScope = 'local' | 'user' | 'project';",
        category="other",
        properties=[],
    )

    # NonNullableUsage
    writer.create_sdk_type(
        name="NonNullableUsage",
        description="A version of Usage with all nullable fields made non-nullable.",
        definition="type NonNullableUsage = { [K in keyof Usage]: NonNullable<Usage[K]>; }",
        category="other",
        properties=[],
    )

    # Usage
    writer.create_sdk_type(
        name="Usage",
        description="Token usage statistics (from @anthropic-ai/sdk).",
        definition="""type Usage = {
  input_tokens: number | null;
  output_tokens: number | null;
  cache_creation_input_tokens?: number | null;
  cache_read_input_tokens?: number | null;
}""",
        category="other",
        properties=[
            {"name": "input_tokens", "type": "number | null"},
            {"name": "output_tokens", "type": "number | null"},
            {"name": "cache_creation_input_tokens", "type": "number | null", "required": False},
            {"name": "cache_read_input_tokens", "type": "number | null", "required": False},
        ],
    )

    # CallToolResult
    writer.create_sdk_type(
        name="CallToolResult",
        description="MCP tool result type (from @modelcontextprotocol/sdk/types.js).",
        definition="""type CallToolResult = {
  content: Array<{ type: 'text' | 'image' | 'resource'; ... }>;
  isError?: boolean;
}""",
        category="other",
        properties=[
            {"name": "content", "type": "Array<{type: 'text' | 'image' | 'resource', ...}>"},
            {"name": "isError", "type": "boolean", "required": False},
        ],
    )

    # AbortError
    writer.create_sdk_type(
        name="AbortError",
        description="Custom error class for abort operations.",
        definition="class AbortError extends Error {}",
        category="other",
        properties=[],
    )

    # SdkPluginConfig
    writer.create_sdk_type(
        name="SdkPluginConfig",
        description="Configuration for loading plugins in the SDK.",
        definition="""type SdkPluginConfig = {
  type: 'local';
  path: string;
}""",
        category="options",
        properties=[
            {"name": "type", "type": "'local'", "required": True, "description": "Must be 'local' (only local plugins currently supported)"},
            {"name": "path", "type": "string", "required": True, "description": "Absolute or relative path to the plugin directory"},
        ],
    )


def create_relationships(writer: SDKDocsNeo4jWriter):
    """Create relationships between SDK components."""

    # Function relationships
    writer.create_function_returns("query", "Query")
    writer.create_function_accepts("query", "Options")

    # Type references
    type_references = [
        ("Options", "AgentDefinition", "REFERENCES"),
        ("Options", "CanUseTool", "REFERENCES"),
        ("Options", "HookEvent", "REFERENCES"),
        ("Options", "HookCallbackMatcher", "REFERENCES"),
        ("Options", "McpServerConfig", "REFERENCES"),
        ("Options", "PermissionMode", "REFERENCES"),
        ("Options", "SandboxSettings", "REFERENCES"),
        ("Options", "SettingSource", "REFERENCES"),
        ("Options", "SdkBeta", "REFERENCES"),
        ("Options", "SdkPluginConfig", "REFERENCES"),
        ("Query", "SDKMessage", "YIELDS"),
        ("Query", "SlashCommand", "REFERENCES"),
        ("Query", "ModelInfo", "REFERENCES"),
        ("Query", "McpServerStatus", "REFERENCES"),
        ("Query", "AccountInfo", "REFERENCES"),
        ("Query", "PermissionMode", "REFERENCES"),
        ("CanUseTool", "PermissionResult", "RETURNS"),
        ("CanUseTool", "PermissionUpdate", "REFERENCES"),
        ("PermissionResult", "PermissionUpdate", "REFERENCES"),
        ("SDKResultMessage", "NonNullableUsage", "REFERENCES"),
        ("SDKResultMessage", "ModelUsage", "REFERENCES"),
        ("SDKResultMessage", "SDKPermissionDenial", "REFERENCES"),
        ("NonNullableUsage", "Usage", "EXTENDS"),
        ("HookJSONOutput", "AsyncHookJSONOutput", "INCLUDES"),
        ("HookJSONOutput", "SyncHookJSONOutput", "INCLUDES"),
        ("HookInput", "BaseHookInput", "EXTENDS"),
        ("SandboxSettings", "NetworkSandboxSettings", "REFERENCES"),
        ("SandboxSettings", "SandboxIgnoreViolations", "REFERENCES"),
    ]

    for from_type, to_type, rel in type_references:
        writer.create_type_reference(from_type, to_type, rel)

    # Message union members
    message_members = [
        "SDKAssistantMessage", "SDKUserMessage", "SDKUserMessageReplay",
        "SDKResultMessage", "SDKSystemMessage", "SDKPartialAssistantMessage",
        "SDKCompactBoundaryMessage"
    ]
    for msg in message_members:
        writer.create_message_in_union(msg, "SDKMessage")

    # Hook input type relationships
    hook_input_types = [
        "PreToolUseHookInput", "PostToolUseHookInput", "PostToolUseFailureHookInput",
        "NotificationHookInput", "UserPromptSubmitHookInput", "SessionStartHookInput",
        "SessionEndHookInput", "StopHookInput", "SubagentStartHookInput",
        "SubagentStopHookInput", "PreCompactHookInput", "PermissionRequestHookInput"
    ]
    for hook_type in hook_input_types:
        writer.create_type_reference(hook_type, "BaseHookInput", "EXTENDS")
        writer.create_type_reference("HookInput", hook_type, "INCLUDES")


def main():
    """Main function to populate SDK documentation."""
    print("Connecting to Neo4j...")

    try:
        with SDKDocsNeo4jWriter() as writer:
            print("Creating indexes...")
            writer.create_index_constraints()

            print("Clearing existing SDK documentation...")
            writer.clear_sdk_docs()

            print("Populating functions...")
            populate_functions(writer)

            print("Populating Options type...")
            populate_options_type(writer)

            print("Populating Query type...")
            populate_query_type(writer)

            print("Populating AgentDefinition type...")
            populate_agent_definition(writer)

            print("Populating SettingSource type...")
            populate_setting_source(writer)

            print("Populating permission types...")
            populate_permission_types(writer)

            print("Populating MCP types...")
            populate_mcp_types(writer)

            print("Populating sandbox types...")
            populate_sandbox_types(writer)

            print("Populating message types...")
            populate_message_types(writer)

            print("Populating hook types...")
            populate_hook_types(writer)

            print("Populating tools...")
            populate_tools(writer)

            print("Populating other types...")
            populate_other_types(writer)

            print("Creating relationships...")
            create_relationships(writer)

            print("\nSDK documentation successfully imported to Neo4j!")
            print("\nExample queries:")
            print("  // Find all SDK functions")
            print("  MATCH (f:SDKFunction) RETURN f.name, f.description")
            print("")
            print("  // Find all tools")
            print("  MATCH (t:SDKTool) RETURN t.name, t.description")
            print("")
            print("  // Find types in a category")
            print("  MATCH (t:SDKType {category: 'hook'}) RETURN t.name")
            print("")
            print("  // Find relationships")
            print("  MATCH (a)-[r]->(b) WHERE a:SDKType OR a:SDKFunction RETURN a.name, type(r), b.name LIMIT 50")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
