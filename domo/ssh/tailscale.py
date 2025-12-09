#!/usr/bin/env python3
"""
Tailscale SSH client for homelab machine connectivity.

Uses Tailscale SSH for authentication - no key management needed.
Authentication is handled via Tailscale identity.
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional


# Machine configuration with Tailscale details
TAILSCALE_MACHINES = {
    "box-rig": {
        "tailscale_name": "box-rig",
        "tailscale_ip": "100.120.211.28",
        "ssh_user": "boxhead",
        "os": "windows",
        "description": "GPU Workstation (RTX 5090)",
    },
    "box-rex": {
        "tailscale_name": "box-rex",
        "tailscale_ip": "100.98.133.117",
        "ssh_user": "boxhead",
        "os": "windows",
        "description": "GPU Workstation (RTX 4090)",
    },
    "box-mac": {
        "tailscale_name": "box-mac-1",
        "tailscale_ip": "100.69.182.91",
        "ssh_user": "boxhead",
        "os": "macos",
        "description": "Mobile Workstation",
    },
    "terramaster-nas": {
        "tailscale_name": "terramaster-nas",
        "tailscale_ip": "100.74.45.35",
        "ssh_user": "boxhead",
        "os": "linux",
        "description": "NAS/Docker Host",
    },
}

# Aliases for convenience
MACHINE_ALIASES = {
    "rig": "box-rig",
    "rex": "box-rex",
    "mac": "box-mac",
    "macbook": "box-mac",
    "nas": "terramaster-nas",
    "terramaster": "terramaster-nas",
}


@dataclass
class MachineStatus:
    """Status of a single machine."""
    machine_id: str
    tailscale_name: str
    tailscale_ip: str
    ssh_user: str
    online: bool
    os: str
    description: str
    last_seen: Optional[str] = None
    connection_state: str = "unknown"


@dataclass
class TailscaleStatus:
    """Overall Tailscale network status."""
    self_name: str
    self_ip: str
    machines: dict[str, MachineStatus] = field(default_factory=dict)
    raw_status: dict = field(default_factory=dict)


class TailscaleSSH:
    """
    Tailscale SSH client for homelab machines.

    Provides methods for:
    - Checking machine online status
    - Running commands on remote machines
    - Opening interactive SSH sessions
    - File transfer (via scp over Tailscale)

    Usage:
        ssh = TailscaleSSH()

        # Check status
        status = ssh.get_status()
        print(f"Online machines: {[m for m, s in status.machines.items() if s.online]}")

        # Run command
        stdout, stderr, rc = ssh.run_command("box-rex", "nvidia-smi")

        # Interactive session
        ssh.connect("box-rig")
    """

    def __init__(self):
        self.machines = TAILSCALE_MACHINES.copy()
        self._status_cache: Optional[TailscaleStatus] = None

    def resolve_machine(self, machine_id: str) -> str:
        """Resolve machine ID or alias to canonical machine ID."""
        machine_id = machine_id.lower().strip()

        # Check aliases first
        if machine_id in MACHINE_ALIASES:
            return MACHINE_ALIASES[machine_id]

        # Check direct match
        if machine_id in self.machines:
            return machine_id

        # Check partial match on tailscale name
        for mid, info in self.machines.items():
            if machine_id == info["tailscale_name"]:
                return mid

        raise ValueError(f"Unknown machine: {machine_id}. Available: {list(self.machines.keys())}")

    def get_machine_info(self, machine_id: str) -> dict:
        """Get machine configuration."""
        machine_id = self.resolve_machine(machine_id)
        return self.machines[machine_id]

    def get_status(self, refresh: bool = False) -> TailscaleStatus:
        """
        Get Tailscale network status.

        Args:
            refresh: Force refresh of cached status

        Returns:
            TailscaleStatus with online/offline state of all machines
        """
        if self._status_cache and not refresh:
            return self._status_cache

        try:
            result = subprocess.run(
                ["tailscale", "status", "--json"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                raise RuntimeError(f"tailscale status failed: {result.stderr}")

            raw = json.loads(result.stdout)
        except FileNotFoundError:
            raise RuntimeError("Tailscale CLI not found. Is Tailscale installed?")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Tailscale status timed out")

        # Parse self info
        self_name = raw.get("Self", {}).get("HostName", "unknown")
        self_ips = raw.get("Self", {}).get("TailscaleIPs", [])
        self_ip = self_ips[0] if self_ips else "unknown"

        # Build peer status map
        peers = raw.get("Peer", {})
        peer_by_name: dict[str, dict] = {}
        peer_by_ip: dict[str, dict] = {}

        for peer_id, peer_info in peers.items():
            hostname = peer_info.get("HostName", "").lower()
            peer_by_name[hostname] = peer_info
            for ip in peer_info.get("TailscaleIPs", []):
                peer_by_ip[ip] = peer_info

        # Build machine status
        machines: dict[str, MachineStatus] = {}

        for machine_id, config in self.machines.items():
            ts_name = config["tailscale_name"].lower()
            ts_ip = config["tailscale_ip"]

            # Find peer by name or IP
            peer = peer_by_name.get(ts_name) or peer_by_ip.get(ts_ip)

            if peer:
                online = peer.get("Online", False)
                last_seen = peer.get("LastSeen", None)
                # Active means currently connected
                active = peer.get("Active", False)
                if active:
                    connection_state = "connected"
                elif online:
                    connection_state = "online"
                else:
                    connection_state = "offline"
            else:
                online = False
                last_seen = None
                connection_state = "not_found"

            machines[machine_id] = MachineStatus(
                machine_id=machine_id,
                tailscale_name=config["tailscale_name"],
                tailscale_ip=ts_ip,
                ssh_user=config["ssh_user"],
                online=online,
                os=config["os"],
                description=config["description"],
                last_seen=last_seen,
                connection_state=connection_state,
            )

        self._status_cache = TailscaleStatus(
            self_name=self_name,
            self_ip=self_ip,
            machines=machines,
            raw_status=raw
        )

        return self._status_cache

    def is_online(self, machine_id: str) -> bool:
        """Check if a machine is online."""
        machine_id = self.resolve_machine(machine_id)
        status = self.get_status()
        machine = status.machines.get(machine_id)
        return machine.online if machine else False

    def run_command(
        self,
        machine_id: str,
        command: str,
        timeout: int = 60,
        check: bool = False
    ) -> tuple[str, str, int]:
        """
        Run a command on a remote machine via Tailscale SSH.

        Args:
            machine_id: Target machine ID or alias
            command: Command to execute
            timeout: Timeout in seconds
            check: Raise exception on non-zero exit code

        Returns:
            Tuple of (stdout, stderr, return_code)

        Raises:
            RuntimeError: If machine is offline or command fails (when check=True)
        """
        machine_id = self.resolve_machine(machine_id)
        info = self.machines[machine_id]

        ssh_target = f"{info['ssh_user']}@{info['tailscale_name']}"

        try:
            result = subprocess.run(
                ["tailscale", "ssh", ssh_target, command],
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if check and result.returncode != 0:
                raise RuntimeError(
                    f"Command failed on {machine_id}: {result.stderr}"
                )

            return result.stdout, result.stderr, result.returncode

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Command timed out on {machine_id}")

    def connect(self, machine_id: str) -> int:
        """
        Open an interactive SSH session.

        Args:
            machine_id: Target machine ID or alias

        Returns:
            Exit code from SSH session
        """
        machine_id = self.resolve_machine(machine_id)
        info = self.machines[machine_id]

        ssh_target = f"{info['ssh_user']}@{info['tailscale_name']}"

        # Use os.system for interactive session (inherits stdin/stdout)
        if sys.platform == "win32":
            return os.system(f'tailscale ssh {ssh_target}')
        else:
            return os.system(f'tailscale ssh {ssh_target}')

    def copy_to(
        self,
        machine_id: str,
        local_path: str,
        remote_path: str,
        timeout: int = 300
    ) -> bool:
        """
        Copy file to remote machine using scp over Tailscale.

        Args:
            machine_id: Target machine ID or alias
            local_path: Local file path
            remote_path: Remote destination path
            timeout: Timeout in seconds

        Returns:
            True if successful
        """
        machine_id = self.resolve_machine(machine_id)
        info = self.machines[machine_id]

        # Use tailscale IP for scp (more reliable than name)
        scp_target = f"{info['ssh_user']}@{info['tailscale_ip']}:{remote_path}"

        try:
            result = subprocess.run(
                ["scp", "-o", "StrictHostKeyChecking=no", local_path, scp_target],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False

    def copy_from(
        self,
        machine_id: str,
        remote_path: str,
        local_path: str,
        timeout: int = 300
    ) -> bool:
        """
        Copy file from remote machine using scp over Tailscale.

        Args:
            machine_id: Target machine ID or alias
            remote_path: Remote file path
            local_path: Local destination path
            timeout: Timeout in seconds

        Returns:
            True if successful
        """
        machine_id = self.resolve_machine(machine_id)
        info = self.machines[machine_id]

        scp_target = f"{info['ssh_user']}@{info['tailscale_ip']}:{remote_path}"

        try:
            result = subprocess.run(
                ["scp", "-o", "StrictHostKeyChecking=no", scp_target, local_path],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False

    def test_connection(self, machine_id: str) -> tuple[bool, str]:
        """
        Test SSH connection to a machine.

        Args:
            machine_id: Target machine ID or alias

        Returns:
            Tuple of (success, message)
        """
        machine_id = self.resolve_machine(machine_id)

        if not self.is_online(machine_id):
            return False, "Machine is offline"

        try:
            stdout, stderr, rc = self.run_command(machine_id, "echo ok", timeout=10)
            if rc == 0 and "ok" in stdout:
                return True, "Connection successful"
            else:
                return False, f"Unexpected response: {stderr or stdout}"
        except Exception as e:
            return False, str(e)

    def test_all_connections(self) -> dict[str, tuple[bool, str]]:
        """Test connections to all configured machines."""
        results = {}
        for machine_id in self.machines:
            results[machine_id] = self.test_connection(machine_id)
        return results


def print_status():
    """Print Tailscale SSH status to console."""
    ssh = TailscaleSSH()
    status = ssh.get_status()

    print(f"Self: {status.self_name} ({status.self_ip})")
    print()
    print(f"{'Machine':<18} {'Status':<12} {'IP':<18} {'Description'}")
    print("-" * 70)

    for machine_id, machine in status.machines.items():
        if machine.online:
            status_str = "ONLINE"
        else:
            status_str = "offline"

        print(f"{machine_id:<18} {status_str:<12} {machine.tailscale_ip:<18} {machine.description}")


def main():
    """CLI for Tailscale SSH."""
    import argparse

    parser = argparse.ArgumentParser(description="Tailscale SSH client")
    subparsers = parser.add_subparsers(dest="command")

    # status
    subparsers.add_parser("status", help="Show machine status")

    # connect
    connect_parser = subparsers.add_parser("connect", help="Connect to machine")
    connect_parser.add_argument("machine", help="Machine ID or alias")

    # run
    run_parser = subparsers.add_parser("run", help="Run command on machine")
    run_parser.add_argument("machine", help="Machine ID or alias")
    run_parser.add_argument("cmd", help="Command to run")

    # test
    test_parser = subparsers.add_parser("test", help="Test connections")
    test_parser.add_argument("machine", nargs="?", help="Machine ID (optional)")

    args = parser.parse_args()

    if not args.command:
        print_status()
        return

    ssh = TailscaleSSH()

    if args.command == "status":
        print_status()

    elif args.command == "connect":
        ssh.connect(args.machine)

    elif args.command == "run":
        stdout, stderr, rc = ssh.run_command(args.machine, args.cmd)
        if stdout:
            print(stdout, end="")
        if stderr:
            print(stderr, end="", file=sys.stderr)
        sys.exit(rc)

    elif args.command == "test":
        if args.machine:
            success, msg = ssh.test_connection(args.machine)
            print(f"{args.machine}: {'OK' if success else 'FAIL'} - {msg}")
            sys.exit(0 if success else 1)
        else:
            results = ssh.test_all_connections()
            all_ok = True
            for machine_id, (success, msg) in results.items():
                status = "OK" if success else "FAIL"
                print(f"{machine_id}: {status} - {msg}")
                if not success:
                    all_ok = False
            sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
