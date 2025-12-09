#!/usr/bin/env python3
"""
Claude Code UserPromptSubmit hook handler.

Logs user prompts to Neo4j.

Usage (configured in .claude/settings.local.json):
    python claude_code_hooks/prompt_hooks.py < hook_data.json
"""

import sys
import json
from datetime import datetime

# Import from same directory (all hook files are in .claude/hooks/)
from models import CLIPromptEvent
from neo4j_writer import CLINeo4jWriter
from config import is_neo4j_available


def handle_user_prompt_submit(hook_data: dict):
    """Handle UserPromptSubmit event."""
    session_id = hook_data.get("sessionId", "unknown")
    prompt_text = hook_data.get("prompt", "")

    event = CLIPromptEvent(
        session_id=session_id, prompt_text=prompt_text, timestamp=datetime.now()
    )

    if is_neo4j_available():
        try:
            with CLINeo4jWriter() as writer:
                writer.create_prompt_node(event)
        except Exception as e:
            print(f"[CLI Hook] Failed to log prompt: {e}", file=sys.stderr)


def main():
    """Main entry point for hook script."""
    try:
        hook_data = json.load(sys.stdin)
        handle_user_prompt_submit(hook_data)
    except Exception as e:
        print(f"[CLI Hook] Error: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
