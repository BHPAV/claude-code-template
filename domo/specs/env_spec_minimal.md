# Homelab Quick Reference

**Machines**: terramaster-nas (NAS, VLAN 10/20), box-rig (RTX 5090, VLAN 30, 192.168.30.10), box-rex (RTX 4090, VLAN 30, 192.168.30.11), macbook-pro (VLAN 30), ugv-rover-jetson (Jetson, VLAN 50, 192.168.50.10), lab-pc (VLAN 50, 192.168.50.20)

**VLANs**: 10=MGMT, 20=CORE, 30=CLIENTS, 40=IoT, 50=LAB

**Neo4j**: bolt://192.168.20.10:7687 | Databases: homelab, claudehooks

**NAS**: 192.168.20.10 | SMB/NFS shares: /srv/media, /srv/projects

**Detection**: $MACHINE_ID env > hostname > IP > GPU

**Agent Bus**: SQLite at /var/lib/domo/agent_bus.sqlite (Linux) or %APPDATA%\domo\ (Windows)
