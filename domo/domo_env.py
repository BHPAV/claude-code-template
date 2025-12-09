#!/usr/bin/env python3
"""
domo-env: Homelab Environment Helper Library

Provides machine detection, service connections, and agent registration
for the distributed homelab environment.

Usage as library:
    from domo_env import DomoEnv

    env = DomoEnv()
    print(f"Running on: {env.machine_id}")

    if env.neo4j_available:
        env.connect_neo4j()

Usage as CLI:
    python domo_env.py info
    python domo_env.py test-connections
    python domo_env.py register-agent my-agent-type
"""

import argparse
import json
import os
import socket
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

# Machine inventory for detection
MACHINE_INVENTORY = {
    "terramaster-nas": {
        "hostnames": ["terramaster", "nas", "f4-424", "box-nas"],
        "ips": ["192.168.1.20", "192.168.10.10", "192.168.20.10"],
        "tailscale_name": "terramaster-nas",
        "tailscale_ip": "100.74.45.35",
        "ssh_user": "boxhead",
        "role": "NAS/Docker Host",
        "os": "linux",
        "vlan": [10, 20],
    },
    "box-rig": {
        "hostnames": ["box-rig", "boxrig"],
        "ips": ["192.168.30.10"],
        "tailscale_name": "box-rig",
        "tailscale_ip": "100.120.211.28",
        "ssh_user": "boxhead",
        "role": "GPU Workstation",
        "os": "windows",
        "gpu": "RTX 5090",
        "vlan": [30],
    },
    "box-rex": {
        "hostnames": ["box-rex", "boxrex"],
        "ips": ["192.168.30.11"],
        "tailscale_name": "box-rex",
        "tailscale_ip": "100.98.133.117",
        "ssh_user": "boxhead",
        "role": "GPU Workstation",
        "os": "windows",
        "gpu": "RTX 4090",
        "vlan": [30],
    },
    "macbook-pro": {
        "hostnames": ["macbook", "mbp"],
        "ips": [],  # DHCP
        "tailscale_name": "box-mac-1",
        "tailscale_ip": "100.69.182.91",
        "ssh_user": "boxhead",
        "role": "Mobile Workstation",
        "os": "macos",
        "vlan": [30],
    },
    "ugv-rover-jetson": {
        "hostnames": ["jetson", "ugv", "rover", "orin"],
        "ips": ["192.168.50.10"],
        "role": "Robotics Platform",
        "os": "linux",
        "vlan": [50],
    },
    "lab-pc": {
        "hostnames": ["lab-pc", "labpc", "pi5"],
        "ips": ["192.168.50.20"],
        "role": "Lab Base Station",
        "os": "linux",
        "vlan": [50],
    },
}

# Default configuration
DEFAULT_CONFIG = {
    "neo4j_uri": "bolt://192.168.1.20:7687",
    "neo4j_user": "neo4j",
    "neo4j_database": "homelab",
    "nas_host": "192.168.1.20",
    "agent_bus_path": "/var/lib/domo/agent_bus.sqlite",
}


@dataclass
class ClusterConfig:
    """Cluster-wide configuration."""
    neo4j_uri: str = ""
    neo4j_user: str = ""
    neo4j_password: str = ""
    neo4j_database: str = "homelab"
    nas_host: str = ""
    nas_mount_path: str = ""
    agent_bus_path: str = ""


@dataclass
class MachineInfo:
    """Information about the current machine."""
    machine_id: str
    hostname: str
    role: str
    vlans: list[int] = field(default_factory=list)
    local_ips: list[str] = field(default_factory=list)
    gpu: Optional[str] = None
    detection_method: str = "unknown"


class DomoEnv:
    """Homelab environment helper."""

    def __init__(self):
        self._machine_info: Optional[MachineInfo] = None
        self._config: Optional[ClusterConfig] = None
        self._neo4j_driver = None
        self._agent_bus_conn: Optional[sqlite3.Connection] = None

    @property
    def machine_id(self) -> str:
        """Get current machine ID."""
        return self.machine_info.machine_id

    @property
    def machine_info(self) -> MachineInfo:
        """Get full machine information."""
        if self._machine_info is None:
            self._machine_info = self._detect_machine()
        return self._machine_info

    @property
    def config(self) -> ClusterConfig:
        """Get cluster configuration."""
        if self._config is None:
            self._config = self._load_config()
        return self._config

    @property
    def neo4j_available(self) -> bool:
        """Check if Neo4j connection info is available."""
        return bool(self.config.neo4j_uri and self.config.neo4j_password)

    @property
    def agent_bus_available(self) -> bool:
        """Check if agent bus SQLite exists."""
        return Path(self.config.agent_bus_path).exists()

    def _detect_machine(self) -> MachineInfo:
        """Detect which machine we're running on."""
        hostname = socket.gethostname().lower()
        local_ips = self._get_local_ips()

        # 1. Check explicit env var
        if machine_id := os.environ.get("MACHINE_ID"):
            inv = MACHINE_INVENTORY.get(machine_id, {})
            return MachineInfo(
                machine_id=machine_id,
                hostname=hostname,
                role=inv.get("role", "Unknown"),
                vlans=inv.get("vlan", []),
                local_ips=local_ips,
                gpu=inv.get("gpu"),
                detection_method="env_var"
            )

        # 2. Check hostname patterns
        for machine_id, inv in MACHINE_INVENTORY.items():
            for pattern in inv.get("hostnames", []):
                if pattern in hostname:
                    return MachineInfo(
                        machine_id=machine_id,
                        hostname=hostname,
                        role=inv.get("role", "Unknown"),
                        vlans=inv.get("vlan", []),
                        local_ips=local_ips,
                        gpu=inv.get("gpu"),
                        detection_method="hostname"
                    )

        # 3. Check IP addresses
        for machine_id, inv in MACHINE_INVENTORY.items():
            for known_ip in inv.get("ips", []):
                if known_ip in local_ips:
                    return MachineInfo(
                        machine_id=machine_id,
                        hostname=hostname,
                        role=inv.get("role", "Unknown"),
                        vlans=inv.get("vlan", []),
                        local_ips=local_ips,
                        gpu=inv.get("gpu"),
                        detection_method="ip_address"
                    )

        # 4. Check GPU (Windows/Linux)
        gpu = self._detect_gpu()
        if gpu:
            for machine_id, inv in MACHINE_INVENTORY.items():
                if inv.get("gpu") and inv["gpu"].lower() in gpu.lower():
                    return MachineInfo(
                        machine_id=machine_id,
                        hostname=hostname,
                        role=inv.get("role", "Unknown"),
                        vlans=inv.get("vlan", []),
                        local_ips=local_ips,
                        gpu=gpu,
                        detection_method="gpu"
                    )

        # Unknown machine
        return MachineInfo(
            machine_id="unknown",
            hostname=hostname,
            role="Unknown",
            local_ips=local_ips,
            gpu=gpu,
            detection_method="fallback"
        )

    def _get_local_ips(self) -> list[str]:
        """Get list of local IP addresses."""
        ips = []
        try:
            # Get all network interfaces
            hostname = socket.gethostname()
            ips = socket.gethostbyname_ex(hostname)[2]
        except Exception:
            pass

        # Also try getting IPs via socket connection
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
            s.close()
        except Exception:
            pass

        return list(set(ips))

    def _detect_gpu(self) -> Optional[str]:
        """Detect GPU model."""
        # Try nvidia-smi
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip().split("\n")[0]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Windows: try wmic
        if sys.platform == "win32":
            try:
                result = subprocess.run(
                    ["wmic", "path", "win32_VideoController", "get", "name"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    lines = [l.strip() for l in result.stdout.split("\n") if l.strip() and "Name" not in l]
                    for line in lines:
                        if "NVIDIA" in line or "RTX" in line or "GTX" in line:
                            return line
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        return None

    def _load_config(self) -> ClusterConfig:
        """Load cluster configuration from environment and files."""
        config = ClusterConfig()

        # Load from environment variables (highest priority)
        config.neo4j_uri = os.environ.get("NEO4J_URI", DEFAULT_CONFIG["neo4j_uri"])
        config.neo4j_user = os.environ.get("NEO4J_USER", DEFAULT_CONFIG["neo4j_user"])
        config.neo4j_password = os.environ.get("NEO4J_PASSWORD", "")
        config.neo4j_database = os.environ.get("NEO4J_DATABASE", DEFAULT_CONFIG["neo4j_database"])
        config.nas_host = os.environ.get("NAS_DATA_HOST", DEFAULT_CONFIG["nas_host"])
        config.nas_mount_path = os.environ.get("NAS_MOUNT_PATH", "")
        config.agent_bus_path = os.environ.get("AGENT_BUS_SQLITE", DEFAULT_CONFIG["agent_bus_path"])

        # Try loading from config file
        config_paths = [
            Path.home() / ".domo" / "config.json",
            Path("/etc/domo/config.json"),
        ]

        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path) as f:
                        file_config = json.load(f)
                    # Only fill in missing values
                    if not config.neo4j_password and "neo4j_password" in file_config:
                        config.neo4j_password = file_config["neo4j_password"]
                    if not config.nas_mount_path and "nas_mount_path" in file_config:
                        config.nas_mount_path = file_config["nas_mount_path"]
                except Exception:
                    pass

        return config

    def connect_neo4j(self):
        """Connect to Neo4j database."""
        if not self.neo4j_available:
            raise RuntimeError("Neo4j connection info not available")

        try:
            from neo4j import GraphDatabase
        except ImportError:
            raise ImportError("neo4j package not installed. Run: pip install neo4j")

        self._neo4j_driver = GraphDatabase.driver(
            self.config.neo4j_uri,
            auth=(self.config.neo4j_user, self.config.neo4j_password)
        )
        return self._neo4j_driver

    def connect_agent_bus(self) -> sqlite3.Connection:
        """Connect to agent bus SQLite database."""
        if self._agent_bus_conn is not None:
            return self._agent_bus_conn

        db_path = Path(self.config.agent_bus_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._agent_bus_conn = sqlite3.connect(str(db_path))
        self._agent_bus_conn.row_factory = sqlite3.Row

        # Initialize schema if needed
        self._agent_bus_conn.executescript("""
            CREATE TABLE IF NOT EXISTS agent_instances (
                instance_id TEXT PRIMARY KEY,
                agent_type TEXT NOT NULL,
                machine_id TEXT NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TIMESTAMP,
                status TEXT DEFAULT 'running',
                metadata TEXT
            );

            CREATE TABLE IF NOT EXISTS agent_messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_agent TEXT NOT NULL,
                to_agent TEXT,
                message_type TEXT NOT NULL,
                payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_messages_to ON agent_messages(to_agent);
            CREATE INDEX IF NOT EXISTS idx_messages_unprocessed ON agent_messages(processed_at) WHERE processed_at IS NULL;
        """)

        return self._agent_bus_conn

    def register_agent(self, agent_type: str, metadata: Optional[dict] = None) -> str:
        """Register this agent instance in the agent bus."""
        conn = self.connect_agent_bus()
        instance_id = f"{agent_type}:{self.machine_id}:{uuid4().hex[:8]}"

        conn.execute("""
            INSERT INTO agent_instances (instance_id, agent_type, machine_id, last_seen_at, metadata)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
        """, (instance_id, agent_type, self.machine_id, json.dumps(metadata or {})))
        conn.commit()

        return instance_id

    def heartbeat(self, instance_id: str):
        """Update agent heartbeat."""
        conn = self.connect_agent_bus()
        conn.execute("""
            UPDATE agent_instances
            SET last_seen_at = CURRENT_TIMESTAMP
            WHERE instance_id = ?
        """, (instance_id,))
        conn.commit()

    def send_message(self, from_agent: str, message_type: str, payload: Any, to_agent: Optional[str] = None):
        """Send a message via the agent bus."""
        conn = self.connect_agent_bus()
        conn.execute("""
            INSERT INTO agent_messages (from_agent, to_agent, message_type, payload)
            VALUES (?, ?, ?, ?)
        """, (from_agent, to_agent, message_type, json.dumps(payload)))
        conn.commit()

    def receive_messages(self, agent_id: str, mark_processed: bool = True) -> list[dict]:
        """Receive messages for this agent."""
        conn = self.connect_agent_bus()
        cursor = conn.execute("""
            SELECT message_id, from_agent, message_type, payload, created_at
            FROM agent_messages
            WHERE (to_agent = ? OR to_agent IS NULL)
              AND processed_at IS NULL
            ORDER BY created_at
        """, (agent_id,))

        messages = []
        message_ids = []

        for row in cursor:
            messages.append({
                "message_id": row["message_id"],
                "from_agent": row["from_agent"],
                "message_type": row["message_type"],
                "payload": json.loads(row["payload"]) if row["payload"] else None,
                "created_at": row["created_at"],
            })
            message_ids.append(row["message_id"])

        if mark_processed and message_ids:
            placeholders = ",".join("?" * len(message_ids))
            conn.execute(f"""
                UPDATE agent_messages
                SET processed_at = CURRENT_TIMESTAMP
                WHERE message_id IN ({placeholders})
            """, message_ids)
            conn.commit()

        return messages

    def get_machine_prompt(self) -> str:
        """Load machine-specific prompt shim.

        Returns:
            str: Machine context prompt from prompts/ directory,
                 or a basic fallback if not found.
        """
        prompt_file = Path(__file__).parent / "prompts" / f"{self.machine_id}.md"
        if prompt_file.exists():
            return prompt_file.read_text()
        return f"## Machine Context: {self.machine_id}\n\nMachine ID: {self.machine_id}\nRole: {self.machine_info.role}\nUnknown machine - no prompt template available."

    def get_spec(self, level: str = 'medium') -> str:
        """Load environment spec at specified compression level.

        Args:
            level: 'full', 'medium', or 'minimal'

        Returns:
            str: Environment specification content
        """
        spec_file = Path(__file__).parent / "specs" / f"env_spec_{level}.md"
        if spec_file.exists():
            return spec_file.read_text()
        # Fallback to core spec
        core_spec = Path(__file__).parent / "core_env_spec.md"
        if core_spec.exists():
            return core_spec.read_text()
        return "# Environment spec not found"

    def get_full_context(self, spec_level: str = 'medium') -> str:
        """Get complete session context with machine prompt and spec.

        Args:
            spec_level: 'full', 'medium', or 'minimal'

        Returns:
            str: Combined machine prompt and environment spec
        """
        machine_prompt = self.get_machine_prompt()
        spec = self.get_spec(spec_level)
        return f"{machine_prompt}\n\n---\n\n{spec}"

    def test_connections(self) -> dict[str, bool]:
        """Test all available connections."""
        results = {}

        # Test Neo4j
        if self.neo4j_available:
            try:
                driver = self.connect_neo4j()
                with driver.session() as session:
                    session.run("RETURN 1").single()
                results["neo4j"] = True
            except Exception as e:
                results["neo4j"] = False
                results["neo4j_error"] = str(e)
        else:
            results["neo4j"] = None  # Not configured

        # Test NAS mount
        if self.config.nas_mount_path:
            results["nas_mount"] = Path(self.config.nas_mount_path).is_mount()
        else:
            results["nas_mount"] = None

        # Test agent bus
        try:
            self.connect_agent_bus()
            results["agent_bus"] = True
        except Exception as e:
            results["agent_bus"] = False
            results["agent_bus_error"] = str(e)

        return results

    def get_tailscale_ssh(self):
        """Get TailscaleSSH instance for SSH operations."""
        try:
            from .ssh import TailscaleSSH
        except ImportError:
            # When running as script, use path-based import
            import sys
            from pathlib import Path
            ssh_path = Path(__file__).parent / "ssh"
            if str(ssh_path.parent) not in sys.path:
                sys.path.insert(0, str(ssh_path.parent))
            from ssh.tailscale import TailscaleSSH
        return TailscaleSSH()

    def get_tailscale_status(self) -> dict:
        """Get Tailscale network status as dict."""
        ssh = self.get_tailscale_ssh()
        status = ssh.get_status()
        return {
            "self_name": status.self_name,
            "self_ip": status.self_ip,
            "machines": {
                mid: {
                    "online": m.online,
                    "tailscale_ip": m.tailscale_ip,
                    "ssh_user": m.ssh_user,
                    "os": m.os,
                    "connection_state": m.connection_state,
                }
                for mid, m in status.machines.items()
            }
        }

    def is_machine_online(self, machine_id: str) -> bool:
        """Check if a machine is online via Tailscale."""
        ssh = self.get_tailscale_ssh()
        return ssh.is_online(machine_id)

    def ssh_run(self, machine_id: str, command: str, timeout: int = 60) -> tuple[str, str, int]:
        """
        Run a command on a remote machine via Tailscale SSH.

        Args:
            machine_id: Target machine ID (box-rig, box-rex, box-mac, terramaster-nas)
            command: Command to execute
            timeout: Timeout in seconds

        Returns:
            Tuple of (stdout, stderr, return_code)
        """
        ssh = self.get_tailscale_ssh()
        return ssh.run_command(machine_id, command, timeout=timeout)

    def ssh_connect(self, machine_id: str) -> int:
        """
        Open an interactive SSH session to a machine.

        Args:
            machine_id: Target machine ID

        Returns:
            Exit code from SSH session
        """
        ssh = self.get_tailscale_ssh()
        return ssh.connect(machine_id)

    def test_ssh_connections(self) -> dict[str, tuple[bool, str]]:
        """Test SSH connections to all Tailscale machines."""
        ssh = self.get_tailscale_ssh()
        return ssh.test_all_connections()

    def close(self):
        """Close all connections."""
        if self._neo4j_driver:
            self._neo4j_driver.close()
        if self._agent_bus_conn:
            self._agent_bus_conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def cmd_info(env: DomoEnv, args):
    """Print environment information."""
    info = env.machine_info
    config = env.config

    print(f"Machine ID:        {info.machine_id}")
    print(f"Hostname:          {info.hostname}")
    print(f"Role:              {info.role}")
    print(f"VLANs:             {info.vlans}")
    print(f"Local IPs:         {info.local_ips}")
    print(f"GPU:               {info.gpu or 'None detected'}")
    print(f"Detection Method:  {info.detection_method}")
    print()
    print(f"Neo4j URI:         {config.neo4j_uri}")
    print(f"Neo4j Database:    {config.neo4j_database}")
    print(f"Neo4j Available:   {env.neo4j_available}")
    print(f"NAS Host:          {config.nas_host}")
    print(f"NAS Mount:         {config.nas_mount_path or 'Not configured'}")
    print(f"Agent Bus Path:    {config.agent_bus_path}")
    print(f"Agent Bus Exists:  {env.agent_bus_available}")


def cmd_test_connections(env: DomoEnv, args):
    """Test all connections."""
    print("Testing connections...")
    results = env.test_connections()

    for name, status in results.items():
        if name.endswith("_error"):
            continue
        if status is True:
            icon = "[OK]"
        elif status is False:
            icon = "[FAIL]"
            error = results.get(f"{name}_error", "")
            if error:
                icon += f" - {error}"
        else:
            icon = "[N/A]"
        print(f"  {name}: {icon}")


def cmd_register_agent(env: DomoEnv, args):
    """Register an agent instance."""
    instance_id = env.register_agent(args.agent_type)
    print(f"Registered agent: {instance_id}")


def cmd_list_agents(env: DomoEnv, args):
    """List registered agents."""
    conn = env.connect_agent_bus()
    cursor = conn.execute("""
        SELECT instance_id, agent_type, machine_id, status, last_seen_at
        FROM agent_instances
        ORDER BY last_seen_at DESC
    """)

    print(f"{'Instance ID':<40} {'Type':<15} {'Machine':<15} {'Status':<10} {'Last Seen'}")
    print("-" * 100)
    for row in cursor:
        print(f"{row['instance_id']:<40} {row['agent_type']:<15} {row['machine_id']:<15} {row['status']:<10} {row['last_seen_at']}")


def cmd_ssh_status(env: DomoEnv, args):
    """Show Tailscale SSH machine status."""
    ssh = env.get_tailscale_ssh()
    status = ssh.get_status()

    print(f"Self: {status.self_name} ({status.self_ip})")
    print()
    print(f"{'Machine':<18} {'Status':<12} {'IP':<18} {'OS':<10} {'User'}")
    print("-" * 75)

    for machine_id, machine in status.machines.items():
        status_str = "ONLINE" if machine.online else "offline"
        print(f"{machine_id:<18} {status_str:<12} {machine.tailscale_ip:<18} {machine.os:<10} {machine.ssh_user}")


def cmd_ssh(env: DomoEnv, args):
    """SSH to a machine or run a command."""
    if args.command:
        # Run command
        stdout, stderr, rc = env.ssh_run(args.machine, args.command, timeout=args.timeout)
        if stdout:
            print(stdout, end="")
        if stderr:
            print(stderr, end="", file=sys.stderr)
        sys.exit(rc)
    else:
        # Interactive session
        rc = env.ssh_connect(args.machine)
        sys.exit(rc)


def cmd_ssh_test(env: DomoEnv, args):
    """Test SSH connections."""
    ssh = env.get_tailscale_ssh()

    if args.machine:
        # Test single machine
        success, msg = ssh.test_connection(args.machine)
        print(f"{args.machine}: {'OK' if success else 'FAIL'} - {msg}")
        sys.exit(0 if success else 1)
    else:
        # Test all machines
        results = ssh.test_all_connections()
        all_ok = True
        for machine_id, (success, msg) in results.items():
            status = "OK" if success else "FAIL"
            print(f"{machine_id}: {status} - {msg}")
            if not success:
                all_ok = False
        sys.exit(0 if all_ok else 1)


def main():
    parser = argparse.ArgumentParser(
        description="Homelab environment helper",
        prog="domo-env"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # info
    subparsers.add_parser("info", help="Show environment information")

    # test-connections
    subparsers.add_parser("test-connections", help="Test all connections")

    # register-agent
    reg_parser = subparsers.add_parser("register-agent", help="Register an agent")
    reg_parser.add_argument("agent_type", help="Type of agent")

    # list-agents
    subparsers.add_parser("list-agents", help="List registered agents")

    # ssh-status
    subparsers.add_parser("ssh-status", help="Show Tailscale SSH machine status")

    # ssh
    ssh_parser = subparsers.add_parser("ssh", help="SSH to a machine")
    ssh_parser.add_argument("machine", help="Machine ID (box-rig, box-rex, box-mac, nas)")
    ssh_parser.add_argument("command", nargs="?", help="Command to run (optional)")
    ssh_parser.add_argument("--timeout", type=int, default=60, help="Timeout in seconds")

    # ssh-test
    ssh_test_parser = subparsers.add_parser("ssh-test", help="Test SSH connections")
    ssh_test_parser.add_argument("machine", nargs="?", help="Machine ID (optional, tests all if omitted)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    with DomoEnv() as env:
        if args.command == "info":
            cmd_info(env, args)
        elif args.command == "test-connections":
            cmd_test_connections(env, args)
        elif args.command == "register-agent":
            cmd_register_agent(env, args)
        elif args.command == "list-agents":
            cmd_list_agents(env, args)
        elif args.command == "ssh-status":
            cmd_ssh_status(env, args)
        elif args.command == "ssh":
            cmd_ssh(env, args)
        elif args.command == "ssh-test":
            cmd_ssh_test(env, args)


if __name__ == "__main__":
    main()
