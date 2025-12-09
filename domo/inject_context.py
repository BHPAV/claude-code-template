#!/usr/bin/env python3
"""
inject_context.py - Inject homelab context into AI assistant sessions.

Usage:
    python inject_context.py                    # Print medium-level context
    python inject_context.py --level full       # Print full context
    python inject_context.py --level minimal    # Print minimal context
    python inject_context.py --machine-only     # Print only machine prompt
    python inject_context.py --spec-only        # Print only environment spec
    python inject_context.py --json             # Output as JSON

This script is designed to inject homelab environment context into
Claude Code CLI sessions or other AI assistants.
"""

import argparse
import json
import sys
from pathlib import Path

# Add domo directory to path
sys.path.insert(0, str(Path(__file__).parent))

from domo_env import DomoEnv


def get_session_context(spec_level: str = 'medium',
                        machine_only: bool = False,
                        spec_only: bool = False) -> str:
    """Get session context with environment spec.

    Args:
        spec_level: 'full', 'medium', or 'minimal'
        machine_only: If True, return only machine prompt
        spec_only: If True, return only environment spec

    Returns:
        str: Context string for injection
    """
    env = DomoEnv()

    if machine_only:
        return env.get_machine_prompt()

    if spec_only:
        return env.get_spec(spec_level)

    return env.get_full_context(spec_level)


def get_context_as_json(spec_level: str = 'medium') -> dict:
    """Get session context as structured JSON.

    Args:
        spec_level: 'full', 'medium', or 'minimal'

    Returns:
        dict: Structured context data
    """
    env = DomoEnv()
    info = env.machine_info

    return {
        "machine": {
            "machine_id": info.machine_id,
            "hostname": info.hostname,
            "role": info.role,
            "vlans": info.vlans,
            "local_ips": info.local_ips,
            "gpu": info.gpu,
            "detection_method": info.detection_method,
        },
        "config": {
            "neo4j_uri": env.config.neo4j_uri,
            "neo4j_database": env.config.neo4j_database,
            "neo4j_available": env.neo4j_available,
            "nas_host": env.config.nas_host,
            "agent_bus_path": env.config.agent_bus_path,
            "agent_bus_available": env.agent_bus_available,
        },
        "context": {
            "machine_prompt": env.get_machine_prompt(),
            "spec_level": spec_level,
            "spec_content": env.get_spec(spec_level),
        }
    }


def main():
    parser = argparse.ArgumentParser(
        description="Inject homelab context into AI assistant sessions",
        prog="inject-context"
    )
    parser.add_argument(
        "--level", "-l",
        choices=['full', 'medium', 'minimal'],
        default='medium',
        help="Compression level for environment spec (default: medium)"
    )
    parser.add_argument(
        "--machine-only", "-m",
        action="store_true",
        help="Output only machine prompt, no environment spec"
    )
    parser.add_argument(
        "--spec-only", "-s",
        action="store_true",
        help="Output only environment spec, no machine prompt"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output as JSON instead of markdown"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress machine detection output to stderr"
    )

    args = parser.parse_args()

    # Get environment info
    env = DomoEnv()

    if not args.quiet:
        print(f"[inject-context] Detected machine: {env.machine_id} "
              f"(via {env.machine_info.detection_method})", file=sys.stderr)

    if args.json:
        output = get_context_as_json(args.level)
        print(json.dumps(output, indent=2))
    else:
        output = get_session_context(
            spec_level=args.level,
            machine_only=args.machine_only,
            spec_only=args.spec_only
        )
        print(output)


if __name__ == "__main__":
    main()
