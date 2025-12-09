## Machine Context: box-rex

- **MACHINE_ID**: box-rex
- **Role**: GPU Workstation (Secondary Compute)
- **VLAN**: 30 (CLIENTS)
- **IP Address**: 192.168.30.11
- **GPU**: NVIDIA RTX 4090 (24GB VRAM)
- **OS**: Windows 11
- **Primary Use**: Rendering, inference, secondary compute
- **NAS Access**: `\\192.168.20.10\projects`
- **Neo4j**: bolt://192.168.20.10:7687

You are running on **box-rex**, a GPU workstation with an RTX 4090 (24GB VRAM). This machine handles rendering, model inference, and serves as secondary compute when box-rig is busy.
