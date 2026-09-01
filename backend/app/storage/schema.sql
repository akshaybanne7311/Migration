-- Schema applied fresh to each new per-session SQLite database file.

CREATE TABLE nodes (
    name TEXT PRIMARY KEY,
    address TEXT NOT NULL,
    address_family TEXT NOT NULL CHECK(address_family IN ('ipv4', 'ipv6')),
    partition_name TEXT NOT NULL DEFAULT 'Common',
    state TEXT,
    source_stanza_json TEXT NOT NULL
);
CREATE INDEX idx_nodes_address ON nodes(address);

CREATE TABLE monitors (
    name TEXT PRIMARY KEY,
    monitor_type TEXT,
    interval INTEGER,
    timeout INTEGER,
    source_stanza_json TEXT NOT NULL
);

CREATE TABLE pools (
    name TEXT PRIMARY KEY,
    partition_name TEXT NOT NULL DEFAULT 'Common',
    source_stanza_json TEXT NOT NULL
);

CREATE TABLE pool_monitors (
    pool_name TEXT NOT NULL REFERENCES pools(name),
    monitor_name TEXT NOT NULL,
    PRIMARY KEY (pool_name, monitor_name)
);

CREATE TABLE pool_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pool_name TEXT NOT NULL REFERENCES pools(name),
    node_name TEXT NOT NULL REFERENCES nodes(name),
    port INTEGER NOT NULL,
    session_state TEXT,
    connection_limit INTEGER,
    source_stanza_json TEXT NOT NULL,
    UNIQUE(pool_name, node_name, port)
);
CREATE INDEX idx_pool_members_pool ON pool_members(pool_name);
CREATE INDEX idx_pool_members_node ON pool_members(node_name);

CREATE TABLE vlans (
    name TEXT PRIMARY KEY,
    tag INTEGER,
    interfaces_json TEXT NOT NULL DEFAULT '[]',
    source_stanza_json TEXT NOT NULL
);

CREATE TABLE vips (
    name TEXT PRIMARY KEY,
    partition_name TEXT NOT NULL DEFAULT 'Common',
    destination_address TEXT NOT NULL,
    destination_port INTEGER NOT NULL,
    address_family TEXT NOT NULL CHECK(address_family IN ('ipv4', 'ipv6')),
    route_domain INTEGER,
    ip_protocol TEXT,
    pool_name TEXT REFERENCES pools(name),
    vlans_enabled INTEGER NOT NULL DEFAULT 1,
    persistence TEXT,
    snat_type TEXT,
    mask TEXT,
    source_stanza_json TEXT NOT NULL
);
CREATE INDEX idx_vips_dest ON vips(destination_address);
CREATE INDEX idx_vips_name ON vips(name);

CREATE TABLE vip_vlans (
    vip_name TEXT NOT NULL REFERENCES vips(name),
    vlan_name TEXT NOT NULL,
    PRIMARY KEY (vip_name, vlan_name)
);

CREATE TABLE vip_profiles (
    vip_name TEXT NOT NULL REFERENCES vips(name),
    profile_name TEXT NOT NULL,
    context TEXT,
    PRIMARY KEY (vip_name, profile_name)
);

CREATE TABLE vip_irules (
    vip_name TEXT NOT NULL REFERENCES vips(name),
    irule_name TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    PRIMARY KEY (vip_name, irule_name)
);

CREATE TABLE vip_monitors (
    vip_name TEXT NOT NULL REFERENCES vips(name),
    monitor_name TEXT NOT NULL,
    PRIMARY KEY (vip_name, monitor_name)
);

CREATE TABLE migration_plans (
    id TEXT PRIMARY KEY,
    step INTEGER NOT NULL DEFAULT 1,
    plan_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE ingest_warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT NOT NULL
);
