## Machine Context: terramaster-nas

- **MACHINE_ID**: terramaster-nas
- **Role**: NAS / Docker Host
- **VLANs**: 10 (MGMT), 20 (CORE/SERVERS)
- **IP Addresses**: 192.168.10.10 (mgmt), 192.168.20.10 (services)
- **Hardware**: Intel i3-N305, 32GB RAM, BTRFS storage
- **OS**: TOS (TerraMaster OS) / Linux
- **Docker Services**: Jellyfin, Sonarr, Radarr, Home Assistant, Neo4j, Code-Server, Immich
- **Storage Shares**: /srv/media, /srv/projects, /srv/backups, /srv/robotics
- **Neo4j**: bolt://localhost:7687 (local)

You are running on **terramaster-nas**, the central NAS and Docker host. Neo4j runs locally here. All storage shares originate from this machine. Docker services are managed via Portainer or CLI.
