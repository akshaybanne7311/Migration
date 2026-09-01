"""Read-side repositories -- the only place SELECT SQL lives.

Every consumer (API routes, the dependency graph builder, generators)
reads parsed config through these functions so there is exactly one code
path from "row in SQLite" to "typed domain object."
"""
import sqlite3
from typing import List, Optional

from app.models.domain import (
    AddressFamily,
    Monitor,
    Node,
    Pool,
    PoolMember,
    Profile,
    Vip,
    Vlan,
)


def _row_to_node(row: sqlite3.Row) -> Node:
    return Node(
        name=row["name"],
        address=row["address"],
        address_family=AddressFamily(row["address_family"]),
        partition=row["partition_name"],
        state=row["state"],
        source_stanza_json=row["source_stanza_json"],
    )


class NodeRepository:
    @staticmethod
    def list(conn: sqlite3.Connection) -> List[Node]:
        rows = conn.execute("SELECT * FROM nodes ORDER BY name").fetchall()
        return [_row_to_node(r) for r in rows]

    @staticmethod
    def get(conn: sqlite3.Connection, name: str) -> Optional[Node]:
        row = conn.execute("SELECT * FROM nodes WHERE name = ?", (name,)).fetchone()
        return _row_to_node(row) if row else None

    @staticmethod
    def referencing_pools(conn: sqlite3.Connection, node_name: str) -> List[str]:
        rows = conn.execute(
            "SELECT DISTINCT pool_name FROM pool_members WHERE node_name = ?",
            (node_name,),
        ).fetchall()
        return [r["pool_name"] for r in rows]


class MonitorRepository:
    @staticmethod
    def list(conn: sqlite3.Connection) -> List[Monitor]:
        rows = conn.execute("SELECT * FROM monitors ORDER BY name").fetchall()
        return [
            Monitor(
                name=r["name"],
                monitor_type=r["monitor_type"],
                interval=r["interval"],
                timeout=r["timeout"],
                source_stanza_json=r["source_stanza_json"],
            )
            for r in rows
        ]


def _hydrate_pool(conn: sqlite3.Connection, row: sqlite3.Row) -> Pool:
    name = row["name"]
    member_rows = conn.execute(
        "SELECT * FROM pool_members WHERE pool_name = ? ORDER BY id", (name,)
    ).fetchall()
    members = [
        PoolMember(
            pool_name=m["pool_name"],
            node_name=m["node_name"],
            port=m["port"],
            session_state=m["session_state"],
            connection_limit=m["connection_limit"],
            source_stanza_json=m["source_stanza_json"],
        )
        for m in member_rows
    ]
    monitor_rows = conn.execute(
        "SELECT monitor_name FROM pool_monitors WHERE pool_name = ?", (name,)
    ).fetchall()
    return Pool(
        name=name,
        partition=row["partition_name"],
        monitor_names=[m["monitor_name"] for m in monitor_rows],
        members=members,
        source_stanza_json=row["source_stanza_json"],
    )


class PoolRepository:
    @staticmethod
    def list(conn: sqlite3.Connection) -> List[Pool]:
        rows = conn.execute("SELECT * FROM pools ORDER BY name").fetchall()
        return [_hydrate_pool(conn, r) for r in rows]

    @staticmethod
    def get(conn: sqlite3.Connection, name: str) -> Optional[Pool]:
        row = conn.execute("SELECT * FROM pools WHERE name = ?", (name,)).fetchone()
        return _hydrate_pool(conn, row) if row else None


class VlanRepository:
    @staticmethod
    def list(conn: sqlite3.Connection) -> List[Vlan]:
        import json

        rows = conn.execute("SELECT * FROM vlans ORDER BY name").fetchall()
        return [
            Vlan(
                name=r["name"],
                tag=r["tag"],
                interfaces=json.loads(r["interfaces_json"]),
                source_stanza_json=r["source_stanza_json"],
            )
            for r in rows
        ]

    @staticmethod
    def names_with_local_object(conn: sqlite3.Connection) -> List[str]:
        rows = conn.execute("SELECT name FROM vlans").fetchall()
        return [r["name"] for r in rows]


def _hydrate_vip(conn: sqlite3.Connection, row: sqlite3.Row) -> Vip:
    name = row["name"]
    vlan_rows = conn.execute(
        "SELECT vlan_name FROM vip_vlans WHERE vip_name = ?", (name,)
    ).fetchall()
    profile_rows = conn.execute(
        "SELECT profile_name, context FROM vip_profiles WHERE vip_name = ?", (name,)
    ).fetchall()
    irule_rows = conn.execute(
        "SELECT irule_name FROM vip_irules WHERE vip_name = ? ORDER BY ordinal", (name,)
    ).fetchall()
    monitor_rows = conn.execute(
        "SELECT monitor_name FROM vip_monitors WHERE vip_name = ?", (name,)
    ).fetchall()
    return Vip(
        name=name,
        partition=row["partition_name"],
        destination_address=row["destination_address"],
        destination_port=row["destination_port"],
        address_family=AddressFamily(row["address_family"]),
        route_domain=row["route_domain"],
        ip_protocol=row["ip_protocol"],
        pool_name=row["pool_name"],
        vlans=[r["vlan_name"] for r in vlan_rows],
        vlans_enabled=bool(row["vlans_enabled"]),
        profiles=[Profile(name=r["profile_name"], context=r["context"]) for r in profile_rows],
        persistence=row["persistence"],
        snat_type=row["snat_type"],
        irules=[r["irule_name"] for r in irule_rows],
        mask=row["mask"],
        monitor_names=[r["monitor_name"] for r in monitor_rows],
        source_stanza_json=row["source_stanza_json"],
    )


class VipRepository:
    @staticmethod
    def list(
        conn: sqlite3.Connection,
        search: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Vip]:
        query = "SELECT * FROM vips"
        params: List[object] = []
        if search:
            query += " WHERE name LIKE ? OR destination_address LIKE ?"
            like = "%%%s%%" % search
            params.extend([like, like])
        query += " ORDER BY name"
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        rows = conn.execute(query, params).fetchall()
        return [_hydrate_vip(conn, r) for r in rows]

    @staticmethod
    def count(conn: sqlite3.Connection, search: Optional[str] = None) -> int:
        query = "SELECT COUNT(*) AS c FROM vips"
        params: List[object] = []
        if search:
            query += " WHERE name LIKE ? OR destination_address LIKE ?"
            like = "%%%s%%" % search
            params.extend([like, like])
        row = conn.execute(query, params).fetchone()
        return row["c"]

    @staticmethod
    def get(conn: sqlite3.Connection, name: str) -> Optional[Vip]:
        row = conn.execute("SELECT * FROM vips WHERE name = ?", (name,)).fetchone()
        return _hydrate_vip(conn, row) if row else None

    @staticmethod
    def get_many(conn: sqlite3.Connection, names: List[str]) -> List[Vip]:
        if not names:
            return []
        placeholders = ",".join("?" for _ in names)
        rows = conn.execute(
            "SELECT * FROM vips WHERE name IN (%s) ORDER BY name" % placeholders, names
        ).fetchall()
        return [_hydrate_vip(conn, r) for r in rows]
