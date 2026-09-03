"""Renders a ResolvedMigrationPlan (via its MigrationContext) as real TMSH
commands, in Node -> Pool -> Vip order, from typed payloads rather than
raw stanza text -- output is always structurally valid.

Pool member membership is always emitted via `replace-all-with` with the
full final member list, regardless of whether the underlying edit was an
add/remove/replace_selected/replace_all/node-rename cascade -- since the
context already computed the final desired state, this is always correct
and keeps the generator simple.
"""
from typing import Dict, List

from app.generation.emit_order import MigrationContext
from app.models.domain import Vip


def _render_node_create(rnc) -> str:
    return "tmsh create ltm node %s address %s" % (rnc.new_node_name, rnc.new_address)


def _render_pool_members_modify(pool_name: str, members) -> str:
    member_lines = " ".join("%s:%d { }" % (m.node_name, m.port) for m in members)
    return "tmsh modify ltm pool %s members replace-all-with { %s }" % (pool_name, member_lines)


def _render_vip_commands(vip: Vip, effective: Dict) -> List[str]:
    lines: List[str] = []
    current_name = vip.name

    if "name" in effective and effective["name"] != vip.name:
        lines.append("tmsh mv ltm virtual %s %s" % (vip.name, effective["name"]))
        current_name = effective["name"]

    if "destination_address" in effective or "destination_port" in effective:
        from app.ingest.net_address import format_destination

        address = effective.get("destination_address", vip.destination_address)
        port = effective.get("destination_port", vip.destination_port)
        dest = format_destination(address, port, vip.address_family, vip.route_domain)
        lines.append(
            "tmsh modify ltm virtual %s destination /%s/%s" % (current_name, vip.partition, dest)
        )

    if "pool_name" in effective:
        lines.append("tmsh modify ltm virtual %s pool %s" % (current_name, effective["pool_name"]))

    if "vlans" in effective:
        vlan_list = " ".join(effective["vlans"])
        flag = "vlans-enabled" if effective.get("vlans_enabled", True) else "vlans-disabled"
        lines.append(
            "tmsh modify ltm virtual %s vlans replace-all-with { %s } %s"
            % (current_name, vlan_list, flag)
        )

    if "persistence" in effective:
        lines.append(
            "tmsh modify ltm virtual %s persist replace-all-with { %s { } }"
            % (current_name, effective["persistence"])
        )

    if "monitor_names" in effective:
        monitor_list = " ".join(effective["monitor_names"])
        lines.append("tmsh modify ltm virtual %s monitor %s" % (current_name, monitor_list))

    if "profile_names" in effective:
        profile_list = " ".join("%s { }" % p for p in effective["profile_names"])
        lines.append(
            "tmsh modify ltm virtual %s profiles replace-all-with { %s }"
            % (current_name, profile_list)
        )

    return lines


def generate_tmsh(context: MigrationContext, vips_by_name: Dict[str, Vip]) -> str:
    lines: List[str] = []

    for rnc in context.new_nodes.values():
        lines.append(_render_node_create(rnc))

    for pool_name, members in context.pool_effective_members.items():
        lines.append(_render_pool_members_modify(pool_name, members))

    for old_name, new_name in context.pool_renames.items():
        lines.append("tmsh mv ltm pool %s %s" % (old_name, new_name))

    for vip_name, effective in context.vip_effective.items():
        if not effective:
            continue
        vip = vips_by_name[vip_name]
        lines.extend(_render_vip_commands(vip, effective))

    # deletes go last -- by construction (node_refs validator) a node here
    # is no longer referenced by any pool once the edits above have run
    for node_name in context.node_deletions:
        lines.append("tmsh delete ltm node %s" % node_name)

    return "\n".join(lines) + ("\n" if lines else "")
