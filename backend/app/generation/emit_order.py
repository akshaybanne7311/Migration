"""Builds the single resolved-object context that every generator
(tmsh/rest/as3) reads from, so they cannot drift from each other.

Fixed emission order: Node -> Pool (with members) -> Vip. Node changes
are deduped by construction (node_cascade.resolve_node_changes already
returns at most one ResolvedNodeChange per physical node); the pool
member-list rewrite below applies the node rename cascade uniformly, so a
pool nobody explicitly edited but whose member's node got renamed still
comes out correct.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List

from app.models.change_set import ChangeType, ResolvedMember, ResolvedMigrationPlan
from app.models.domain import Node, Pool, Vip


@dataclass
class MigrationContext:
    new_nodes: Dict[str, Any] = field(default_factory=dict)  # new_node_name -> ResolvedNodeChange
    old_to_new_node_name: Dict[str, str] = field(default_factory=dict)
    pool_effective_members: Dict[str, List[ResolvedMember]] = field(default_factory=dict)
    vip_effective: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    create_network_objects: bool = False


def _apply_string_pattern(original: str, payload: Dict[str, Any]) -> str:
    find = payload.get("find")
    replace = payload.get("replace")
    if find is not None and replace is not None:
        return original.replace(find, replace)
    return original


def build_migration_context(
    resolved: ResolvedMigrationPlan,
    nodes_by_name: Dict[str, Node],
    pools_by_name: Dict[str, Pool],
    vips_by_name: Dict[str, Vip],
) -> MigrationContext:
    new_nodes: Dict[str, Any] = {}
    old_to_new: Dict[str, str] = {}
    for rnc in resolved.resolved_node_changes:
        new_nodes[rnc.new_node_name] = rnc
        old_to_new[rnc.old_node_name] = rnc.new_node_name

    pool_effective_members: Dict[str, List[ResolvedMember]] = {}
    touched_pools = set()
    for rpmc in resolved.resolved_pool_member_changes:
        pool_effective_members[rpmc.pool_name] = list(rpmc.new_members)
        touched_pools.add(rpmc.pool_name)

    for pool_name, pool in pools_by_name.items():
        if pool_name in touched_pools:
            continue
        if any(m.node_name in old_to_new for m in pool.members):
            pool_effective_members[pool_name] = [
                ResolvedMember(
                    node_name=m.node_name,
                    port=m.port,
                    address=nodes_by_name[m.node_name].address if m.node_name in nodes_by_name else None,
                )
                for m in pool.members
            ]

    for pool_name in list(pool_effective_members.keys()):
        rewritten: List[ResolvedMember] = []
        for m in pool_effective_members[pool_name]:
            if m.node_name in old_to_new:
                new_name = old_to_new[m.node_name]
                rnc = new_nodes[new_name]
                rewritten.append(ResolvedMember(node_name=new_name, port=m.port, address=rnc.new_address))
            else:
                rewritten.append(m)
        pool_effective_members[pool_name] = rewritten

    vlan_by_vip = {rvc.vip_name: rvc for rvc in resolved.resolved_vlan_changes}
    vip_effective: Dict[str, Dict[str, Any]] = {}
    for vc in resolved.vip_changes:
        vip = vips_by_name[vc.vip_name]
        fields: Dict[str, Any] = {}

        if vc.vip_name in vlan_by_vip:
            rv = vlan_by_vip[vc.vip_name]
            fields["vlans"] = rv.new_vlans
            fields["vlans_enabled"] = rv.vlans_enabled

        name_payload = vc.effective.get(ChangeType.VIP_NAME)
        if name_payload:
            fields["name"] = _apply_string_pattern(vip.name, name_payload)

        ip_port_payload = vc.effective.get(ChangeType.VIP_IP_PORT)
        if ip_port_payload:
            if ip_port_payload.get("new_port") is not None:
                fields["destination_port"] = ip_port_payload["new_port"]
            if ip_port_payload.get("new_address"):
                fields["destination_address"] = ip_port_payload["new_address"]

        pool_name_payload = vc.effective.get(ChangeType.POOL_NAME)
        if pool_name_payload and vip.pool_name:
            fields["pool_name"] = _apply_string_pattern(vip.pool_name, pool_name_payload)

        persistence_payload = vc.effective.get(ChangeType.PERSISTENCE)
        if persistence_payload and persistence_payload.get("new_persistence") is not None:
            fields["persistence"] = persistence_payload["new_persistence"]

        monitor_payload = vc.effective.get(ChangeType.MONITOR)
        if monitor_payload and monitor_payload.get("new_monitor"):
            fields["monitor_names"] = [monitor_payload["new_monitor"]]

        profiles_payload = vc.effective.get(ChangeType.PROFILES)
        if profiles_payload:
            current = [p.name for p in vip.profiles]
            to_add = profiles_payload.get("add") or []
            to_remove = set(profiles_payload.get("remove") or [])
            merged = [p for p in current if p not in to_remove]
            for name in to_add:
                if name not in merged:
                    merged.append(name)
            fields["profile_names"] = merged

        vip_effective[vc.vip_name] = fields

    return MigrationContext(
        new_nodes=new_nodes,
        old_to_new_node_name=old_to_new,
        pool_effective_members=pool_effective_members,
        vip_effective=vip_effective,
        create_network_objects=resolved.create_network_objects,
    )
