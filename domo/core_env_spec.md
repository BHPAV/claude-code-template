# Core Environment & Network Specification

This document is the **single source of truth** for the homelab environment. AI assistants should use this as background context when working on any homelab-related tasks.

---

## 1. Network Topology

### 1.1 VLAN Layout

| VLAN | Name         | CIDR            | Gateway       | Purpose                          |
|------|--------------|-----------------|---------------|----------------------------------|
| 10   | MGMT         | 192.168.10.0/24 | 192.168.10.1  | Router, switches, APs, NAS mgmt  |
| 20   | CORE/SERVERS | 192.168.20.0/24 | 192.168.20.1  | TerraMaster, NAS services, VMs   |
| 30   | CLIENTS      | 192.168.30.0/24 | 192.168.30.1  | PCs, MacBook, workstations       |
| 40   | IoT          | 192.168.40.0/24 | 192.168.40.1  | TV, consoles, smart home devices |
| 50   | LAB/ROBOTICS | 192.168.50.0/24 | 192.168.50.1  | UGV Rover, Jetson, lab devices   |

### 1.2 Core Infrastructure

| Device          | Type     | VLAN | IP              | Role                    |
|-----------------|----------|------|-----------------|-------------------------|
| Router/Firewall | Router   | 10   | 192.168.10.1    | Gateway, VLAN routing   |
| Core Switch     | Switch   | 10   | 192.168.10.2    | L2/L3, trunk ports      |

---

## 2. Machine Inventory

### 2.1 Physical Hosts

| Machine ID        | Name                   | VLAN | IP(s)                          | Role               | Key Specs                   | OS            |
|-------------------|------------------------|------|--------------------------------|--------------------|-----------------------------|---------------|
| terramaster-nas   | TerraMaster F4-424 Pro | 10,20| 192.168.10.10, 192.168.20.10   | NAS, Docker Host   | i3-N305, 32GB, BTRFS        | TOS / Linux   |
| box-rig           | Box-Rig                | 30   | 192.168.30.10                  | GPU Workstation    | RTX 5090 (32GB VRAM)        | Windows 11    |
| box-rex           | Box-Rex                | 30   | 192.168.30.11                  | GPU Workstation    | RTX 4090 (24GB VRAM)        | Windows 11    |
| macbook-pro       | MacBook Pro            | 30   | DHCP                           | Mobile Workstation | Apple Silicon, WiFi         | macOS         |
| ugv-rover-jetson  | UGV Rover Jetson Orin  | 50   | 192.168.50.10                  | Robotics Platform  | Jetson Orin, ROS2           | JetPack/Ubuntu|
| lab-pc            | Lab PC/Pi              | 50   | 192.168.50.20                  | Lab Base Station   | Raspberry Pi 5              | Linux         |

### 2.2 Machine Detection

Agents should detect which machine they're running on using this priority:

1. **Environment variable**: `MACHINE_ID` (if set explicitly)
2. **Hostname match**: Compare `socket.gethostname()` to known hostnames
3. **IP match**: Check local IPs against the inventory
4. **GPU detection**: Presence of specific GPUs (RTX 5090 = box-rig, RTX 4090 = box-rex)

```python
def identify_machine() -> str:
    """Identify current machine from environment or system info."""
    import os
    import socket

    # 1. Check explicit env var
    if machine_id := os.environ.get("MACHINE_ID"):
        return machine_id

    # 2. Check hostname
    hostname = socket.gethostname().lower()
    hostname_map = {
        "box-rig": "box-rig",
        "box-rex": "box-rex",
        "terramaster": "terramaster-nas",
        "nas": "terramaster-nas",
        "jetson": "ugv-rover-jetson",
        "ugv": "ugv-rover-jetson",
    }
    for pattern, machine_id in hostname_map.items():
        if pattern in hostname:
            return machine_id

    # 3. Check IP addresses
    # (implement based on network interface detection)

    return "unknown"
```

---

## 3. Services

### 3.1 Docker Services (on TerraMaster NAS)

| Service        | Port  | Access VLANs       | Description            |
|----------------|-------|---------------------|------------------------|
| Jellyfin       | 8096  | 30, 40, Tailscale   | Media server           |
| qBittorrent    | 8080  | 30                  | Torrent client         |
| Sonarr         | 8989  | 30                  | TV management          |
| Radarr         | 7878  | 30                  | Movie management       |
| Home Assistant | 8123  | 30, 40, 50, Tailscale| Smart home automation |
| Code-Server    | 8443  | 30, Tailscale       | VS Code in browser     |
| Immich         | 2283  | 30, Tailscale       | Photo management       |
| SMB/NFS        | 445/2049 | 30, 50           | File sharing           |

### 3.2 Storage Shares

| Share Name     | Path           | Protocol | Purpose                     |
|----------------|----------------|----------|-----------------------------|
| Media          | /srv/media     | SMB/NFS  | Movies, TV, music           |
| Projects       | /srv/projects  | SMB/NFS  | Development projects        |
| Backups        | /srv/backups   | SMB/NFS  | Backup storage              |
| Robotics Logs  | /srv/robotics  | SMB/NFS  | Rover telemetry, datasets   |

---

## 4. Agent Infrastructure

### 4.1 Environment Variables

Agents should check for these environment variables:

| Variable          | Description                           | Example                          |
|-------------------|---------------------------------------|----------------------------------|
| `MACHINE_ID`      | Explicit machine identifier           | `box-rig`                        |
| `NEO4J_URI`       | Neo4j connection URI                  | `bolt://192.168.20.10:7687`      |
| `NEO4J_USER`      | Neo4j username                        | `neo4j`                          |
| `NEO4J_PASSWORD`  | Neo4j password                        | (secret)                         |
| `NEO4J_DATABASE`  | Target database                       | `homelab`                        |
| `AGENT_BUS_SQLITE`| Path to agent bus SQLite              | `/var/lib/domo/agent_bus.sqlite` |
| `NAS_DATA_HOST`   | NAS hostname/IP for data access       | `192.168.20.10`                  |
| `NAS_MOUNT_PATH`  | Local NAS mount point                 | `/mnt/nas`                       |

### 4.2 Agent Bus (SQLite)

Local agent message passing via SQLite:

```sql
-- agent_instances: Track running agents
CREATE TABLE agent_instances (
    instance_id TEXT PRIMARY KEY,
    agent_type TEXT NOT NULL,
    machine_id TEXT NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP,
    status TEXT DEFAULT 'running'
);

-- agent_messages: Inter-agent messaging
CREATE TABLE agent_messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_agent TEXT NOT NULL,
    to_agent TEXT,  -- NULL = broadcast
    message_type TEXT NOT NULL,
    payload TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);
```

### 4.3 Neo4j Graph Database

- **URI**: `bolt://192.168.20.10:7687` (or via Tailscale)
- **Node Types**: See database mapping below

#### Neo4j Database Mapping

| Database       | Purpose                                                    | Key Node Types                                              |
|----------------|------------------------------------------------------------|------------------------------------------------------------|
| `homelab`      | Network topology, infrastructure                           | VLAN, PhysicalHost, DockerService, DiscoveredDevice        |
| `claudehooks`  | Claude Code CLI session logging                            | ClaudeCodeSession, CLIToolCall, CLIPrompt, CLIMetrics, Machine, File |
| `neo4j`        | Default database (legacy data, agent orchestration)        | Agent, AgentSession, Session, Instance                      |

**Note**: Database names in Neo4j cannot contain underscores, hence `claudehooks` (not `claude_hooks`).

### 4.4 Platform-Specific Paths

Paths vary by operating system. Agents should use these conventions:

| Platform | Agent Bus SQLite                                | Config Directory        | Spec File Location                   |
|----------|------------------------------------------------|-------------------------|--------------------------------------|
| Windows  | `%APPDATA%\domo\agent_bus.sqlite`              | `%USERPROFILE%\.domo\`  | `%USERPROFILE%\.domo\core_env_spec.md` |
| Linux    | `/var/lib/domo/agent_bus.sqlite`               | `~/.domo/`              | `~/.domo/core_env_spec.md`           |
| macOS    | `~/Library/Application Support/domo/agent_bus.sqlite` | `~/.domo/`       | `~/.domo/core_env_spec.md`           |

**Python path resolution**:
```python
import os
from pathlib import Path

def get_domo_config_dir() -> Path:
    """Get platform-appropriate domo config directory."""
    if os.name == 'nt':  # Windows
        return Path(os.environ.get('USERPROFILE', '~')) / '.domo'
    return Path.home() / '.domo'

def get_agent_bus_path() -> Path:
    """Get platform-appropriate agent bus SQLite path."""
    if os.name == 'nt':  # Windows
        return Path(os.environ.get('APPDATA', '~')) / 'domo' / 'agent_bus.sqlite'
    elif sys.platform == 'darwin':  # macOS
        return Path.home() / 'Library' / 'Application Support' / 'domo' / 'agent_bus.sqlite'
    return Path('/var/lib/domo/agent_bus.sqlite')
```

---

## 5. Tailscale Overlay

Tailscale provides secure remote access without port forwarding.

| Node             | Role           | Advertised Routes              |
|------------------|----------------|--------------------------------|
| Router           | Subnet Router  | 192.168.20.0/24, 192.168.50.0/24|
| TerraMaster NAS  | Client         | -                              |
| Box-Rig          | Client         | -                              |
| Box-Rex          | Client         | -                              |
| MacBook Pro      | Client         | -                              |
| Jetson/Lab       | Client         | -                              |

---

## 6. Firewall Policy Summary

| From VLAN | To VLAN   | Policy                                      |
|-----------|-----------|---------------------------------------------|
| MGMT (10) | ALL       | ALLOW (admin access)                        |
| CORE (20) | WAN       | ALLOW (updates, Docker pulls)               |
| CLIENTS (30)| CORE (20)| ALLOW specific ports (NAS, services)        |
| IoT (40)  | CORE (20) | ALLOW port 8096 only (Jellyfin)             |
| IoT (40)  | MGMT, LAB | DENY                                        |
| LAB (50)  | CORE (20) | ALLOW SMB/NFS (logs, datasets)              |

---

## 7. Conventions

### 7.1 Naming

- **Machine IDs**: lowercase, hyphen-separated (e.g., `box-rig`, `terramaster-nas`)
- **Service IDs**: lowercase, hyphen-separated (e.g., `home-assistant`, `code-server`)
- **VLAN names**: UPPERCASE or Title Case (e.g., `MGMT`, `CORE/SERVERS`)

### 7.2 Paths

- **NAS shares**: `/srv/<share_name>` on NAS, `/mnt/nas/<share_name>` when mounted
- **Config files**: `~/.domo/` for user config, `/etc/domo/` for system config
- **Agent data**: `/var/lib/domo/` for persistent agent data

### 7.3 Logging

- Use structured JSON logging where possible
- Include `machine_id`, `timestamp`, `level`, `message` fields
- Write to Neo4j for cross-machine analysis when appropriate

---

## 8. Quick Reference

```bash
# Check current machine
echo $MACHINE_ID

# Test Neo4j connection
cypher-shell -a bolt://192.168.20.10:7687 -u neo4j "RETURN 1"

# Mount NAS (Linux)
sudo mount -t cifs //192.168.20.10/projects /mnt/nas/projects -o username=user

# Run discovery scan
python scripts/network_discovery.py --verbose
```

---

*Last updated: 2025-12-09*
*Location: ~/.domo/core_env_spec.md or /srv/projects/claudius/domo/core_env_spec.md*
