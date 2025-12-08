#!/usr/bin/env python3
"""
Neo4j Homelab Writer Utilities

Provides CRUD operations for the homelab network graph database.

Usage:
    from neo4j_homelab_writer import HomelabWriter

    with HomelabWriter() as writer:
        writer.add_device("new-device", "192.168.30.100", vlan_id=30)
        devices = writer.list_devices()
        writer.update_device("new-device", status="offline")
        writer.delete_device("new-device")

Environment Variables:
    NEO4J_URI      - Neo4j connection URI (default: bolt://localhost:7687)
    NEO4J_USER     - Neo4j username (default: neo4j)
    NEO4J_PASSWORD - Neo4j password (required)
    NEO4J_DATABASE - Target database (default: homelab)
"""

import os
import json
from datetime import datetime
from typing import Any, Optional
from dataclasses import dataclass, asdict

try:
    from neo4j import GraphDatabase
except ImportError:
    print("neo4j package not installed. Run: pip install neo4j")
    GraphDatabase = None


@dataclass
class NetworkNode:
    """Base class for network node data."""
    name: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class DiscoveredDeviceData:
    """Discovered device data structure."""
    mac_address: str
    ip_address: str
    hostname: Optional[str] = None
    vendor: Optional[str] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    vlan_id: Optional[int] = None


class HomelabWriter:
    """Neo4j writer for homelab network data."""

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None
    ):
        self.uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.environ.get("NEO4J_USER", "neo4j")
        self.password = password or os.environ.get("NEO4J_PASSWORD")
        self.database = database or os.environ.get("NEO4J_DATABASE", "homelab")

        if not self.password:
            raise ValueError("NEO4J_PASSWORD is required")

        if GraphDatabase is None:
            raise ImportError("neo4j package not installed")

        self.driver = GraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password)
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Close database connection."""
        if self.driver:
            self.driver.close()

    def _query(self, cypher: str, **params) -> list[dict]:
        """Execute a read query and return results."""
        with self.driver.session() as session:
            result = session.run(f"USE {self.database}\n{cypher}", **params)
            return [dict(record) for record in result]

    def _write(self, cypher: str, **params) -> dict:
        """Execute a write query and return summary."""
        with self.driver.session() as session:
            result = session.run(f"USE {self.database}\n{cypher}", **params)
            summary = result.consume()
            return {
                "nodes_created": summary.counters.nodes_created,
                "nodes_deleted": summary.counters.nodes_deleted,
                "relationships_created": summary.counters.relationships_created,
                "relationships_deleted": summary.counters.relationships_deleted,
                "properties_set": summary.counters.properties_set,
            }

    # ==================== READ OPERATIONS ====================

    def list_vlans(self) -> list[dict]:
        """List all VLANs."""
        return self._query("""
            MATCH (v:VLAN)
            RETURN v.vlan_id as vlan_id, v.name as name, v.cidr as cidr, v.purpose as purpose
            ORDER BY v.vlan_id
        """)

    def list_hosts(self) -> list[dict]:
        """List all physical hosts."""
        return self._query("""
            MATCH (h:PhysicalHost)
            OPTIONAL MATCH (h)-[:MEMBER_OF]->(v:VLAN)
            RETURN h.host_id as host_id, h.name as name, h.role as role,
                   h.ip_address as ip_address, collect(v.vlan_id) as vlans
            ORDER BY h.name
        """)

    def list_services(self) -> list[dict]:
        """List all Docker services."""
        return self._query("""
            MATCH (s:DockerService)-[:RUNS_ON]->(h:PhysicalHost)
            RETURN s.service_id as service_id, s.name as name, s.port as port,
                   s.description as description, h.name as host
            ORDER BY s.name
        """)

    def list_discovered_devices(self, include_identified: bool = True) -> list[dict]:
        """List all discovered devices."""
        query = """
            MATCH (d:DiscoveredDevice)
            OPTIONAL MATCH (d)-[:ON_SUBNET]->(v:VLAN)
            OPTIONAL MATCH (d)-[:IDENTIFIED_AS]->(h:PhysicalHost)
            RETURN d.mac_address as mac_address, d.ip_address as ip_address,
                   d.vendor as vendor, d.first_seen as first_seen,
                   d.last_seen as last_seen, v.vlan_id as vlan_id,
                   h.name as identified_as
            ORDER BY d.last_seen DESC
        """
        if not include_identified:
            query = """
                MATCH (d:DiscoveredDevice)
                WHERE NOT (d)-[:IDENTIFIED_AS]->(:PhysicalHost)
                OPTIONAL MATCH (d)-[:ON_SUBNET]->(v:VLAN)
                RETURN d.mac_address as mac_address, d.ip_address as ip_address,
                       d.vendor as vendor, d.first_seen as first_seen,
                       d.last_seen as last_seen, v.vlan_id as vlan_id
                ORDER BY d.last_seen DESC
            """
        return self._query(query)

    def get_network_summary(self) -> dict:
        """Get a summary of the network topology."""
        results = self._query("""
            MATCH (n)
            RETURN labels(n)[0] as label, count(*) as count
            ORDER BY count DESC
        """)
        return {r["label"]: r["count"] for r in results}

    def get_vlan_members(self, vlan_id: int) -> list[dict]:
        """Get all members of a specific VLAN."""
        return self._query("""
            MATCH (v:VLAN {vlan_id: $vlan_id})<-[:MEMBER_OF|ON_SUBNET]-(n)
            RETURN labels(n)[0] as type, n.name as name, n.ip_address as ip_address,
                   n.mac_address as mac_address
            ORDER BY type, name
        """, vlan_id=vlan_id)

    # ==================== WRITE OPERATIONS ====================

    def add_discovered_device(
        self,
        mac_address: str,
        ip_address: str,
        hostname: Optional[str] = None,
        vendor: Optional[str] = None,
        vlan_id: Optional[int] = None
    ) -> dict:
        """Add or update a discovered device."""
        return self._write("""
            MERGE (d:DiscoveredDevice {mac_address: $mac})
            ON CREATE SET
                d.first_seen = datetime(),
                d.ip_address = $ip,
                d.hostname = $hostname,
                d.vendor = $vendor
            ON MATCH SET
                d.last_seen = datetime(),
                d.ip_address = $ip,
                d.hostname = COALESCE($hostname, d.hostname)

            WITH d
            OPTIONAL MATCH (v:VLAN {vlan_id: $vlan_id})
            WHERE $vlan_id IS NOT NULL
            FOREACH (_ IN CASE WHEN v IS NOT NULL THEN [1] ELSE [] END |
                MERGE (d)-[:ON_SUBNET]->(v)
            )

            RETURN d
        """, mac=mac_address, ip=ip_address, hostname=hostname,
             vendor=vendor, vlan_id=vlan_id)

    def add_physical_host(
        self,
        host_id: str,
        name: str,
        role: str,
        ip_address: Optional[str] = None,
        vlan_id: Optional[int] = None,
        **extra_props
    ) -> dict:
        """Add a new physical host."""
        props = {
            "host_id": host_id,
            "name": name,
            "role": role,
            "ip_address": ip_address,
            **extra_props
        }
        props_str = ", ".join(f"{k}: ${k}" for k in props.keys())

        result = self._write(f"""
            CREATE (h:PhysicalHost {{{props_str}, created_at: datetime()}})
            WITH h
            OPTIONAL MATCH (v:VLAN {{vlan_id: $vlan_id}})
            WHERE $vlan_id IS NOT NULL
            FOREACH (_ IN CASE WHEN v IS NOT NULL THEN [1] ELSE [] END |
                CREATE (h)-[:MEMBER_OF]->(v)
            )
            RETURN h
        """, **props, vlan_id=vlan_id)

        return result

    def add_docker_service(
        self,
        service_id: str,
        name: str,
        port: int,
        description: str,
        host_id: str = "terramaster-nas"
    ) -> dict:
        """Add a new Docker service."""
        return self._write("""
            MATCH (h:PhysicalHost {host_id: $host_id})
            CREATE (s:DockerService {
                service_id: $service_id,
                name: $name,
                port: $port,
                description: $description,
                created_at: datetime()
            })-[:RUNS_ON]->(h)
            RETURN s
        """, service_id=service_id, name=name, port=port,
             description=description, host_id=host_id)

    def link_discovered_to_host(self, mac_address: str, host_id: str) -> dict:
        """Link a discovered device to a known physical host."""
        return self._write("""
            MATCH (d:DiscoveredDevice {mac_address: $mac})
            MATCH (h:PhysicalHost {host_id: $host_id})
            MERGE (d)-[:IDENTIFIED_AS]->(h)
            RETURN d, h
        """, mac=mac_address, host_id=host_id)

    def update_host_status(self, host_id: str, status: str) -> dict:
        """Update a host's status."""
        return self._write("""
            MATCH (h:PhysicalHost {host_id: $host_id})
            SET h.status = $status, h.updated_at = datetime()
            RETURN h
        """, host_id=host_id, status=status)

    def delete_discovered_device(self, mac_address: str) -> dict:
        """Delete a discovered device."""
        return self._write("""
            MATCH (d:DiscoveredDevice {mac_address: $mac})
            DETACH DELETE d
        """, mac=mac_address)

    def purge_old_discoveries(self, days: int = 30) -> dict:
        """Delete discovered devices not seen in the last N days."""
        return self._write(f"""
            MATCH (d:DiscoveredDevice)
            WHERE d.last_seen < datetime() - duration('P{days}D')
            DETACH DELETE d
        """)


def main():
    """CLI interface for HomelabWriter."""
    import argparse

    parser = argparse.ArgumentParser(description="Homelab Neo4j utilities")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # List commands
    list_parser = subparsers.add_parser("list", help="List entities")
    list_parser.add_argument(
        "entity",
        choices=["vlans", "hosts", "services", "discovered", "summary"],
        help="Entity type to list"
    )
    list_parser.add_argument(
        "--unidentified",
        action="store_true",
        help="Only show unidentified discovered devices"
    )

    # VLAN members
    vlan_parser = subparsers.add_parser("vlan", help="Show VLAN members")
    vlan_parser.add_argument("vlan_id", type=int, help="VLAN ID")

    # Add discovered device
    add_parser = subparsers.add_parser("add-device", help="Add discovered device")
    add_parser.add_argument("mac", help="MAC address")
    add_parser.add_argument("ip", help="IP address")
    add_parser.add_argument("--vendor", help="Vendor name")
    add_parser.add_argument("--vlan", type=int, help="VLAN ID")

    # Link device
    link_parser = subparsers.add_parser("link", help="Link discovered to host")
    link_parser.add_argument("mac", help="MAC address")
    link_parser.add_argument("host_id", help="Host ID")

    # Purge old
    purge_parser = subparsers.add_parser("purge", help="Purge old discoveries")
    purge_parser.add_argument("--days", type=int, default=30, help="Days threshold")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        with HomelabWriter() as writer:
            if args.command == "list":
                if args.entity == "vlans":
                    results = writer.list_vlans()
                elif args.entity == "hosts":
                    results = writer.list_hosts()
                elif args.entity == "services":
                    results = writer.list_services()
                elif args.entity == "discovered":
                    results = writer.list_discovered_devices(
                        include_identified=not args.unidentified
                    )
                elif args.entity == "summary":
                    results = writer.get_network_summary()

                print(json.dumps(results, indent=2, default=str))

            elif args.command == "vlan":
                results = writer.get_vlan_members(args.vlan_id)
                print(json.dumps(results, indent=2, default=str))

            elif args.command == "add-device":
                result = writer.add_discovered_device(
                    args.mac, args.ip,
                    vendor=args.vendor,
                    vlan_id=args.vlan
                )
                print(f"Added device: {result}")

            elif args.command == "link":
                result = writer.link_discovered_to_host(args.mac, args.host_id)
                print(f"Linked: {result}")

            elif args.command == "purge":
                result = writer.purge_old_discoveries(args.days)
                print(f"Purged: {result}")

    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    main()
