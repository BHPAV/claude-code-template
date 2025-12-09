# Homelab Environment Specification (Full)

## Network Topology

### VLANs
| VLAN | Name         | CIDR            | Gateway       | Purpose                          |
|------|--------------|-----------------|---------------|----------------------------------|
| 10   | MGMT         | 192.168.10.0/24 | 192.168.10.1  | Router, switches, APs, NAS mgmt  |
| 20   | CORE/SERVERS | 192.168.20.0/24 | 192.168.20.1  | TerraMaster, NAS services, VMs   |
| 30   | CLIENTS      | 192.168.30.0/24 | 192.168.30.1  | PCs, MacBook, workstations       |
| 40   | IoT          | 192.168.40.0/24 | 192.168.40.1  | TV, consoles, smart home devices |
| 50   | LAB/ROBOTICS | 192.168.50.0/24 | 192.168.50.1  | UGV Rover, Jetson, lab devices   |

## Machine Inventory

| Machine ID        | Role               | VLAN  | IP(s)                          | Key Specs                   | OS            |
|-------------------|-------------------|-------|--------------------------------|-----------------------------|---------------|
| terramaster-nas   | NAS, Docker Host   | 10,20 | 192.168.10.10, 192.168.20.10   | i3-N305, 32GB, BTRFS        | TOS / Linux   |
| box-rig           | GPU Workstation    | 30    | 192.168.30.10                  | RTX 5090 (32GB VRAM)        | Windows 11    |
| box-rex           | GPU Workstation    | 30    | 192.168.30.11                  | RTX 4090 (24GB VRAM)        | Windows 11    |
| macbook-pro       | Mobile Workstation | 30    | DHCP                           | Apple Silicon               | macOS         |
| ugv-rover-jetson  | Robotics Platform  | 50    | 192.168.50.10                  | Jetson Orin, ROS2           | JetPack/Ubuntu|
| lab-pc            | Lab Base Station   | 50    | 192.168.50.20                  | Raspberry Pi 5              | Linux         |

### Machine Detection Priority
1. `MACHINE_ID` environment variable (if set explicitly)
2. Hostname pattern matching (e.g., "box-rig" in hostname)
3. IP address matching against known inventory
4. GPU detection (RTX 5090 = box-rig, RTX 4090 = box-rex)

## Services (on TerraMaster NAS)

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

### Storage Shares
| Share Name     | Path           | Protocol | Purpose                     |
|----------------|----------------|----------|-----------------------------|
| Media          | /srv/media     | SMB/NFS  | Movies, TV, music           |
| Projects       | /srv/projects  | SMB/NFS  | Development projects        |
| Backups        | /srv/backups   | SMB/NFS  | Backup storage              |
| Robotics Logs  | /srv/robotics  | SMB/NFS  | Rover telemetry, datasets   |

## Agent Infrastructure

### Environment Variables
| Variable          | Description                           | Example                          |
|-------------------|---------------------------------------|----------------------------------|
| `MACHINE_ID`      | Explicit machine identifier           | `box-rig`                        |
| `NEO4J_URI`       | Neo4j connection URI                  | `bolt://192.168.20.10:7687`      |
| `NEO4J_USER`      | Neo4j username                        | `neo4j`                          |
| `NEO4J_PASSWORD`  | Neo4j password                        | (secret)                         |
| `NEO4J_DATABASE`  | Target database                       | `claudehooks`                    |
| `AGENT_BUS_SQLITE`| Path to agent bus SQLite              | `/var/lib/domo/agent_bus.sqlite` |
| `NAS_DATA_HOST`   | NAS hostname/IP for data access       | `192.168.20.10`                  |
| `NAS_MOUNT_PATH`  | Local NAS mount point                 | `/mnt/nas`                       |

### Neo4j Database Mapping
| Database       | Purpose                                     |
|----------------|---------------------------------------------|
| `homelab`      | Network topology, PhysicalHost, VLAN        |
| `claudehooks`  | CLI sessions, tool calls, prompts, metrics  |
| `neo4j`        | Legacy data, agent orchestration            |

### Agent Bus Schema (SQLite)
```sql
CREATE TABLE agent_instances (
    instance_id TEXT PRIMARY KEY,
    agent_type TEXT NOT NULL,
    machine_id TEXT NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP,
    status TEXT DEFAULT 'running'
);

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

### Platform-Specific Paths
| Platform | Agent Bus Path                                   | Config Directory       |
|----------|------------------------------------------------|------------------------|
| Windows  | `%APPDATA%\domo\agent_bus.sqlite`              | `%USERPROFILE%\.domo\` |
| Linux    | `/var/lib/domo/agent_bus.sqlite`               | `~/.domo/`             |
| macOS    | `~/Library/Application Support/domo/agent_bus.sqlite` | `~/.domo/`      |

## Firewall Policy
| From VLAN | To VLAN   | Policy                                      |
|-----------|-----------|---------------------------------------------|
| MGMT (10) | ALL       | ALLOW (admin access)                        |
| CORE (20) | WAN       | ALLOW (updates, Docker pulls)               |
| CLIENTS (30)| CORE (20)| ALLOW specific ports (NAS, services)        |
| IoT (40)  | CORE (20) | ALLOW port 8096 only (Jellyfin)             |
| IoT (40)  | MGMT, LAB | DENY                                        |
| LAB (50)  | CORE (20) | ALLOW SMB/NFS (logs, datasets)              |

## Naming Conventions
- **Machine IDs**: lowercase, hyphen-separated (e.g., `box-rig`, `terramaster-nas`)
- **Service IDs**: lowercase, hyphen-separated (e.g., `home-assistant`, `code-server`)
- **Paths**: `/srv/<share>` on NAS, `/mnt/nas/<share>` when mounted
