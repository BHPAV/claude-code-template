"""
Tailscale SSH module for cross-machine connectivity.

Provides programmatic SSH access to homelab machines via Tailscale SSH.
No key management required - authentication via Tailscale identity.

Usage:
    from domo.ssh import TailscaleSSH

    ssh = TailscaleSSH()

    # Check machine status
    if ssh.is_online("box-rex"):
        stdout, stderr, rc = ssh.run_command("box-rex", "hostname")
        print(stdout)

    # Interactive session
    ssh.connect("box-rig")
"""

from .tailscale import TailscaleSSH, TailscaleStatus, MachineStatus

__all__ = ["TailscaleSSH", "TailscaleStatus", "MachineStatus"]
