"""Per-session SQLite database: connection lifecycle + writing a
ParsedConfig into the normalized schema.

No connection is ever cached or shared across requests: each request opens
its own connection (see deps.get_session_db) and closes it when the
request finishes. This is deliberate -- FastAPI dispatches sync routes to
a worker threadpool, and a cached sqlite3 connection reused concurrently
by two requests on different threads is not safe (it previously segfaulted
the process under real concurrent browser traffic). A per-request
connection sidesteps that entirely, and also means "does this session
exist" is answered fresh from disk every time, which is what prevents
stale/auto-reopened sessions after delete (see storage/registry_db.py for
the registry row that is the actual source of truth).
"""
import json
import sqlite3
from pathlib import Path

from app.config import settings
from app.models.domain import ParsedConfig

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class SessionNotFoundError(Exception):
    pass


def session_db_path(session_id: str) -> Path:
    return settings.sessions_dir / session_id / "session.db"


def create_session_db(session_id: str) -> sqlite3.Connection:
    db_path = session_db_path(session_id)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA_PATH.read_text())
    return conn


def open_session_conn(session_id: str) -> sqlite3.Connection:
    db_path = session_db_path(session_id)
    if not db_path.exists():
        raise SessionNotFoundError(session_id)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def delete_session_files(session_id: str) -> None:
    db_path = session_db_path(session_id)
    if db_path.exists():
        db_path.unlink()
    session_dir = db_path.parent
    if session_dir.exists() and not any(session_dir.iterdir()):
        session_dir.rmdir()


def write_parsed_config(conn: sqlite3.Connection, config: ParsedConfig) -> None:
    with conn:
        for node in config.nodes.values():
            conn.execute(
                "INSERT INTO nodes (name, address, address_family, partition_name, "
                "state, source_stanza_json) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    node.name,
                    node.address,
                    node.address_family.value,
                    node.partition,
                    node.state,
                    node.source_stanza_json,
                ),
            )

        for monitor in config.monitors.values():
            conn.execute(
                "INSERT INTO monitors (name, monitor_type, interval, timeout, "
                "source_stanza_json) VALUES (?, ?, ?, ?, ?)",
                (
                    monitor.name,
                    monitor.monitor_type,
                    monitor.interval,
                    monitor.timeout,
                    monitor.source_stanza_json,
                ),
            )

        for vlan in config.vlans.values():
            conn.execute(
                "INSERT INTO vlans (name, tag, interfaces_json, source_stanza_json) "
                "VALUES (?, ?, ?, ?)",
                (
                    vlan.name,
                    vlan.tag,
                    json.dumps(vlan.interfaces),
                    vlan.source_stanza_json,
                ),
            )

        for pool in config.pools.values():
            conn.execute(
                "INSERT INTO pools (name, partition_name, source_stanza_json) "
                "VALUES (?, ?, ?)",
                (pool.name, pool.partition, pool.source_stanza_json),
            )
            for monitor_name in pool.monitor_names:
                conn.execute(
                    "INSERT OR IGNORE INTO pool_monitors (pool_name, monitor_name) "
                    "VALUES (?, ?)",
                    (pool.name, monitor_name),
                )
            for member in pool.members:
                conn.execute(
                    "INSERT OR IGNORE INTO pool_members "
                    "(pool_name, node_name, port, session_state, connection_limit, "
                    " source_stanza_json) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        member.pool_name,
                        member.node_name,
                        member.port,
                        member.session_state,
                        member.connection_limit,
                        member.source_stanza_json,
                    ),
                )

        for vip in config.vips.values():
            conn.execute(
                "INSERT INTO vips (name, partition_name, destination_address, "
                "destination_port, address_family, route_domain, ip_protocol, "
                "pool_name, vlans_enabled, persistence, snat_type, mask, "
                "source_stanza_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    vip.name,
                    vip.partition,
                    vip.destination_address,
                    vip.destination_port,
                    vip.address_family.value,
                    vip.route_domain,
                    vip.ip_protocol,
                    vip.pool_name,
                    1 if vip.vlans_enabled else 0,
                    vip.persistence,
                    vip.snat_type,
                    vip.mask,
                    vip.source_stanza_json,
                ),
            )
            for vlan_name in vip.vlans:
                conn.execute(
                    "INSERT OR IGNORE INTO vip_vlans (vip_name, vlan_name) VALUES (?, ?)",
                    (vip.name, vlan_name),
                )
            for profile in vip.profiles:
                conn.execute(
                    "INSERT OR IGNORE INTO vip_profiles (vip_name, profile_name, context) "
                    "VALUES (?, ?, ?)",
                    (vip.name, profile.name, profile.context),
                )
            for ordinal, irule_name in enumerate(vip.irules):
                conn.execute(
                    "INSERT OR IGNORE INTO vip_irules (vip_name, irule_name, ordinal) "
                    "VALUES (?, ?, ?)",
                    (vip.name, irule_name, ordinal),
                )
            for monitor_name in vip.monitor_names:
                conn.execute(
                    "INSERT OR IGNORE INTO vip_monitors (vip_name, monitor_name) "
                    "VALUES (?, ?)",
                    (vip.name, monitor_name),
                )

        for warning in config.warnings:
            conn.execute("INSERT INTO ingest_warnings (message) VALUES (?)", (warning,))
