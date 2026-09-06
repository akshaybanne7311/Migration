"""Config health check -- the same spirit as F5 iHealth's role for TAC
(run a set of known-issue/best-practice heuristics over a device's
config and flag what needs attention), scoped to what this app actually
parses. This is deliberately NOT a claim to replicate iHealth's
proprietary knowledge base; every check here is a concrete, explainable
condition computed from the session's own parsed VIPs/pools/nodes/VLANs/
system objects -- nothing fabricated, nothing that requires F5's database
of known issues.
"""
import json
import sqlite3
from typing import Dict, List

from app.graph.builder import build_dependency_graph
from app.models.validation import Severity, ValidationCheck
from app.storage.repositories import NodeRepository, PoolRepository, SystemObjectRepository, VipRepository, VlanRepository


def _entries(json_str: str) -> Dict:
    try:
        parsed = json.loads(json_str)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def run_health_check(conn: sqlite3.Connection) -> List[ValidationCheck]:
    vips = VipRepository.list(conn)
    pools = PoolRepository.list(conn)
    nodes = NodeRepository.list(conn)
    vlans = VlanRepository.list(conn)
    system_objects = SystemObjectRepository.list(conn)
    vlan_names = {v.name for v in vlans}
    graph = build_dependency_graph(conn)

    checks: List[ValidationCheck] = []

    # -- pools without a health monitor
    no_monitor = [p.name for p in pools if not p.monitor_names]
    checks.append(
        ValidationCheck(
            id="pools_without_monitor",
            label="Pool health monitoring",
            severity=Severity.WARN if no_monitor else Severity.PASS,
            details=(
                "%d pool(s) have no health monitor -- a dead member won't be taken out of rotation"
                % len(no_monitor)
                if no_monitor
                else "every pool has at least one health monitor"
            ),
            affected=no_monitor,
        )
    )

    # -- pools where every member is administratively disabled
    all_disabled = [
        p.name for p in pools if p.members and all(m.session_state == "user-disabled" for m in p.members)
    ]
    checks.append(
        ValidationCheck(
            id="pools_all_members_disabled",
            label="Pool member availability",
            severity=Severity.WARN if all_disabled else Severity.PASS,
            details=(
                "%d pool(s) have every member administratively disabled -- traffic to that pool has nowhere to go"
                % len(all_disabled)
                if all_disabled
                else "no pool has all members disabled"
            ),
            affected=all_disabled,
        )
    )

    # -- VIPs with no pool assigned
    no_pool = [v.name for v in vips if not v.pool_name]
    checks.append(
        ValidationCheck(
            id="vips_without_pool",
            label="Virtual servers without a pool",
            severity=Severity.WARN if no_pool else Severity.PASS,
            details=(
                "%d virtual server(s) have no default pool assigned" % len(no_pool)
                if no_pool
                else "every virtual server has a default pool"
            ),
            affected=no_pool,
        )
    )

    # -- nodes not referenced by any pool or virtual-address
    orphaned_nodes = [n.name for n in nodes if not graph.pools_using_node(n.name) and not graph.vips_using_node(n.name)]
    checks.append(
        ValidationCheck(
            id="orphaned_nodes",
            label="Unreferenced nodes",
            severity=Severity.WARN if orphaned_nodes else Severity.PASS,
            details=(
                "%d node(s) aren't used by any pool -- safe to review for cleanup" % len(orphaned_nodes)
                if orphaned_nodes
                else "every node is referenced by at least one pool"
            ),
            affected=orphaned_nodes,
        )
    )

    # -- VIP VLAN references that don't resolve to a parsed net vlan object
    dangling_vip_vlans = []
    for v in vips:
        for vlan_name in v.vlans:
            if vlan_name not in vlan_names:
                dangling_vip_vlans.append("%s -> %s" % (v.name, vlan_name))
    checks.append(
        ValidationCheck(
            id="vip_vlan_refs",
            label="Virtual server VLAN references",
            severity=Severity.BLOCKED if dangling_vip_vlans else Severity.PASS,
            details=(
                "%d virtual server VLAN reference(s) don't match any parsed VLAN object" % len(dangling_vip_vlans)
                if dangling_vip_vlans
                else "every virtual server VLAN reference resolves"
            ),
            affected=dangling_vip_vlans,
        )
    )

    # -- self IP VLAN references
    self_ips = [o for o in system_objects if o.object_type == "net self"]
    dangling_self_ip_vlans = []
    for o in self_ips:
        vlan_ref = _entries(o.entries_json).get("vlan")
        if isinstance(vlan_ref, str) and vlan_ref and vlan_ref not in vlan_names:
            dangling_self_ip_vlans.append("%s -> %s" % (o.name, vlan_ref))
    checks.append(
        ValidationCheck(
            id="self_ip_vlan_refs",
            label="Self IP VLAN references",
            severity=Severity.BLOCKED if dangling_self_ip_vlans else Severity.PASS,
            details=(
                "%d self IP(s) reference a VLAN that wasn't parsed" % len(dangling_self_ip_vlans)
                if dangling_self_ip_vlans
                else "every self IP's VLAN reference resolves"
            ),
            affected=dangling_self_ip_vlans,
        )
    )

    # -- duplicate virtual server destinations (address + port + route domain)
    seen: Dict[tuple, List[str]] = {}
    for v in vips:
        key = (v.destination_address, v.destination_port, v.route_domain)
        seen.setdefault(key, []).append(v.name)
    duplicate_destinations = []
    for (addr, port, rd), names in seen.items():
        if len(names) > 1:
            duplicate_destinations.append("%s:%s%s -> %s" % (addr, port, (" %%%d" % rd) if rd else "", ", ".join(names)))
    checks.append(
        ValidationCheck(
            id="duplicate_vip_destinations",
            label="Duplicate virtual server destinations",
            severity=Severity.BLOCKED if duplicate_destinations else Severity.PASS,
            details=(
                "%d destination(s) are claimed by more than one virtual server" % len(duplicate_destinations)
                if duplicate_destinations
                else "no two virtual servers share a destination"
            ),
            affected=duplicate_destinations,
        )
    )

    # -- NTP configured (best practice: cert validation, HA, and log timestamps all depend on it)
    has_ntp = any(o.object_type == "sys ntp" for o in system_objects)
    checks.append(
        ValidationCheck(
            id="ntp_configured",
            label="NTP configuration",
            severity=Severity.PASS if has_ntp else Severity.WARN,
            details="NTP is configured" if has_ntp else "no sys ntp object was parsed -- clock drift affects cert validation, HA, and log correlation",
            affected=[],
        )
    )

    # -- DNS resolver configured
    has_dns = any(o.object_type == "net dns-resolver" for o in system_objects)
    checks.append(
        ValidationCheck(
            id="dns_configured",
            label="DNS resolver configuration",
            severity=Severity.PASS if has_dns else Severity.WARN,
            details="a DNS resolver is configured" if has_dns else "no net dns-resolver object was parsed -- iRules or monitors doing name lookups would fail",
            affected=[],
        )
    )

    # -- SNMP access not wide open
    snmp_objects = [o for o in system_objects if o.object_type == "sys snmp"]
    broad_snmp: List[str] = []
    for o in snmp_objects:
        allowed = _entries(o.entries_json).get("allowed-addresses")
        allowed_list = allowed if isinstance(allowed, list) else [allowed] if allowed else []
        if any(a in ("0.0.0.0/0", "::/0", "all", "0.0.0.0") for a in allowed_list) or not allowed_list:
            broad_snmp.append("sys snmp allowed-addresses: %s" % (", ".join(str(a) for a in allowed_list) or "(none set -- check default)"))
    checks.append(
        ValidationCheck(
            id="snmp_access_scope",
            label="SNMP access scope",
            severity=Severity.WARN if broad_snmp else Severity.PASS,
            details=(
                "SNMP allowed-addresses looks unrestricted -- confirm that's intentional" if broad_snmp else "SNMP access is scoped to specific addresses (or SNMP isn't configured)"
            ),
            affected=broad_snmp,
        )
    )

    # -- HA device-group with fewer than 2 members
    thin_ha_groups = []
    for o in system_objects:
        if o.object_type != "cm device-group":
            continue
        entries = _entries(o.entries_json)
        if entries.get("type") != "sync-failover":
            continue
        devices = entries.get("devices")
        device_count = len(devices) if isinstance(devices, dict) else (len(devices) if isinstance(devices, list) else 0)
        if device_count < 2:
            thin_ha_groups.append("%s (%d device%s)" % (o.name, device_count, "" if device_count == 1 else "s"))
    checks.append(
        ValidationCheck(
            id="ha_group_membership",
            label="HA device-group membership",
            severity=Severity.WARN if thin_ha_groups else Severity.PASS,
            details=(
                "%d sync-failover device-group(s) have fewer than 2 devices -- no real failover peer" % len(thin_ha_groups)
                if thin_ha_groups
                else "every sync-failover device-group has at least 2 devices"
            ),
            affected=thin_ha_groups,
        )
    )

    # -- certificate expiry (real X.509 files pulled from the archive, not
    # bigip.conf's cm cert stanza -- that only has cache-path/checksum, no
    # expiry date; see app/ingest/certificates.py)
    CERT_WARN_WINDOW_DAYS = 60
    certs = [o for o in system_objects if o.object_type == "x509 certificate"]
    expired_certs = []
    expiring_certs = []
    for o in certs:
        e = _entries(o.entries_json)
        days = e.get("days_until_expiry")
        if not isinstance(days, int):
            continue
        label = "%s (%s)" % (o.name, e.get("not_after", "")[:10])
        if e.get("is_expired"):
            expired_certs.append("%s -- expired %d day(s) ago" % (label, -days))
        elif days <= CERT_WARN_WINDOW_DAYS:
            expiring_certs.append("%s -- expires in %d day(s)" % (label, days))
    checks.append(
        ValidationCheck(
            id="certificates_expired",
            label="Expired certificates",
            severity=Severity.BLOCKED if expired_certs else Severity.PASS,
            details=(
                "%d certificate(s) are already expired" % len(expired_certs)
                if expired_certs
                else ("no certificates parsed from this session" if not certs else "no parsed certificate is expired")
            ),
            affected=expired_certs,
        )
    )
    checks.append(
        ValidationCheck(
            id="certificates_expiring_soon",
            label="Certificates expiring soon (%d days)" % CERT_WARN_WINDOW_DAYS,
            severity=Severity.WARN if expiring_certs else Severity.PASS,
            details=(
                "%d certificate(s) expire within %d days" % (len(expiring_certs), CERT_WARN_WINDOW_DAYS)
                if expiring_certs
                else ("no certificates parsed from this session" if not certs else "no parsed certificate expires soon")
            ),
            affected=expiring_certs,
        )
    )

    # -- license usage type (real config/bigip.license, not sys provision --
    # provision says what's turned on, only the license says what's actually
    # entitled and whether it's time-limited)
    license_obj = next((o for o in system_objects if o.object_type == "sys license" and o.name == "current"), None)
    usage = _entries(license_obj.entries_json).get("usage") if license_obj else None
    is_eval = isinstance(usage, str) and usage.strip().lower() == "evaluation"
    checks.append(
        ValidationCheck(
            id="license_evaluation",
            label="License type",
            severity=Severity.BLOCKED if is_eval else Severity.PASS,
            details=(
                "this device is running on an Evaluation license -- it will expire and stop passing traffic; "
                "not suitable as a permanent migration target without a Production license"
                if is_eval
                else (
                    "licensed for Production use" if usage else "no license file was parsed from this session"
                )
            ),
            affected=[],
        )
    )

    # -- duplicate node IP addresses (two logical node names pointing at
    # the same real address) -- a real migration risk: creating both on a
    # target device either conflicts or silently makes one redundant.
    addr_to_nodes: Dict[str, List[str]] = {}
    for n in nodes:
        addr_to_nodes.setdefault(n.address, []).append(n.name)
    duplicate_addresses = ["%s -> %s" % (addr, ", ".join(names)) for addr, names in addr_to_nodes.items() if len(names) > 1]
    checks.append(
        ValidationCheck(
            id="duplicate_node_addresses",
            label="Duplicate node addresses",
            severity=Severity.WARN if duplicate_addresses else Severity.PASS,
            details=(
                "%d address(es) are claimed by more than one node object" % len(duplicate_addresses)
                if duplicate_addresses
                else "every node has a unique address"
            ),
            affected=duplicate_addresses,
        )
    )

    # -- VIP persistence profile references that don't resolve to a real
    # parsed persistence object (same pattern as vip_vlan_refs/
    # self_ip_vlan_refs above, for a different reference type)
    persistence_names = {o.name for o in system_objects if o.object_type.startswith("ltm persistence ")}
    dangling_persistence = [
        "%s -> %s" % (v.name, v.persistence) for v in vips if v.persistence and v.persistence not in persistence_names
    ]
    checks.append(
        ValidationCheck(
            id="vip_persistence_refs",
            label="Virtual server persistence profile references",
            severity=Severity.BLOCKED if dangling_persistence else Severity.PASS,
            details=(
                "%d virtual server persistence reference(s) don't match any parsed persistence object" % len(dangling_persistence)
                if dangling_persistence
                else "every virtual server persistence reference resolves"
            ),
            affected=dangling_persistence,
        )
    )

    # -- VIP iRule references that don't resolve to a real parsed iRule
    irule_names = {o.name for o in system_objects if o.object_type == "ltm rule"}
    dangling_irules = []
    for v in vips:
        for irule_name in v.irules:
            if irule_name not in irule_names:
                dangling_irules.append("%s -> %s" % (v.name, irule_name))
    checks.append(
        ValidationCheck(
            id="vip_irule_refs",
            label="Virtual server iRule references",
            severity=Severity.BLOCKED if dangling_irules else Severity.PASS,
            details=(
                "%d virtual server iRule reference(s) don't match any parsed iRule" % len(dangling_irules)
                if dangling_irules
                else "every virtual server iRule reference resolves"
            ),
            affected=dangling_irules,
        )
    )

    return checks
