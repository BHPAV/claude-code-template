"""
Neo4j write operations for Agent SDK documentation.

Creates a knowledge graph of SDK types, functions, and relationships.
"""

import json
from neo4j import GraphDatabase
from config import load_neo4j_config


class SDKDocsNeo4jWriter:
    """Writes Agent SDK documentation to Neo4j as a knowledge graph."""

    def __init__(self):
        self.config = load_neo4j_config()
        self.database = self.config.database
        self.driver = GraphDatabase.driver(
            self.config.uri,
            auth=(self.config.user, self.config.password),
            connection_timeout=5.0,
            max_connection_lifetime=30.0,
        )

    def _with_database(self, query: str) -> str:
        """Prepend USE database statement to query."""
        return f"USE {self.database}\n{query}"

    def close(self):
        """Close driver connection."""
        if self.driver:
            self.driver.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def create_sdk_function(
        self,
        name: str,
        description: str,
        signature: str,
        parameters: list[dict] | None = None,
        returns: str | None = None,
        example_code: str | None = None,
        sdk: str = "typescript",
        package: str = "@anthropic-ai/claude-agent-sdk",
    ) -> str:
        """
        Create an SDKFunction node.

        Args:
            name: Function name (e.g., 'query', 'tool')
            description: Function description
            signature: Function signature
            parameters: List of parameter dicts with name, type, description
            returns: Return type description
            example_code: Optional example code
            sdk: SDK language ('typescript' or 'python')
            package: Package name

        Returns:
            str: Node ID
        """
        node_id = f"sdk_function:{sdk}:{name}"

        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MERGE (f:SDKFunction {id: $id})
                    SET f.name = $name,
                        f.description = $description,
                        f.signature = $signature,
                        f.parameters = $parameters,
                        f.returns = $returns,
                        f.example_code = $example_code,
                        f.sdk = $sdk,
                        f.package = $package
                    """),
                    {
                        "id": node_id,
                        "name": name,
                        "description": description,
                        "signature": signature,
                        "parameters": json.dumps(parameters or []),
                        "returns": returns,
                        "example_code": example_code,
                        "sdk": sdk,
                        "package": package,
                    },
                )
            )

        return node_id

    def create_sdk_type(
        self,
        name: str,
        description: str,
        definition: str,
        category: str,
        properties: list[dict] | None = None,
        sdk: str = "typescript",
        package: str = "@anthropic-ai/claude-agent-sdk",
    ) -> str:
        """
        Create an SDKType node.

        Args:
            name: Type name (e.g., 'Options', 'Query')
            description: Type description
            definition: Full type definition
            category: Category (options, message, hook, etc.)
            properties: List of property dicts
            sdk: SDK language ('typescript' or 'python')
            package: Package name

        Returns:
            str: Node ID
        """
        node_id = f"sdk_type:{sdk}:{name}"

        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MERGE (t:SDKType {id: $id})
                    SET t.name = $name,
                        t.description = $description,
                        t.definition = $definition,
                        t.category = $category,
                        t.properties = $properties,
                        t.sdk = $sdk,
                        t.package = $package
                    """),
                    {
                        "id": node_id,
                        "name": name,
                        "description": description,
                        "definition": definition,
                        "category": category,
                        "properties": json.dumps(properties or []),
                        "sdk": sdk,
                        "package": package,
                    },
                )
            )

        return node_id

    def create_sdk_tool(
        self,
        tool_name: str,
        description: str,
        input_schema: list[dict],
        output_schema: list[dict] | None = None,
        output_description: str | None = None,
        sdk: str = "typescript",
        package: str = "@anthropic-ai/claude-agent-sdk",
    ) -> str:
        """
        Create an SDKTool node with input and output schemas.

        Args:
            tool_name: Tool name (e.g., 'Bash', 'Read', 'Write')
            description: Tool description
            input_schema: List of input property dicts
            output_schema: List of output property dicts
            output_description: Description of the output
            sdk: SDK language ('typescript' or 'python')
            package: Package name

        Returns:
            str: Node ID
        """
        node_id = f"sdk_tool:{sdk}:{tool_name}"

        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MERGE (tool:SDKTool {id: $id})
                    SET tool.name = $name,
                        tool.description = $description,
                        tool.input_schema = $input_schema,
                        tool.output_schema = $output_schema,
                        tool.output_description = $output_description,
                        tool.sdk = $sdk,
                        tool.package = $package
                    """),
                    {
                        "id": node_id,
                        "name": tool_name,
                        "description": description,
                        "input_schema": json.dumps(input_schema),
                        "output_schema": json.dumps(output_schema or []),
                        "output_description": output_description,
                        "sdk": sdk,
                        "package": package,
                    },
                )
            )

        return node_id

    def create_sdk_hook_event(
        self,
        name: str,
        description: str,
        input_type_name: str,
        input_fields: list[dict],
        sdk: str = "typescript",
        package: str = "@anthropic-ai/claude-agent-sdk",
    ) -> str:
        """
        Create an SDKHookEvent node.

        Args:
            name: Event name (e.g., 'PreToolUse', 'PostToolUse')
            description: Event description
            input_type_name: Name of the input type
            input_fields: List of input field dicts
            sdk: SDK language ('typescript' or 'python')
            package: Package name

        Returns:
            str: Node ID
        """
        node_id = f"sdk_hook_event:{sdk}:{name}"

        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MERGE (h:SDKHookEvent {id: $id})
                    SET h.name = $name,
                        h.description = $description,
                        h.input_type_name = $input_type_name,
                        h.input_fields = $input_fields,
                        h.sdk = $sdk,
                        h.package = $package
                    """),
                    {
                        "id": node_id,
                        "name": name,
                        "description": description,
                        "input_type_name": input_type_name,
                        "input_fields": json.dumps(input_fields),
                        "sdk": sdk,
                        "package": package,
                    },
                )
            )

        return node_id

    def create_sdk_message(
        self,
        name: str,
        description: str,
        message_type: str,
        definition: str,
        sdk: str = "typescript",
        package: str = "@anthropic-ai/claude-agent-sdk",
    ) -> str:
        """
        Create an SDKMessage node.

        Args:
            name: Message type name (e.g., 'SDKAssistantMessage')
            description: Message description
            message_type: Type indicator (assistant, user, result, system)
            definition: Full type definition
            sdk: SDK language ('typescript' or 'python')
            package: Package name

        Returns:
            str: Node ID
        """
        node_id = f"sdk_message:{sdk}:{name}"

        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MERGE (m:SDKMessage {id: $id})
                    SET m.name = $name,
                        m.description = $description,
                        m.message_type = $message_type,
                        m.definition = $definition,
                        m.sdk = $sdk,
                        m.package = $package
                    """),
                    {
                        "id": node_id,
                        "name": name,
                        "description": description,
                        "message_type": message_type,
                        "definition": definition,
                        "sdk": sdk,
                        "package": package,
                    },
                )
            )

        return node_id

    def create_type_reference(
        self, from_type: str, to_type: str, relationship: str = "REFERENCES", sdk: str = "typescript"
    ):
        """
        Create a relationship between types.

        Args:
            from_type: Source type name
            to_type: Target type name
            relationship: Relationship type (REFERENCES, EXTENDS, CONTAINS, etc.)
            sdk: SDK language ('typescript' or 'python')
        """
        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database(f"""
                    MATCH (from:SDKType {{name: $from_type, sdk: $sdk}})
                    MATCH (to:SDKType {{name: $to_type, sdk: $sdk}})
                    MERGE (from)-[:{relationship}]->(to)
                    """),
                    {
                        "from_type": from_type,
                        "to_type": to_type,
                        "sdk": sdk,
                    },
                )
            )

    def create_function_returns(self, function_name: str, type_name: str, sdk: str = "typescript"):
        """Link a function to its return type."""
        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MATCH (f:SDKFunction {name: $function_name, sdk: $sdk})
                    MATCH (t:SDKType {name: $type_name, sdk: $sdk})
                    MERGE (f)-[:RETURNS]->(t)
                    """),
                    {
                        "function_name": function_name,
                        "type_name": type_name,
                        "sdk": sdk,
                    },
                )
            )

    def create_function_accepts(self, function_name: str, type_name: str, sdk: str = "typescript"):
        """Link a function to a type it accepts as parameter."""
        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MATCH (f:SDKFunction {name: $function_name, sdk: $sdk})
                    MATCH (t:SDKType {name: $type_name, sdk: $sdk})
                    MERGE (f)-[:ACCEPTS]->(t)
                    """),
                    {
                        "function_name": function_name,
                        "type_name": type_name,
                        "sdk": sdk,
                    },
                )
            )

    def create_tool_uses_type(self, tool_name: str, type_name: str, direction: str, sdk: str = "typescript"):
        """
        Link a tool to its input or output type.

        Args:
            tool_name: Tool name
            type_name: Type name
            direction: 'input' or 'output'
            sdk: SDK language ('typescript' or 'python')
        """
        rel_type = "USES_INPUT" if direction == "input" else "PRODUCES_OUTPUT"

        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database(f"""
                    MATCH (tool:SDKTool {{name: $tool_name, sdk: $sdk}})
                    MATCH (t:SDKType {{name: $type_name, sdk: $sdk}})
                    MERGE (tool)-[:{rel_type}]->(t)
                    """),
                    {
                        "tool_name": tool_name,
                        "type_name": type_name,
                        "sdk": sdk,
                    },
                )
            )

    def create_hook_uses_type(self, hook_name: str, type_name: str, direction: str, sdk: str = "typescript"):
        """
        Link a hook event to its input or output type.

        Args:
            hook_name: Hook event name
            type_name: Type name
            direction: 'input' or 'output'
            sdk: SDK language ('typescript' or 'python')
        """
        rel_type = "RECEIVES" if direction == "input" else "RETURNS"

        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database(f"""
                    MATCH (h:SDKHookEvent {{name: $hook_name, sdk: $sdk}})
                    MATCH (t:SDKType {{name: $type_name, sdk: $sdk}})
                    MERGE (h)-[:{rel_type}]->(t)
                    """),
                    {
                        "hook_name": hook_name,
                        "type_name": type_name,
                        "sdk": sdk,
                    },
                )
            )

    def create_message_in_union(self, message_name: str, union_name: str, sdk: str = "typescript"):
        """Link a message type to the union it belongs to."""
        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MATCH (m:SDKMessage {name: $message_name, sdk: $sdk})
                    MATCH (u:SDKType {name: $union_name, sdk: $sdk})
                    MERGE (m)-[:MEMBER_OF]->(u)
                    """),
                    {
                        "message_name": message_name,
                        "union_name": union_name,
                        "sdk": sdk,
                    },
                )
            )

    def create_enum_value(
        self, parent_type: str, value: str, description: str | None = None, sdk: str = "typescript"
    ):
        """
        Create an SDKEnumValue node for union/enum types.

        Args:
            parent_type: Parent type name
            value: Enum/union value
            description: Optional description
            sdk: SDK language ('typescript' or 'python')
        """
        node_id = f"sdk_enum:{sdk}:{parent_type}:{value}"

        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MERGE (e:SDKEnumValue {id: $id})
                    SET e.parent_type = $parent_type,
                        e.value = $value,
                        e.description = $description,
                        e.sdk = $sdk
                    WITH e
                    MATCH (t:SDKType {name: $parent_type, sdk: $sdk})
                    MERGE (e)-[:VALUE_OF]->(t)
                    """),
                    {
                        "id": node_id,
                        "parent_type": parent_type,
                        "value": value,
                        "description": description,
                        "sdk": sdk,
                    },
                )
            )

    def create_sdk_config(
        self,
        name: str,
        description: str,
        config_type: str,
        definition: str,
        properties: list[dict] | None = None,
        sdk: str = "typescript",
        package: str = "@anthropic-ai/claude-agent-sdk",
    ) -> str:
        """
        Create an SDKConfig node for MCP server configs, sandbox settings, etc.

        Args:
            name: Config type name
            description: Description
            config_type: Category (mcp, sandbox, permission)
            definition: Type definition
            properties: List of property dicts
            sdk: SDK language ('typescript' or 'python')
            package: Package name

        Returns:
            str: Node ID
        """
        node_id = f"sdk_config:{sdk}:{name}"

        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MERGE (c:SDKConfig {id: $id})
                    SET c.name = $name,
                        c.description = $description,
                        c.config_type = $config_type,
                        c.definition = $definition,
                        c.properties = $properties,
                        c.sdk = $sdk,
                        c.package = $package
                    """),
                    {
                        "id": node_id,
                        "name": name,
                        "description": description,
                        "config_type": config_type,
                        "definition": definition,
                        "properties": json.dumps(properties or []),
                        "sdk": sdk,
                        "package": package,
                    },
                )
            )

        return node_id

    def create_sdk_class(
        self,
        name: str,
        description: str,
        definition: str,
        methods: list[dict] | None = None,
        properties: list[dict] | None = None,
        sdk: str = "python",
        package: str = "claude-agent-sdk",
    ) -> str:
        """
        Create an SDKClass node (primarily for Python SDK).

        Args:
            name: Class name (e.g., 'ClaudeSDKClient')
            description: Class description
            definition: Class definition/signature
            methods: List of method dicts with name, description, signature
            properties: List of property dicts
            sdk: SDK language
            package: Package name

        Returns:
            str: Node ID
        """
        node_id = f"sdk_class:{sdk}:{name}"

        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MERGE (c:SDKClass {id: $id})
                    SET c.name = $name,
                        c.description = $description,
                        c.definition = $definition,
                        c.methods = $methods,
                        c.properties = $properties,
                        c.sdk = $sdk,
                        c.package = $package
                    """),
                    {
                        "id": node_id,
                        "name": name,
                        "description": description,
                        "definition": definition,
                        "methods": json.dumps(methods or []),
                        "properties": json.dumps(properties or []),
                        "sdk": sdk,
                        "package": package,
                    },
                )
            )

        return node_id

    def create_sdk_error(
        self,
        name: str,
        description: str,
        definition: str,
        parent_class: str | None = None,
        sdk: str = "python",
        package: str = "claude-agent-sdk",
    ) -> str:
        """
        Create an SDKError node for exception classes.

        Args:
            name: Error class name
            description: Error description
            definition: Class definition
            parent_class: Parent exception class name
            sdk: SDK language
            package: Package name

        Returns:
            str: Node ID
        """
        node_id = f"sdk_error:{sdk}:{name}"

        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database("""
                    MERGE (e:SDKError {id: $id})
                    SET e.name = $name,
                        e.description = $description,
                        e.definition = $definition,
                        e.parent_class = $parent_class,
                        e.sdk = $sdk,
                        e.package = $package
                    """),
                    {
                        "id": node_id,
                        "name": name,
                        "description": description,
                        "definition": definition,
                        "parent_class": parent_class,
                        "sdk": sdk,
                        "package": package,
                    },
                )
            )

        return node_id

    def create_index_constraints(self):
        """Create indexes and constraints for SDK documentation nodes."""
        indexes = [
            "CREATE INDEX sdk_function_name IF NOT EXISTS FOR (f:SDKFunction) ON (f.name)",
            "CREATE INDEX sdk_function_sdk IF NOT EXISTS FOR (f:SDKFunction) ON (f.sdk)",
            "CREATE INDEX sdk_type_name IF NOT EXISTS FOR (t:SDKType) ON (t.name)",
            "CREATE INDEX sdk_type_sdk IF NOT EXISTS FOR (t:SDKType) ON (t.sdk)",
            "CREATE INDEX sdk_type_category IF NOT EXISTS FOR (t:SDKType) ON (t.category)",
            "CREATE INDEX sdk_tool_name IF NOT EXISTS FOR (tool:SDKTool) ON (tool.name)",
            "CREATE INDEX sdk_tool_sdk IF NOT EXISTS FOR (tool:SDKTool) ON (tool.sdk)",
            "CREATE INDEX sdk_hook_name IF NOT EXISTS FOR (h:SDKHookEvent) ON (h.name)",
            "CREATE INDEX sdk_hook_sdk IF NOT EXISTS FOR (h:SDKHookEvent) ON (h.sdk)",
            "CREATE INDEX sdk_message_name IF NOT EXISTS FOR (m:SDKMessage) ON (m.name)",
            "CREATE INDEX sdk_message_sdk IF NOT EXISTS FOR (m:SDKMessage) ON (m.sdk)",
            "CREATE INDEX sdk_config_name IF NOT EXISTS FOR (c:SDKConfig) ON (c.name)",
            "CREATE INDEX sdk_config_sdk IF NOT EXISTS FOR (c:SDKConfig) ON (c.sdk)",
            "CREATE INDEX sdk_enum_parent IF NOT EXISTS FOR (e:SDKEnumValue) ON (e.parent_type)",
            "CREATE INDEX sdk_enum_sdk IF NOT EXISTS FOR (e:SDKEnumValue) ON (e.sdk)",
            "CREATE INDEX sdk_class_name IF NOT EXISTS FOR (c:SDKClass) ON (c.name)",
            "CREATE INDEX sdk_class_sdk IF NOT EXISTS FOR (c:SDKClass) ON (c.sdk)",
            "CREATE INDEX sdk_error_name IF NOT EXISTS FOR (e:SDKError) ON (e.name)",
            "CREATE INDEX sdk_error_sdk IF NOT EXISTS FOR (e:SDKError) ON (e.sdk)",
        ]

        with self.driver.session() as session:
            for index_query in indexes:
                try:
                    session.run(self._with_database(index_query))
                except Exception:
                    pass  # Index may already exist

    def clear_sdk_docs(self, sdk: str | None = None):
        """
        Remove SDK documentation nodes.

        Args:
            sdk: If provided, only remove nodes for this SDK ('typescript' or 'python').
                 If None, removes all SDK documentation nodes.
        """
        if sdk:
            where_clause = f"AND n.sdk = '{sdk}'"
        else:
            where_clause = ""

        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    self._with_database(f"""
                    MATCH (n)
                    WHERE (n:SDKFunction OR n:SDKType OR n:SDKTool
                       OR n:SDKHookEvent OR n:SDKMessage OR n:SDKConfig
                       OR n:SDKEnumValue OR n:SDKClass OR n:SDKError)
                    {where_clause}
                    DETACH DELETE n
                    """)
                )
            )
