#!/usr/bin/env python3
"""
Network Discovery Script for Homelab

Discovers devices on the local network using ARP scanning and logs them to Neo4j.
Supports Windows (arp -a) and Linux (arp-scan or ip neigh).

Usage:
    python network_discovery.py [--scan-only] [--verbose]

Environment Variables:
    NEO4J_URI      - Neo4j connection URI (default: bolt://localhost:7687)
    NEO4J_USER     - Neo4j username (default: neo4j)
    NEO4J_PASSWORD - Neo4j password (required)
    NEO4J_DATABASE - Target database (default: homelab)
"""

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

# OUI vendor lookup (common manufacturers)
OUI_VENDORS = {
    "00:1A:79": "Intel",
    "00:50:56": "VMware",
    "00:0C:29": "VMware",
    "00:15:5D": "Microsoft Hyper-V",
    "08:00:27": "VirtualBox",
    "52:54:00": "QEMU/KVM",
    "B8:27:EB": "Raspberry Pi",
    "DC:A6:32": "Raspberry Pi",
    "E4:5F:01": "Raspberry Pi",
    "28:CD:C1": "Raspberry Pi",
    "D8:3A:DD": "Raspberry Pi",
    "00:E0:4C": "Realtek",
    "00:1B:21": "Intel",
    "00:1E:67": "Intel",
    "3C:7C:3F": "Intel",
    "AC:DE:48": "Intel",
    "A4:83:E7": "Apple",
    "14:98:77": "Apple",
    "F0:18:98": "Apple",
    "00:1F:F3": "Apple",
    "00:25:00": "Apple",
    "00:03:93": "Apple",
    "00:14:51": "Apple",
    "00:16:CB": "Apple",
    "00:17:F2": "Apple",
    "00:1C:B3": "Apple",
    "00:1D:4F": "Apple",
    "00:1E:C2": "Apple",
    "00:21:E9": "Apple",
    "00:22:41": "Apple",
    "00:23:12": "Apple",
    "00:23:32": "Apple",
    "00:23:6C": "Apple",
    "00:23:DF": "Apple",
    "00:24:36": "Apple",
    "00:25:4B": "Apple",
    "00:25:BC": "Apple",
    "00:26:08": "Apple",
    "00:26:4A": "Apple",
    "00:26:B0": "Apple",
    "00:26:BB": "Apple",
    "18:E7:F4": "Apple",
    "20:C9:D0": "Apple",
    "24:A0:74": "Apple",
    "28:6A:BA": "Apple",
    "34:C0:59": "Apple",
    "40:6C:8F": "Apple",
    "44:2A:60": "Apple",
    "58:55:CA": "Apple",
    "5C:F9:38": "Apple",
    "60:03:08": "Apple",
    "64:B9:E8": "Apple",
    "78:31:C1": "Apple",
    "78:7B:8A": "Apple",
    "80:E6:50": "Apple",
    "84:38:35": "Apple",
    "88:66:A5": "Apple",
    "8C:58:77": "Apple",
    "90:B9:31": "Apple",
    "98:D6:BB": "Apple",
    "9C:20:7B": "Apple",
    "A4:5E:60": "Apple",
    "A8:66:7F": "Apple",
    "AC:87:A3": "Apple",
    "B4:F0:AB": "Apple",
    "B8:C1:11": "Apple",
    "BC:52:B7": "Apple",
    "C0:CE:CD": "Apple",
    "C8:2A:14": "Apple",
    "D0:E1:40": "Apple",
    "D4:9A:20": "Apple",
    "D8:1D:72": "Apple",
    "DC:2B:2A": "Apple",
    "E0:5F:45": "Apple",
    "E4:8B:7F": "Apple",
    "E8:06:88": "Apple",
    "F0:B4:79": "Apple",
    "F4:5C:89": "Apple",
    "FC:25:3F": "Apple",
    "00:1A:A0": "Dell",
    "00:14:22": "Dell",
    "00:1E:4F": "Dell",
    "00:21:9B": "Dell",
    "14:FE:B5": "Dell",
    "18:A9:9B": "Dell",
    "24:B6:FD": "Dell",
    "34:17:EB": "Dell",
    "44:A8:42": "Dell",
    "54:9F:35": "Dell",
    "5C:26:0A": "Dell",
    "74:86:7A": "Dell",
    "78:2B:CB": "Dell",
    "80:18:44": "Dell",
    "84:7B:EB": "Dell",
    "90:B1:1C": "Dell",
    "98:90:96": "Dell",
    "A4:1F:72": "Dell",
    "A4:BA:DB": "Dell",
    "B0:83:FE": "Dell",
    "B8:AC:6F": "Dell",
    "BC:30:5B": "Dell",
    "C8:1F:66": "Dell",
    "D4:BE:D9": "Dell",
    "E4:F0:04": "Dell",
    "F0:1F:AF": "Dell",
    "F4:8E:38": "Dell",
    "F8:B1:56": "Dell",
    "FC:4D:D4": "Dell",
    "00:50:B6": "NVIDIA",
    "00:04:4B": "NVIDIA",
    "48:B0:2D": "NVIDIA",
    "00:1B:FC": "ASUSTek",
    "00:22:15": "ASUSTek",
    "00:26:18": "ASUSTek",
    "04:92:26": "ASUSTek",
    "08:60:6E": "ASUSTek",
    "10:BF:48": "ASUSTek",
    "14:DA:E9": "ASUSTek",
    "1C:87:2C": "ASUSTek",
    "20:CF:30": "ASUSTek",
    "2C:56:DC": "ASUSTek",
    "30:5A:3A": "ASUSTek",
    "30:85:A9": "ASUSTek",
    "38:D5:47": "ASUSTek",
    "40:B0:34": "ASUSTek",
    "4C:ED:FB": "ASUSTek",
    "50:46:5D": "ASUSTek",
    "54:04:A6": "ASUSTek",
    "60:45:CB": "ASUSTek",
    "74:D0:2B": "ASUSTek",
    "AC:9E:17": "ASUSTek",
    "B0:6E:BF": "ASUSTek",
    "BC:EE:7B": "ASUSTek",
    "C8:60:00": "ASUSTek",
    "E0:3F:49": "ASUSTek",
    "F4:6D:04": "ASUSTek",
    "70:85:C2": "TP-Link",
    "98:DA:C4": "TP-Link",
    "00:EB:D5": "Cisco",
    "00:1A:6C": "Cisco",
    "00:24:C4": "Cisco",
    "28:CF:DA": "Netgear",
    "A0:63:91": "Netgear",
    "C4:04:15": "Netgear",
    "00:04:4B": "Synology",
    "00:11:32": "Synology",
    "00:1E:06": "QNAP",
    "24:5E:BE": "QNAP",
    "00:08:9B": "TerraMaster",
    "50:6B:4B": "Amazon",
    "68:54:FD": "Amazon",
    "84:D6:D0": "Amazon",
    "A4:08:EA": "Amazon",
    "FC:65:DE": "Amazon",
    "34:8A:7B": "Samsung",
    "00:1E:E2": "Samsung",
    "08:FC:88": "Samsung",
    "24:4B:81": "Samsung",
    "50:01:BB": "Samsung",
    "78:AB:BB": "Samsung",
    "94:35:0A": "Samsung",
    "A8:7C:01": "Samsung",
    "BC:44:86": "Samsung",
    "CC:07:AB": "Samsung",
    "D0:22:BE": "Samsung",
    "EC:1F:72": "Samsung",
    "F8:04:2E": "Samsung",
    "00:1D:43": "Sony",
    "00:1E:A4": "Sony",
    "04:5D:4B": "Sony",
    "28:0D:FC": "Sony",
    "70:9E:29": "Sony",
    "78:84:3C": "Sony",
    "AC:64:DD": "Sony",
    "D8:D4:3C": "Sony",
    "FC:0F:E6": "Sony",
    "00:1A:2B": "Philips",
    "00:17:88": "Philips Hue",
    "EC:B5:FA": "Philips Hue",
    "00:09:B0": "Roku",
    "B0:A7:37": "Roku",
    "00:1D:C9": "Google",
    "00:1A:11": "Google",
    "3C:5A:B4": "Google",
    "54:60:09": "Google",
    "94:EB:2C": "Google",
    "F4:F5:D8": "Google",
    "F8:8F:CA": "Google",
    "20:DF:B9": "Google Nest",
    "64:16:66": "Google Nest",
    "D8:EB:46": "Google Nest",
    "2C:AA:8E": "Wyze",
}


@dataclass
class DiscoveredDevice:
    """Represents a discovered network device."""
    mac_address: str
    ip_address: str
    hostname: Optional[str] = None
    vendor: Optional[str] = None
    discovery_method: str = "arp"
    interface: Optional[str] = None


def get_vendor_from_mac(mac: str) -> Optional[str]:
    """Look up vendor from MAC address OUI (first 3 octets)."""
    mac_normalized = mac.upper().replace("-", ":").replace(".", ":")
    oui = ":".join(mac_normalized.split(":")[:3])
    return OUI_VENDORS.get(oui)


def parse_windows_arp(output: str) -> list[DiscoveredDevice]:
    """Parse Windows 'arp -a' output."""
    devices = []
    current_interface = None

    for line in output.strip().split("\n"):
        line = line.strip()

        # Interface header: "Interface: 192.168.1.100 --- 0x5"
        if line.startswith("Interface:"):
            match = re.search(r"Interface:\s+([\d.]+)", line)
            if match:
                current_interface = match.group(1)
            continue

        # ARP entry: "  192.168.1.1          00-1a-2b-3c-4d-5e     dynamic"
        match = re.match(
            r"^\s*([\d.]+)\s+([0-9a-fA-F-]{17})\s+(\w+)",
            line
        )
        if match:
            ip, mac, entry_type = match.groups()

            # Skip broadcast/multicast addresses
            mac_lower = mac.lower()
            if mac_lower == "ff-ff-ff-ff-ff-ff":
                continue
            if mac_lower.startswith("01-00-5e"):  # Multicast
                continue
            if mac_lower.startswith("33-33"):  # IPv6 multicast
                continue
            if ip.endswith(".255") or ip == "255.255.255.255":
                continue
            if ip.startswith("224.") or ip.startswith("239."):  # Multicast IPs
                continue

            # Normalize MAC to colon format
            mac_normalized = mac.replace("-", ":").upper()
            vendor = get_vendor_from_mac(mac_normalized)

            devices.append(DiscoveredDevice(
                mac_address=mac_normalized,
                ip_address=ip,
                vendor=vendor,
                discovery_method="arp",
                interface=current_interface
            ))

    return devices


def parse_linux_arp(output: str) -> list[DiscoveredDevice]:
    """Parse Linux 'ip neigh' or 'arp -n' output."""
    devices = []

    for line in output.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        # ip neigh format: "192.168.1.1 dev eth0 lladdr 00:1a:2b:3c:4d:5e REACHABLE"
        match = re.match(
            r"^([\d.]+)\s+dev\s+(\S+)\s+lladdr\s+([0-9a-fA-F:]{17})",
            line
        )
        if match:
            ip, interface, mac = match.groups()
            mac_normalized = mac.upper()
            vendor = get_vendor_from_mac(mac_normalized)

            devices.append(DiscoveredDevice(
                mac_address=mac_normalized,
                ip_address=ip,
                vendor=vendor,
                discovery_method="arp",
                interface=interface
            ))
            continue

        # arp -n format: "192.168.1.1  ether  00:1a:2b:3c:4d:5e  C  eth0"
        match = re.match(
            r"^([\d.]+)\s+\w+\s+([0-9a-fA-F:]{17})\s+\w+\s+(\S+)",
            line
        )
        if match:
            ip, mac, interface = match.groups()
            mac_normalized = mac.upper()
            vendor = get_vendor_from_mac(mac_normalized)

            devices.append(DiscoveredDevice(
                mac_address=mac_normalized,
                ip_address=ip,
                vendor=vendor,
                discovery_method="arp",
                interface=interface
            ))

    return devices


def discover_devices() -> list[DiscoveredDevice]:
    """Run ARP discovery and return list of devices."""
    devices = []

    if sys.platform == "win32":
        # Windows: use arp -a
        try:
            result = subprocess.run(
                ["arp", "-a"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                devices = parse_windows_arp(result.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"[Discovery] ARP scan failed: {e}", file=sys.stderr)
    else:
        # Linux/Mac: try ip neigh first, fall back to arp -n
        try:
            result = subprocess.run(
                ["ip", "neigh"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                devices = parse_linux_arp(result.stdout)
        except FileNotFoundError:
            # Fallback to arp -n
            try:
                result = subprocess.run(
                    ["arp", "-n"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    devices = parse_linux_arp(result.stdout)
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                print(f"[Discovery] ARP scan failed: {e}", file=sys.stderr)

    return devices


def determine_vlan_from_ip(ip: str) -> Optional[int]:
    """Determine VLAN ID from IP address based on subnet mapping."""
    # Map IP ranges to VLAN IDs
    vlan_mapping = {
        "192.168.10.": 10,  # MGMT
        "192.168.20.": 20,  # CORE/SERVERS
        "192.168.30.": 30,  # CLIENTS
        "192.168.40.": 40,  # IoT
        "192.168.50.": 50,  # LAB/ROBOTICS
    }

    for prefix, vlan_id in vlan_mapping.items():
        if ip.startswith(prefix):
            return vlan_id

    return None


def write_to_neo4j(devices: list[DiscoveredDevice], verbose: bool = False):
    """Write discovered devices to Neo4j."""
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("[Discovery] neo4j package not installed. Run: pip install neo4j", file=sys.stderr)
        return

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")
    database = os.environ.get("NEO4J_DATABASE", "homelab")

    if not password:
        print("[Discovery] NEO4J_PASSWORD environment variable not set", file=sys.stderr)
        return

    driver = GraphDatabase.driver(uri, auth=(user, password))

    try:
        with driver.session() as session:
            # Create scan record
            scan_id = f"scan:{datetime.now().isoformat()}"
            scan_result = session.run(
                f"""
                USE {database}
                CREATE (s:DiscoveryScan {{
                    scan_id: $scan_id,
                    scan_type: 'arp',
                    timestamp: datetime(),
                    devices_found: $device_count,
                    platform: $platform
                }})
                RETURN s.scan_id as id
                """,
                scan_id=scan_id,
                device_count=len(devices),
                platform=sys.platform
            )
            scan_record = scan_result.single()
            if verbose:
                print(f"[Discovery] Created scan record: {scan_record['id']}")

            # Upsert each device
            for device in devices:
                vlan_id = determine_vlan_from_ip(device.ip_address)

                result = session.run(
                    f"""
                    USE {database}
                    MERGE (d:DiscoveredDevice {{mac_address: $mac}})
                    ON CREATE SET
                        d.first_seen = datetime(),
                        d.ip_address = $ip,
                        d.hostname = $hostname,
                        d.vendor = $vendor,
                        d.discovery_method = $method
                    ON MATCH SET
                        d.last_seen = datetime(),
                        d.ip_address = $ip,
                        d.hostname = $hostname

                    WITH d
                    MATCH (s:DiscoveryScan {{scan_id: $scan_id}})
                    MERGE (d)-[:FOUND_IN]->(s)

                    WITH d
                    OPTIONAL MATCH (v:VLAN {{vlan_id: $vlan_id}})
                    WHERE $vlan_id IS NOT NULL
                    FOREACH (_ IN CASE WHEN v IS NOT NULL THEN [1] ELSE [] END |
                        MERGE (d)-[:ON_SUBNET]->(v)
                    )

                    WITH d
                    OPTIONAL MATCH (h:PhysicalHost)
                    WHERE h.ip_address = $ip OR h.ip_mgmt = $ip OR h.ip_data = $ip
                    FOREACH (_ IN CASE WHEN h IS NOT NULL THEN [1] ELSE [] END |
                        MERGE (d)-[:IDENTIFIED_AS]->(h)
                    )

                    RETURN d.mac_address as mac, d.ip_address as ip
                    """,
                    mac=device.mac_address,
                    ip=device.ip_address,
                    hostname=device.hostname,
                    vendor=device.vendor,
                    method=device.discovery_method,
                    scan_id=scan_id,
                    vlan_id=vlan_id
                )

                record = result.single()
                if verbose:
                    vendor_str = f" ({device.vendor})" if device.vendor else ""
                    vlan_str = f" [VLAN {vlan_id}]" if vlan_id else ""
                    print(f"  {record['mac']} -> {record['ip']}{vendor_str}{vlan_str}")

            print(f"[Discovery] Logged {len(devices)} devices to Neo4j ({database})")

    finally:
        driver.close()


def main():
    parser = argparse.ArgumentParser(
        description="Discover network devices and log to Neo4j"
    )
    parser.add_argument(
        "--scan-only",
        action="store_true",
        help="Only scan, don't write to Neo4j"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    args = parser.parse_args()

    print("[Discovery] Scanning network...", file=sys.stderr)
    devices = discover_devices()

    if not devices:
        print("[Discovery] No devices found", file=sys.stderr)
        return

    print(f"[Discovery] Found {len(devices)} devices", file=sys.stderr)

    if args.json:
        output = [
            {
                "mac_address": d.mac_address,
                "ip_address": d.ip_address,
                "hostname": d.hostname,
                "vendor": d.vendor,
                "vlan_id": determine_vlan_from_ip(d.ip_address)
            }
            for d in devices
        ]
        print(json.dumps(output, indent=2))
    elif args.verbose or args.scan_only:
        print("\nDiscovered Devices:")
        print("-" * 70)
        for d in devices:
            vendor_str = f" ({d.vendor})" if d.vendor else ""
            vlan_id = determine_vlan_from_ip(d.ip_address)
            vlan_str = f" [VLAN {vlan_id}]" if vlan_id else ""
            print(f"  {d.mac_address}  {d.ip_address:15}{vendor_str}{vlan_str}")
        print("-" * 70)

    if not args.scan_only:
        write_to_neo4j(devices, verbose=args.verbose)


if __name__ == "__main__":
    main()
