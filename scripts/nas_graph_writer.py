#!/usr/bin/env python3
"""
NAS Service Graph Writer

Populates the Neo4j homelab database with Docker service data from the Terramaster NAS.
Creates Machine, DockerStack, DockerService, StorageVolume, and DockerNetwork nodes
with appropriate relationships.

Usage:
    python scripts/nas_graph_writer.py              # Populate all NAS data
    python scripts/nas_graph_writer.py --dry-run    # Preview without writing

Environment Variables:
    NEO4J_URI      - Neo4j connection URI (default: bolt://localhost:7687)
    NEO4J_USER     - Neo4j username (default: neo4j)
    NEO4J_PASSWORD - Neo4j password (required)
    NEO4J_DATABASE - Target database (default: homelab)
"""

import os
import sys
import argparse
from datetime import datetime
from typing import Optional

try:
    from neo4j import GraphDatabase
except ImportError:
    print("neo4j package not installed. Run: pip install neo4j")
    sys.exit(1)


# =============================================================================
# NAS SERVICE DATA
# =============================================================================

MACHINE_DATA = {
    "machine_id": "terramaster-nas",
    "hostname": "BOX-NAS",
    "ip_address": "192.168.1.20",
    "os": "Linux 6.1.120+",
    "os_family": "TOS",
    "role": "NAS/Docker Host",
    "cpu": "Intel i3-N305",
    "ram_gb": 32,
    "total_storage_tb": 11.0,
    "filesystem": "BTRFS",
    "timezone": "Australia/Brisbane",
}

DOCKER_STACKS = [
    {
        "stack_id": "media-stack",
        "name": "media",
        "compose_file": "media_stack.yml",
        "category": "media",
        "description": "Media automation and streaming",
    },
    {
        "stack_id": "monitoring-stack",
        "name": "monitoring",
        "compose_file": "monitoring_stack.yml",
        "category": "monitoring",
        "description": "System and container monitoring",
    },
    {
        "stack_id": "immich-stack",
        "name": "immich",
        "compose_file": "immich_stack.yml",
        "category": "photos",
        "description": "Photo management and ML",
    },
    {
        "stack_id": "documents-stack",
        "name": "documents",
        "compose_file": "documents_stack.yml",
        "category": "documents",
        "description": "Document management and OCR",
    },
    {
        "stack_id": "utilities-stack",
        "name": "utilities",
        "compose_file": "utilities_stack.yml",
        "category": "utilities",
        "description": "Home automation and development tools",
    },
    {
        "stack_id": "security-stack",
        "name": "security",
        "compose_file": "security_stack.yml",
        "category": "security",
        "description": "Password management and VPN",
    },
]

DOCKER_SERVICES = [
    # Media Stack
    {"service_id": "jellyfin", "name": "jellyfin", "image": "jellyfin/jellyfin:latest", "port": 8096, "stack_id": "media-stack", "purpose": "Media streaming server", "category": "media"},
    {"service_id": "gluetun", "name": "gluetun", "image": "qmcgaw/gluetun:latest", "port": 8001, "stack_id": "media-stack", "purpose": "VPN gateway (ExpressVPN)", "category": "network"},
    {"service_id": "qbittorrent", "name": "qbittorrent", "image": "lscr.io/linuxserver/qbittorrent:latest", "port": 8080, "stack_id": "media-stack", "purpose": "Torrent client", "category": "downloads"},
    {"service_id": "sonarr", "name": "sonarr", "image": "lscr.io/linuxserver/sonarr:latest", "port": 8989, "stack_id": "media-stack", "purpose": "TV show automation", "category": "media"},
    {"service_id": "radarr", "name": "radarr", "image": "lscr.io/linuxserver/radarr:latest", "port": 7878, "stack_id": "media-stack", "purpose": "Movie automation", "category": "media"},
    {"service_id": "prowlarr", "name": "prowlarr", "image": "lscr.io/linuxserver/prowlarr:latest", "port": 9696, "stack_id": "media-stack", "purpose": "Indexer management", "category": "media"},
    {"service_id": "bazarr", "name": "bazarr", "image": "lscr.io/linuxserver/bazarr:latest", "port": 6767, "stack_id": "media-stack", "purpose": "Subtitle downloads", "category": "media"},
    {"service_id": "jellyseerr", "name": "jellyseerr", "image": "fallenbagel/jellyseerr:latest", "port": 5055, "stack_id": "media-stack", "purpose": "Content request UI", "category": "media"},

    # Monitoring Stack
    {"service_id": "grafana", "name": "grafana", "image": "grafana/grafana:latest", "port": 3000, "stack_id": "monitoring-stack", "purpose": "Visualization dashboards", "category": "monitoring"},
    {"service_id": "prometheus", "name": "prometheus", "image": "prom/prometheus:latest", "port": 9090, "stack_id": "monitoring-stack", "purpose": "Metrics collection", "category": "monitoring"},
    {"service_id": "cadvisor", "name": "cadvisor", "image": "gcr.io/cadvisor/cadvisor:latest", "port": 8081, "stack_id": "monitoring-stack", "purpose": "Container metrics", "category": "monitoring"},
    {"service_id": "node-exporter", "name": "node-exporter", "image": "prom/node-exporter:latest", "port": 9100, "stack_id": "monitoring-stack", "purpose": "Host system metrics", "category": "monitoring"},
    {"service_id": "exportarr-sonarr", "name": "exportarr-sonarr", "image": "ghcr.io/onedr0p/exportarr:latest", "port": 9707, "stack_id": "monitoring-stack", "purpose": "Sonarr metrics exporter", "category": "monitoring"},
    {"service_id": "exportarr-radarr", "name": "exportarr-radarr", "image": "ghcr.io/onedr0p/exportarr:latest", "port": 9708, "stack_id": "monitoring-stack", "purpose": "Radarr metrics exporter", "category": "monitoring"},
    {"service_id": "qbittorrent-exporter", "name": "qbittorrent-exporter", "image": "esanchezm/prometheus-qbittorrent-exporter:latest", "port": 8008, "stack_id": "monitoring-stack", "purpose": "qBittorrent metrics", "category": "monitoring"},

    # Immich Stack
    {"service_id": "immich-server", "name": "immich-server", "image": "ghcr.io/immich-app/immich-server:release", "port": 2283, "stack_id": "immich-stack", "purpose": "Photo management server", "category": "photos"},
    {"service_id": "immich-machine-learning", "name": "immich-machine-learning", "image": "ghcr.io/immich-app/immich-machine-learning:release", "port": None, "stack_id": "immich-stack", "purpose": "AI/ML for photos", "category": "photos"},
    {"service_id": "immich-postgres", "name": "immich-postgres", "image": "tensorchord/pgvecto-rs:pg16-v0.3.0", "port": None, "stack_id": "immich-stack", "purpose": "Vector database", "category": "database"},
    {"service_id": "immich-redis", "name": "immich-redis", "image": "redis:7-alpine", "port": None, "stack_id": "immich-stack", "purpose": "Cache", "category": "cache"},

    # Documents Stack
    {"service_id": "paperless-webserver", "name": "paperless-webserver", "image": "ghcr.io/paperless-ngx/paperless-ngx:latest", "port": 8000, "stack_id": "documents-stack", "purpose": "Document management", "category": "documents"},
    {"service_id": "paperless-db", "name": "paperless-db", "image": "postgres:16-alpine", "port": None, "stack_id": "documents-stack", "purpose": "Database", "category": "database"},
    {"service_id": "paperless-redis", "name": "paperless-redis", "image": "redis:7-alpine", "port": None, "stack_id": "documents-stack", "purpose": "Cache", "category": "cache"},
    {"service_id": "paperless-gotenberg", "name": "paperless-gotenberg", "image": "gotenberg/gotenberg:8", "port": None, "stack_id": "documents-stack", "purpose": "PDF generation", "category": "documents"},
    {"service_id": "paperless-tika", "name": "paperless-tika", "image": "apache/tika:latest", "port": None, "stack_id": "documents-stack", "purpose": "Text extraction", "category": "documents"},

    # Utilities Stack
    {"service_id": "homeassistant", "name": "homeassistant", "image": "ghcr.io/home-assistant/home-assistant:stable", "port": 8123, "stack_id": "utilities-stack", "purpose": "Home automation", "category": "automation"},
    {"service_id": "code-server", "name": "code-server", "image": "lscr.io/linuxserver/code-server:latest", "port": 8443, "stack_id": "utilities-stack", "purpose": "VS Code in browser", "category": "development"},
    {"service_id": "homepage", "name": "homepage", "image": "ghcr.io/gethomepage/homepage:latest", "port": 3001, "stack_id": "utilities-stack", "purpose": "Dashboard", "category": "utilities"},
    {"service_id": "portainer", "name": "portainer", "image": "portainer/portainer-ce:latest", "port": 9443, "stack_id": "utilities-stack", "purpose": "Docker management", "category": "management"},

    # Security Stack
    {"service_id": "vaultwarden", "name": "vaultwarden", "image": "vaultwarden/server:latest", "port": 8088, "stack_id": "security-stack", "purpose": "Password manager", "category": "security"},
    {"service_id": "tailscale", "name": "tailscale", "image": "tailscale/tailscale:latest", "port": None, "stack_id": "security-stack", "purpose": "VPN mesh network", "category": "network"},

    # Additional
    {"service_id": "recyclarr", "name": "recyclarr", "image": "ghcr.io/recyclarr/recyclarr:latest", "port": None, "stack_id": "media-stack", "purpose": "Quality profile sync", "category": "media"},
]

STORAGE_VOLUMES = [
    {"volume_id": "media-movies", "path": "/Volume1/media/movies", "purpose": "Movie files", "category": "media"},
    {"volume_id": "media-tv", "path": "/Volume1/media/tv", "purpose": "TV shows", "category": "media"},
    {"volume_id": "media-music", "path": "/Volume1/media/music", "purpose": "Music files", "category": "media"},
    {"volume_id": "media-photos", "path": "/Volume1/media/photos", "purpose": "Photo library", "category": "media"},
    {"volume_id": "media-downloads", "path": "/Volume1/media/downloads", "purpose": "Download staging", "category": "downloads"},
    {"volume_id": "media-documents", "path": "/Volume1/media/documents", "purpose": "Document intake", "category": "documents"},
    {"volume_id": "docker-configs", "path": "/Volume1/docker/configs", "purpose": "Service configurations", "category": "config"},
    {"volume_id": "docker-volumes", "path": "/Volume1/docker/volumes", "purpose": "Persistent data", "category": "data"},
    {"volume_id": "projects", "path": "/Volume1/projects", "purpose": "Development projects", "category": "development"},
    {"volume_id": "backups", "path": "/Volume1/backups", "purpose": "Backup storage", "category": "backups"},
]

DOCKER_NETWORKS = [
    {"network_id": "media-net", "name": "media_net", "driver": "bridge", "purpose": "Media services network"},
    {"network_id": "monitoring-net", "name": "monitoring_net", "driver": "bridge", "purpose": "Monitoring services network"},
]

# Service -> Volume relationships (service_id, volume_id, access_type)
SERVICE_VOLUME_RELATIONS = [
    # Jellyfin reads from media libraries
    ("jellyfin", "media-movies", "reads"),
    ("jellyfin", "media-tv", "reads"),
    ("jellyfin", "media-music", "reads"),
    ("jellyfin", "media-photos", "reads"),

    # Radarr/Sonarr manage media
    ("radarr", "media-movies", "writes"),
    ("radarr", "media-downloads", "reads"),
    ("sonarr", "media-tv", "writes"),
    ("sonarr", "media-downloads", "reads"),

    # qBittorrent downloads
    ("qbittorrent", "media-downloads", "writes"),

    # Immich manages photos
    ("immich-server", "media-photos", "writes"),

    # Paperless manages documents
    ("paperless-webserver", "media-documents", "reads"),

    # Code-server accesses projects
    ("code-server", "projects", "writes"),
]

# Service -> Service relationships (from, to, relationship_type)
SERVICE_RELATIONS = [
    # VPN dependencies
    ("qbittorrent", "gluetun", "ROUTES_THROUGH"),

    # Indexer relationships
    ("prowlarr", "sonarr", "INDEXES_FOR"),
    ("prowlarr", "radarr", "INDEXES_FOR"),

    # Download automation
    ("sonarr", "qbittorrent", "SENDS_TO"),
    ("radarr", "qbittorrent", "SENDS_TO"),

    # Subtitle management
    ("bazarr", "sonarr", "FETCHES_FOR"),
    ("bazarr", "radarr", "FETCHES_FOR"),

    # Request flow
    ("jellyseerr", "sonarr", "REQUESTS_FROM"),
    ("jellyseerr", "radarr", "REQUESTS_FROM"),
    ("jellyseerr", "jellyfin", "AUTHENTICATES_WITH"),

    # Monitoring relationships
    ("exportarr-sonarr", "sonarr", "MONITORS"),
    ("exportarr-radarr", "radarr", "MONITORS"),
    ("qbittorrent-exporter", "qbittorrent", "MONITORS"),
    ("prometheus", "grafana", "FEEDS_INTO"),
    ("cadvisor", "prometheus", "EXPORTS_TO"),
    ("node-exporter", "prometheus", "EXPORTS_TO"),
    ("exportarr-sonarr", "prometheus", "EXPORTS_TO"),
    ("exportarr-radarr", "prometheus", "EXPORTS_TO"),
    ("qbittorrent-exporter", "prometheus", "EXPORTS_TO"),

    # Immich internal
    ("immich-server", "immich-postgres", "USES_DATABASE"),
    ("immich-server", "immich-redis", "USES_CACHE"),
    ("immich-server", "immich-machine-learning", "USES_ML"),

    # Paperless internal
    ("paperless-webserver", "paperless-db", "USES_DATABASE"),
    ("paperless-webserver", "paperless-redis", "USES_CACHE"),
    ("paperless-webserver", "paperless-gotenberg", "USES_PDF"),
    ("paperless-webserver", "paperless-tika", "USES_OCR"),
]


# =============================================================================
# GRAPH WRITER
# =============================================================================

class NASGraphWriter:
    """Neo4j writer for NAS infrastructure data."""

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
        dry_run: bool = False
    ):
        self.uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.environ.get("NEO4J_USER", "neo4j")
        self.password = password or os.environ.get("NEO4J_PASSWORD")
        self.database = database or os.environ.get("NEO4J_DATABASE", "homelab")
        self.dry_run = dry_run

        if not self.password:
            raise ValueError("NEO4J_PASSWORD environment variable is required")

        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        self.stats = {
            "nodes_created": 0,
            "relationships_created": 0,
            "properties_set": 0,
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        if self.driver:
            self.driver.close()

    def _execute(self, cypher: str, **params) -> dict:
        """Execute a Cypher query."""
        full_query = f"USE {self.database}\n{cypher}"

        if self.dry_run:
            print(f"[DRY RUN] Would execute:\n{full_query}")
            print(f"  Params: {params}\n")
            return {}

        with self.driver.session() as session:
            result = session.run(full_query, **params)
            summary = result.consume()

            self.stats["nodes_created"] += summary.counters.nodes_created
            self.stats["relationships_created"] += summary.counters.relationships_created
            self.stats["properties_set"] += summary.counters.properties_set

            return {
                "nodes_created": summary.counters.nodes_created,
                "relationships_created": summary.counters.relationships_created,
            }

    def create_machine(self, data: dict) -> dict:
        """Create or update the Machine node."""
        print(f"Creating Machine: {data['machine_id']}")
        return self._execute("""
            MERGE (m:Machine {machine_id: $machine_id})
            ON CREATE SET m.created_at = datetime()
            SET m.hostname = $hostname,
                m.ip_address = $ip_address,
                m.os = $os,
                m.os_family = $os_family,
                m.role = $role,
                m.cpu = $cpu,
                m.ram_gb = $ram_gb,
                m.total_storage_tb = $total_storage_tb,
                m.filesystem = $filesystem,
                m.timezone = $timezone,
                m.updated_at = datetime()
        """, **data)

    def create_docker_stack(self, data: dict) -> dict:
        """Create or update a DockerStack node."""
        print(f"  Creating DockerStack: {data['name']}")
        return self._execute("""
            MERGE (st:DockerStack {stack_id: $stack_id})
            ON CREATE SET st.created_at = datetime()
            SET st.name = $name,
                st.compose_file = $compose_file,
                st.category = $category,
                st.description = $description,
                st.machine_id = 'terramaster-nas',
                st.updated_at = datetime()

            WITH st
            MATCH (m:Machine {machine_id: 'terramaster-nas'})
            MERGE (st)-[:DEPLOYED_ON]->(m)
        """, **data)

    def create_docker_service(self, data: dict) -> dict:
        """Create or update a DockerService node."""
        print(f"    Creating DockerService: {data['name']}")
        return self._execute("""
            MERGE (s:DockerService {service_id: $service_id})
            ON CREATE SET s.created_at = datetime()
            SET s.name = $name,
                s.image = $image,
                s.port = $port,
                s.purpose = $purpose,
                s.category = $category,
                s.stack_id = $stack_id,
                s.machine_id = 'terramaster-nas',
                s.status = 'running',
                s.updated_at = datetime()

            WITH s
            MATCH (m:Machine {machine_id: 'terramaster-nas'})
            MERGE (s)-[:RUNS_ON]->(m)

            WITH s
            MATCH (st:DockerStack {stack_id: $stack_id})
            MERGE (s)-[:PART_OF_STACK]->(st)
        """, **data)

    def create_storage_volume(self, data: dict) -> dict:
        """Create or update a StorageVolume node."""
        print(f"  Creating StorageVolume: {data['path']}")
        return self._execute("""
            MERGE (v:StorageVolume {volume_id: $volume_id})
            ON CREATE SET v.created_at = datetime()
            SET v.path = $path,
                v.purpose = $purpose,
                v.category = $category,
                v.filesystem = 'btrfs',
                v.machine_id = 'terramaster-nas',
                v.updated_at = datetime()

            WITH v
            MATCH (m:Machine {machine_id: 'terramaster-nas'})
            MERGE (v)-[:MOUNTED_ON]->(m)
        """, **data)

    def create_docker_network(self, data: dict) -> dict:
        """Create or update a DockerNetwork node."""
        print(f"  Creating DockerNetwork: {data['name']}")
        return self._execute("""
            MERGE (n:DockerNetwork {network_id: $network_id})
            ON CREATE SET n.created_at = datetime()
            SET n.name = $name,
                n.driver = $driver,
                n.purpose = $purpose,
                n.machine_id = 'terramaster-nas',
                n.updated_at = datetime()

            WITH n
            MATCH (m:Machine {machine_id: 'terramaster-nas'})
            MERGE (n)-[:DEFINED_ON]->(m)
        """, **data)

    def create_service_volume_relation(self, service_id: str, volume_id: str, access_type: str) -> dict:
        """Create a relationship between a service and a volume."""
        rel_type = "WRITES_TO" if access_type == "writes" else "READS_FROM"
        print(f"    Linking {service_id} -{rel_type}-> {volume_id}")
        return self._execute(f"""
            MATCH (s:DockerService {{service_id: $service_id}})
            MATCH (v:StorageVolume {{volume_id: $volume_id}})
            MERGE (s)-[:{rel_type}]->(v)
        """, service_id=service_id, volume_id=volume_id)

    def create_service_relation(self, from_service: str, to_service: str, rel_type: str) -> dict:
        """Create a relationship between two services."""
        print(f"    Linking {from_service} -{rel_type}-> {to_service}")
        return self._execute(f"""
            MATCH (s1:DockerService {{service_id: $from_service}})
            MATCH (s2:DockerService {{service_id: $to_service}})
            MERGE (s1)-[:{rel_type}]->(s2)
        """, from_service=from_service, to_service=to_service)

    def populate_all(self):
        """Populate the entire NAS infrastructure graph."""
        print("=" * 60)
        print("NAS Graph Writer - Populating homelab database")
        print("=" * 60)

        # 1. Create Machine
        print("\n[1/7] Creating Machine node...")
        self.create_machine(MACHINE_DATA)

        # 2. Create Docker Stacks
        print("\n[2/7] Creating DockerStack nodes...")
        for stack in DOCKER_STACKS:
            self.create_docker_stack(stack)

        # 3. Create Docker Services
        print("\n[3/7] Creating DockerService nodes...")
        for service in DOCKER_SERVICES:
            self.create_docker_service(service)

        # 4. Create Storage Volumes
        print("\n[4/7] Creating StorageVolume nodes...")
        for volume in STORAGE_VOLUMES:
            self.create_storage_volume(volume)

        # 5. Create Docker Networks
        print("\n[5/7] Creating DockerNetwork nodes...")
        for network in DOCKER_NETWORKS:
            self.create_docker_network(network)

        # 6. Create Service-Volume relationships
        print("\n[6/7] Creating service-volume relationships...")
        for service_id, volume_id, access_type in SERVICE_VOLUME_RELATIONS:
            self.create_service_volume_relation(service_id, volume_id, access_type)

        # 7. Create Service-Service relationships
        print("\n[7/7] Creating service-service relationships...")
        for from_svc, to_svc, rel_type in SERVICE_RELATIONS:
            self.create_service_relation(from_svc, to_svc, rel_type)

        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"  Nodes created:         {self.stats['nodes_created']}")
        print(f"  Relationships created: {self.stats['relationships_created']}")
        print(f"  Properties set:        {self.stats['properties_set']}")
        print(f"  Database: {self.database}")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Populate Neo4j with NAS infrastructure data")
    parser.add_argument("--dry-run", action="store_true", help="Preview queries without executing")
    parser.add_argument("--database", default=None, help="Override target database")
    args = parser.parse_args()

    try:
        with NASGraphWriter(database=args.database, dry_run=args.dry_run) as writer:
            writer.populate_all()

        if not args.dry_run:
            print("\nGraph population complete!")
            print(f"\nView in Neo4j Browser:")
            print(f"  MATCH (m:Machine)-[*1..2]-(n) RETURN m, n LIMIT 50")

    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
