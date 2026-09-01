"""Full-recreate generation.

The three generators in tmsh_generator.py / rest_generator.py /
as3_generator.py are all "modify existing objects" generators: they only
emit output for fields the plan actually changes (`if not effective:
continue`), on the assumption that every node/monitor/pool/virtual
referenced by a selected VIP already exists on the target and just needs
a field patched (e.g. renumbering nodes on the same device).

That assumption is wrong for the other real migration scenario: standing
the selected VIPs up on a *new* device that doesn't have any of these
objects yet. Selecting VIPs there with zero field-level changes chosen is
completely valid ("just move these VIPs as-is") but the modify-only
generators silently produce nothing, because there is nothing to patch.

This module produces a complete, self-contained script instead: monitors,
nodes, pools (with members), and virtuals for the full dependency closure
of the selected VIPs, in that creation order, deduplicated the same way
emit_order.MigrationContext dedupes shared objects. Any changes chosen in
the plan are still applied to the recreated objects' values -- this is
"recreate everything, changed or not," not a second, competing change
engine.

FullRecreateUnits is built once and handed to all three renderers so
TMSH/REST/AS3 can't drift from each other, the same guarantee
MigrationContext gives the modify-only generators.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from pydantic import BaseModel

from app.generation.emit_order import MigrationContext
from app.ingest.net_address import format_destination
from app.models.domain import Monitor, Pool, Vip


@dataclass
class PoolUnit:
    name: str
    pool: Pool
    members: List[Any]


@dataclass
class VipUnit:
    vip: Vip
    effective: Dict[str, Any]


@dataclass
class FullRecreateUnits:
    monitors: List[Monitor] = field(default_factory=list)
    nodes: List[Tuple[str, str]] = field(default_factory=list)
    pools: List[PoolUnit] = field(default_factory=list)
    vips: List[VipUnit] = field(default_factory=list)


def build_full_recreate_units(
    selected_vip_names: List[str],
    context: MigrationContext,
    nodes_by_name: Dict[str, Any],
    pools_by_name: Dict[str, Pool],
    vips_by_name: Dict[str, Vip],
    monitors_by_name: Dict[str, Monitor],
) -> FullRecreateUnits:
    selected_vips = [vips_by_name[n] for n in selected_vip_names if n in vips_by_name]
    selected_pool_names = sorted({v.pool_name for v in selected_vips if v.pool_name})

    pool_units: List[PoolUnit] = []
    monitor_names_needed = set()
    node_entries: Dict[str, str] = {}

    for pn in selected_pool_names:
        pool = pools_by_name.get(pn)
        if pool is None:
            continue
        members = context.pool_effective_members.get(pn) or pool.members
        pool_units.append(PoolUnit(name=pn, pool=pool, members=members))
        monitor_names_needed.update(pool.monitor_names)
        for m in members:
            # context.new_nodes is keyed by *new* node name and is the
            # source of truth for any node touched by a NodeChange -- check
            # it first, since an address-only change (new_node_name ==
            # old_node_name) would otherwise still be found in
            # nodes_by_name under the same name and shadow the new address.
            if m.node_name in context.new_nodes:
                node_entries[m.node_name] = context.new_nodes[m.node_name].new_address
            elif m.node_name in nodes_by_name:
                node_entries[m.node_name] = nodes_by_name[m.node_name].address
            elif getattr(m, "address", None):
                node_entries[m.node_name] = m.address

    vip_units: List[VipUnit] = []
    for v in selected_vips:
        monitor_names_needed.update(v.monitor_names)
        vip_units.append(VipUnit(vip=v, effective=context.vip_effective.get(v.name, {})))

    monitors = [monitors_by_name[mn] for mn in sorted(monitor_names_needed) if mn in monitors_by_name]

    return FullRecreateUnits(
        monitors=monitors,
        nodes=sorted(node_entries.items()),
        pools=pool_units,
        vips=vip_units,
    )


def _vip_field_bag(vip: Vip, effective: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": effective.get("name", vip.name),
        "destination_address": effective.get("destination_address", vip.destination_address),
        "destination_port": effective.get("destination_port", vip.destination_port),
        "pool_name": effective.get("pool_name", vip.pool_name),
        "vlans": effective.get("vlans", vip.vlans),
        "vlans_enabled": effective.get("vlans_enabled", vip.vlans_enabled),
        "persistence": effective.get("persistence", vip.persistence),
        "monitor_names": effective.get("monitor_names", vip.monitor_names),
        "profile_names": effective.get("profile_names", [p.name for p in vip.profiles]),
    }


def _render_monitor_create(m: Monitor) -> str:
    mtype = m.monitor_type or "http"
    fields = []
    if m.interval is not None:
        fields.append("interval %d" % m.interval)
    if m.timeout is not None:
        fields.append("timeout %d" % m.timeout)
    if fields:
        return "tmsh create ltm monitor %s %s { %s }" % (mtype, m.name, " ".join(fields))
    return "tmsh create ltm monitor %s %s" % (mtype, m.name)


def _render_pool_create(pu: PoolUnit) -> str:
    member_lines = " ".join("%s:%d { }" % (m.node_name, m.port) for m in pu.members)
    body = []
    if pu.pool.monitor_names:
        body.append("monitor %s" % " and ".join(pu.pool.monitor_names))
    if member_lines:
        body.append("members replace-all-with { %s }" % member_lines)
    if body:
        return "tmsh create ltm pool %s { %s }" % (pu.name, " ".join(body))
    return "tmsh create ltm pool %s" % pu.name


def _render_vip_create(vip: Vip, effective: Dict[str, Any]) -> str:
    f = _vip_field_bag(vip, effective)
    dest = format_destination(f["destination_address"], f["destination_port"], vip.address_family, vip.route_domain)
    body = ["destination /%s/%s" % (vip.partition, dest)]
    if vip.ip_protocol:
        body.append("ip-protocol %s" % vip.ip_protocol)
    if f["pool_name"]:
        body.append("pool %s" % f["pool_name"])
    if f["vlans"]:
        flag = "vlans-enabled" if f["vlans_enabled"] else "vlans-disabled"
        body.append("vlans replace-all-with { %s } %s" % (" ".join(f["vlans"]), flag))
    if f["persistence"]:
        body.append("persist replace-all-with { %s { } }" % f["persistence"])
    if f["monitor_names"]:
        body.append("monitor %s" % " ".join(f["monitor_names"]))
    if f["profile_names"]:
        body.append("profiles replace-all-with { %s }" % " ".join("%s { }" % p for p in f["profile_names"]))
    if vip.irules:
        body.append("rules replace-all-with { %s }" % " ".join(vip.irules))
    return "tmsh create ltm virtual %s { %s }" % (f["name"], " ".join(body))


def generate_full_recreate_tmsh(units: FullRecreateUnits) -> str:
    lines: List[str] = []
    for m in units.monitors:
        lines.append(_render_monitor_create(m))
    for name, address in units.nodes:
        lines.append("tmsh create ltm node %s address %s" % (name, address))
    for pu in units.pools:
        lines.append(_render_pool_create(pu))
    for vu in units.vips:
        lines.append(_render_vip_create(vu.vip, vu.effective))
    return "\n".join(lines) + ("\n" if lines else "")


class RestCallLike(BaseModel):
    method: str
    path: str
    body: Dict[str, Any]


def generate_full_recreate_rest(units: FullRecreateUnits) -> List[RestCallLike]:
    calls: List[RestCallLike] = []

    for m in units.monitors:
        body: Dict[str, Any] = {"name": m.name}
        if m.interval is not None:
            body["interval"] = m.interval
        if m.timeout is not None:
            body["timeout"] = m.timeout
        calls.append(RestCallLike(method="POST", path="/mgmt/tm/ltm/monitor/%s" % (m.monitor_type or "http"), body=body))

    for name, address in units.nodes:
        calls.append(RestCallLike(method="POST", path="/mgmt/tm/ltm/node", body={"name": name, "address": address}))

    for pu in units.pools:
        body = {"name": pu.name, "members": [{"name": "%s:%d" % (m.node_name, m.port)} for m in pu.members]}
        if pu.pool.monitor_names:
            body["monitor"] = " and ".join(pu.pool.monitor_names)
        calls.append(RestCallLike(method="POST", path="/mgmt/tm/ltm/pool", body=body))

    for vu in units.vips:
        f = _vip_field_bag(vu.vip, vu.effective)
        dest = format_destination(
            f["destination_address"], f["destination_port"], vu.vip.address_family, vu.vip.route_domain
        )
        body = {
            "name": f["name"],
            "destination": "/%s/%s" % (vu.vip.partition, dest),
        }
        if vu.vip.ip_protocol:
            body["ipProtocol"] = vu.vip.ip_protocol
        if f["pool_name"]:
            body["pool"] = f["pool_name"]
        if f["vlans"]:
            body["vlans"] = f["vlans"]
            body["vlansEnabled"] = f["vlans_enabled"]
        if f["persistence"]:
            body["persist"] = [{"name": f["persistence"]}]
        if f["monitor_names"]:
            body["monitor"] = " and ".join(f["monitor_names"])
        if f["profile_names"]:
            body["profiles"] = [{"name": p} for p in f["profile_names"]]
        calls.append(RestCallLike(method="POST", path="/mgmt/tm/ltm/virtual", body=body))

    return calls


def generate_full_recreate_as3(units: FullRecreateUnits) -> Dict[str, Any]:
    notes: List[Dict[str, str]] = []

    def app_name(name: str) -> str:
        parts = [p for p in name.split("/") if p]
        return parts[-1] if parts else name

    pools_service: Dict[str, Any] = {}
    for pu in units.pools:
        pools_service[app_name(pu.name) + "_pool"] = {
            "class": "Pool",
            "members": [
                {"servicePort": m.port, "serverAddresses": [getattr(m, "address", None)] if getattr(m, "address", None) else []}
                for m in pu.members
            ],
        }

    applications: Dict[str, Any] = {}
    for vu in units.vips:
        vip, f = vu.vip, _vip_field_bag(vu.vip, vu.effective)
        name = app_name(f["name"])
        service: Dict[str, Any] = {
            "class": "Service_Generic" if vip.ip_protocol != "udp" else "Service_UDP",
            "virtualAddresses": [f["destination_address"]],
            "virtualPort": f["destination_port"],
        }
        if vip.route_domain is not None:
            notes.append({"object": vip.name, "field": "route_domain", "note": "route domains are not modeled in AS3; handle via Tenant/RouteDomain"})
        if f["persistence"]:
            notes.append({"object": vip.name, "field": "persistence", "note": "persistence profile mapped by name only"})
        if vip.irules:
            notes.append({"object": vip.name, "field": "irules", "note": "iRules referenced by name only, logic not represented"})

        app = applications.setdefault(name, {"class": "Application"})
        if f["pool_name"] and (app_name(f["pool_name"]) + "_pool") in pools_service:
            pool_key = app_name(f["pool_name"]) + "_pool"
            service["pool"] = pool_key
            app[pool_key] = pools_service[pool_key]
        app[name] = service

    return {
        "declaration": {
            "class": "ADC",
            "schemaVersion": "3.0.0",
            "id": "f5-config-intelligence-full-recreate",
            "Tenant_Migration": {"class": "Tenant", **applications},
        },
        "x-tmos-notes": notes,
    }
