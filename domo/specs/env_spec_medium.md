# Homelab Environment (Medium)

## Machines
| ID | Role | VLAN | IP | Specs | OS |
|----|------|------|-----|-------|-----|
| terramaster-nas | NAS/Docker | 10,20 | 192.168.10.10, .20.10 | i3-N305, 32GB | Linux |
| box-rig | GPU Workstation | 30 | 192.168.30.10 | RTX 5090 32GB | Windows |
| box-rex | GPU Workstation | 30 | 192.168.30.11 | RTX 4090 24GB | Windows |
| macbook-pro | Mobile | 30 | DHCP | Apple Silicon | macOS |
| ugv-rover-jetson | Robotics | 50 | 192.168.50.10 | Jetson Orin | Ubuntu |
| lab-pc | Lab Station | 50 | 192.168.50.20 | Raspberry Pi 5 | Linux |

## VLANs
- 10 = MGMT (192.168.10.0/24)
- 20 = CORE/SERVERS (192.168.20.0/24)
- 30 = CLIENTS (192.168.30.0/24)
- 40 = IoT (192.168.40.0/24)
- 50 = LAB/ROBOTICS (192.168.50.0/24)

## Services (on terramaster-nas)
- Jellyfin: 8096, Home Assistant: 8123, Neo4j: 7687
- SMB/NFS: /srv/media, /srv/projects, /srv/backups, /srv/robotics

## Neo4j
- **URI**: `bolt://192.168.20.10:7687`
- **Databases**: `homelab` (topology), `claudehooks` (CLI sessions)

## Machine Detection
1. `$MACHINE_ID` env var
2. Hostname pattern match
3. IP address match
4. GPU detection (5090=box-rig, 4090=box-rex)

## Key Environment Variables
```
MACHINE_ID=box-rig
NEO4J_URI=bolt://192.168.20.10:7687
NEO4J_DATABASE=claudehooks
NAS_DATA_HOST=192.168.20.10
```

## Agent Bus (SQLite)
- Windows: `%APPDATA%\domo\agent_bus.sqlite`
- Linux: `/var/lib/domo/agent_bus.sqlite`
- Tables: `agent_instances`, `agent_messages`

## Conventions
- Machine IDs: lowercase, hyphen-separated
- NAS paths: `/srv/<share>` on NAS, `/mnt/nas/<share>` mounted
