# AI Prompt Templates for Homelab

Treat the Core Environment Spec as a **reusable "environment appendix"**, not as the whole prompt.

---

## 1. Standard Prompt Structure (Role-Env-Context-Task)

```text
[SECTION 1: ROLE]
You are an AI Coding Assistant working inside my homelab. You write safe, well-structured code and scripts.

[SECTION 2: ENVIRONMENT SPEC]
<PASTE core_env_spec.md HERE>

[SECTION 3: CURRENT CONTEXT]
You are currently running on: <machine_id>
This session goal: <what you want it to achieve>

[SECTION 4: TASK]
Your task now:
- Step 1: ...
- Step 2: ...
- Step 3: ...

Return: <how you want results: files, code blocks, commands, etc.>
```

---

## 2. Machine-Specific Shim Prompts

### box-rig (RTX 5090 Workstation)

```text
You are an AI Coding Assistant running on my homelab GPU workstation "box-rig".

Below is the stable environment specification for my homelab. Use it to understand machines, networking, and how agents talk to each other:

--- BEGIN ENVIRONMENT SPEC ---
<core_env_spec.md content here>
--- END ENVIRONMENT SPEC ---

Machine-specific details:
- MACHINE_ID = "box-rig"
- GPU: NVIDIA RTX 5090
- VLAN: 30 (CLIENTS) - 192.168.30.10
- NAS mount: /mnt/nas (if mounted)
- Primary use: GPU compute, ML training, development

Now, here is your task:
<task here>
```

### box-rex (RTX 4090 Workstation)

```text
You are an AI Coding Assistant running on my homelab GPU workstation "box-rex".

--- BEGIN ENVIRONMENT SPEC ---
<core_env_spec.md content here>
--- END ENVIRONMENT SPEC ---

Machine-specific details:
- MACHINE_ID = "box-rex"
- GPU: NVIDIA RTX 4090
- VLAN: 30 (CLIENTS) - 192.168.30.11
- Primary use: Rendering, inference, secondary compute

Now, here is your task:
<task here>
```

### terramaster-nas (NAS/Docker Host)

```text
You are an AI Coding Assistant running on my homelab NAS "terramaster-nas".

--- BEGIN ENVIRONMENT SPEC ---
<core_env_spec.md content here>
--- END ENVIRONMENT SPEC ---

Machine-specific details:
- MACHINE_ID = "terramaster-nas"
- OS: TOS (TerraMaster OS)
- VLANs: 10 (MGMT) - 192.168.10.10, 20 (CORE) - 192.168.20.10
- Services: Docker (Jellyfin, Sonarr, Radarr, Home Assistant, etc.)
- Storage: /srv/media, /srv/projects, /srv/backups, /srv/robotics
- Neo4j runs here: bolt://localhost:7687

Now, here is your task:
<task here>
```

### ugv-rover-jetson (Robotics Platform)

```text
You are an AI Coding Assistant running on my robotics platform "ugv-rover-jetson".

--- BEGIN ENVIRONMENT SPEC ---
<core_env_spec.md content here>
--- END ENVIRONMENT SPEC ---

Machine-specific details:
- MACHINE_ID = "ugv-rover-jetson"
- Hardware: NVIDIA Jetson Orin
- VLAN: 50 (LAB/ROBOTICS) - 192.168.50.10
- Capabilities: ROS2, AI inference, sensor fusion
- Logs to: /srv/robotics on NAS via SMB/NFS

Now, here is your task:
<task here>
```

---

## 3. CLI/API Automation Script

### Bash Script Builder

```bash
#!/bin/bash
# build_prompt.sh - Build a prompt with environment spec

CORE_SPEC_FILE="${DOMO_SPEC_FILE:-$HOME/.domo/core_env_spec.md}"
MACHINE_ID="${MACHINE_ID:-$(hostname)}"

build_prompt() {
    local task="$1"

    cat << PROMPT
You are an AI Coding Assistant working in my homelab.

--- BEGIN ENVIRONMENT SPEC ---
PROMPT

    cat "$CORE_SPEC_FILE"

    cat << PROMPT

--- END ENVIRONMENT SPEC ---

Your current machine is: $MACHINE_ID

Your task:
$task

Follow the Core Environment & Network Spec for machine detection, networking, and agent messaging.
PROMPT
}

# Example usage:
# build_prompt "Write a Python module that detects the current machine and connects to Neo4j"
```

### Python Script Builder

```python
#!/usr/bin/env python3
"""Build prompts with environment spec."""

import os
from pathlib import Path

def build_prompt(task: str, machine_id: str = None) -> str:
    """Build a prompt with the core environment spec."""
    spec_file = Path(os.environ.get("DOMO_SPEC_FILE", Path.home() / ".domo" / "core_env_spec.md"))
    machine_id = machine_id or os.environ.get("MACHINE_ID", "unknown")

    spec_content = spec_file.read_text() if spec_file.exists() else "[SPEC FILE NOT FOUND]"

    return f"""You are an AI Coding Assistant working in my homelab.

--- BEGIN ENVIRONMENT SPEC ---
{spec_content}
--- END ENVIRONMENT SPEC ---

Your current machine is: {machine_id}

Your task:
{task}

Follow the Core Environment & Network Spec for machine detection, networking, and agent messaging.
"""

# Example
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(build_prompt(" ".join(sys.argv[1:])))
```

---

## 4. API Message Format (OpenAI/Anthropic)

```json
{
  "messages": [
    {
      "role": "system",
      "content": "You are an AI Coding Assistant in my homelab.\n\n<CORE_ENV_SPEC_HERE>\n\nAlways follow the spec for machine detection and service connections."
    },
    {
      "role": "user",
      "content": "You are running on box-rig. Implement identify_machine() and connect_neo4j() helpers according to the spec."
    }
  ]
}
```

---

## 5. Common Task Templates

### Implement Helper Library

```text
Your task:
1. Implement the domo-env helper library with these functions:
   - identify_machine() - detect current machine from env/hostname/IP/GPU
   - load_cluster_config() - load config from env vars and ~/.domo/config.json
   - connect_neo4j() - connect to Neo4j using cluster config
   - connect_agent_bus() - connect to SQLite agent bus
   - register_agent_instance() - register this agent in the bus

2. Follow the naming conventions from the spec
3. Use environment variables as the primary configuration source
4. Handle missing config gracefully

Return: Python module with all functions implemented
```

### Create Agent Runner

```text
Your task:
Build a new agent runner that:
1. Uses identify_machine() to detect where it's running
2. Registers itself in the agent bus
3. Sends heartbeats every 30 seconds
4. Listens for messages from other agents
5. Logs activity to Neo4j

Make sure you follow the Core Environment & Network Spec for machine detection, networking and agent messaging.

Return: Complete Python script with systemd unit file
```

### Network Discovery Script

```text
Your task:
Create a network discovery script that:
1. Scans the local network using ARP
2. Identifies devices by MAC vendor (OUI lookup)
3. Maps discovered devices to VLANs based on IP
4. Writes results to the Neo4j homelab database
5. Links discovered devices to known PhysicalHost nodes when possible

Use the VLAN layout from the spec to determine which VLAN each device belongs to.

Return: Python script with CLI interface
```

### Debug Connection Issues

```text
Your task:
I'm having trouble connecting to <service> from <machine>.

Given the network topology in the spec:
1. Identify which VLANs are involved
2. Check if firewall rules should allow this traffic
3. Suggest diagnostic commands to run
4. Propose fixes if the connection should work

Return: Diagnosis and recommended actions
```

---

## 6. Maintenance Reminders

- Keep **one master copy** of core_env_spec.md in Git or on NAS
- Update the spec FIRST when you change network or add machines
- Don't proliferate slightly different versions - single source of truth
- Suggested locations:
  - Git: `/srv/projects/claudius/domo/core_env_spec.md`
  - User: `~/.domo/core_env_spec.md`
  - System: `/etc/domo/core_env_spec.md`
