"""Merges common changes + per-VIP exceptions into a fully resolved plan.

Merge rule: common changes apply to every selected VIP first; each
VipException then overwrites only the change-type keys it specifies on
that one VIP (field-level override, not whole-record replacement) -- a
VIP with only a VLAN exception still inherits the common pool-members
change.
"""
from typing import Dict, List

from app.ingest.net_address import parse_node_address
from app.migration.node_cascade import resolve_node_changes
from app.models.change_set import (
    ChangeType,
    MemberRef,
    MigrationPlan,
    PoolMemberEdit,
    ResolvedMember,
    ResolvedMigrationPlan,
    ResolvedPoolMemberChange,
    ResolvedVipChange,
    ResolvedVlanChange,
)
from app.models.domain import Node, Pool, Vip
from app.models.graph import DependencyGraph


class ChangeEngineError(Exception):
    pass


def _resolve_member_ref(ref: MemberRef, nodes_by_name: Dict[str, Node]) -> ResolvedMember:
    if ref.node_name:
        known = ref.node_name in nodes_by_name
        return ResolvedMember(
            node_name=ref.node_name,
            address=nodes_by_name[ref.node_name].address if known else ref.address,
            is_new_node=not known,
            port=ref.port,
        )
    if ref.address:
        address, _family = parse_node_address(ref.address)
        name = ref.new_node_name or ("/Common/%s" % address)
        return ResolvedMember(node_name=name, address=address, is_new_node=True, port=ref.port)
    raise ChangeEngineError("member ref must specify node_name or address")


def resolve_pool_member_edits(
    edits: List[PoolMemberEdit],
    vips_by_name: Dict[str, Vip],
    pools_by_name: Dict[str, Pool],
    nodes_by_name: Dict[str, Node],
) -> List[ResolvedPoolMemberChange]:
    results: List[ResolvedPoolMemberChange] = []

    for edit in edits:
        vip = vips_by_name.get(edit.vip_name)
        if vip is None or not vip.pool_name:
            raise ChangeEngineError(
                "pool member edit for %s has no resolvable pool" % edit.vip_name
            )
        pool = pools_by_name.get(vip.pool_name)
        if pool is None:
            raise ChangeEngineError("pool %s not found" % vip.pool_name)

        current = [
            ResolvedMember(
                node_name=m.node_name,
                port=m.port,
                address=nodes_by_name[m.node_name].address if m.node_name in nodes_by_name else None,
            )
            for m in pool.members
        ]

        if edit.action == "replace_all":
            old_members = current
            new_members = [_resolve_member_ref(r, nodes_by_name) for r in edit.new_refs]
        elif edit.action == "add":
            old_members = []
            new_members = current + [_resolve_member_ref(r, nodes_by_name) for r in edit.new_refs]
        elif edit.action == "remove":
            remove_keys = {(r.node_name, r.port) for r in edit.old_refs if r.node_name}
            old_members = [m for m in current if (m.node_name, m.port) in remove_keys]
            new_members = [m for m in current if (m.node_name, m.port) not in remove_keys]
        elif edit.action == "replace_selected":
            remove_keys = {(r.node_name, r.port) for r in edit.old_refs if r.node_name}
            old_members = [m for m in current if (m.node_name, m.port) in remove_keys]
            kept = [m for m in current if (m.node_name, m.port) not in remove_keys]
            new_members = kept + [_resolve_member_ref(r, nodes_by_name) for r in edit.new_refs]
        else:
            raise ChangeEngineError("unknown pool member edit action %r" % edit.action)

        results.append(
            ResolvedPoolMemberChange(
                vip_name=edit.vip_name,
                pool_name=pool.name,
                action=edit.action,
                old_members=old_members,
                new_members=new_members,
            )
        )

    _check_no_conflicting_pool_edits(results)
    return results


def _member_key_set(members: List[ResolvedMember]):
    return frozenset((m.node_name, m.port) for m in members)


def _check_no_conflicting_pool_edits(results: List[ResolvedPoolMemberChange]) -> None:
    """Two selected VIPs that share a pool (a common real-world case -- see
    the synthetic fixture's SIP pool) can each be given an independent
    per-VIP pool-member edit. Both edits resolve to the same pool, but
    emit_order.build_migration_context stores pool_effective_members in a
    dict keyed by pool name, so only the last-processed edit would survive
    -- silently discarding the other VIP's intended members with no error.
    Block that here instead of guessing which edit the user "really"
    meant.
    """
    by_pool: Dict[str, List[ResolvedPoolMemberChange]] = {}
    for r in results:
        by_pool.setdefault(r.pool_name, []).append(r)

    for pool_name, edits in by_pool.items():
        if len(edits) < 2:
            continue
        distinct = {_member_key_set(e.new_members) for e in edits}
        if len(distinct) > 1:
            vip_names = ", ".join(e.vip_name for e in edits)
            raise ChangeEngineError(
                "conflicting pool member edits for shared pool %s: %s all "
                "reference it but were given different member lists -- "
                "since they share one pool, edit it once (e.g. via a "
                "common change) instead of per-VIP exceptions that disagree"
                % (pool_name, vip_names)
            )


def resolve(
    plan: MigrationPlan,
    nodes_by_name: Dict[str, Node],
    pools_by_name: Dict[str, Pool],
    vips_by_name: Dict[str, Vip],
    graph: DependencyGraph,
) -> ResolvedMigrationPlan:
    selected_set = set(plan.selected_vips)
    for exc in plan.exceptions:
        if exc.vip_name not in selected_set:
            raise ChangeEngineError(
                "exception for %s references a VIP not in the current selection"
                % exc.vip_name
            )

    exceptions_by_vip = {e.vip_name: e for e in plan.exceptions}

    vip_changes: List[ResolvedVipChange] = []
    for vip_name in plan.selected_vips:
        effective: Dict[ChangeType, Dict] = {}
        for cc in plan.common_changes:
            effective[cc.change_type] = dict(cc.payload)
        exception = exceptions_by_vip.get(vip_name)
        if exception:
            for change_type, override_payload in exception.overrides.items():
                effective[change_type] = dict(override_payload)
        vip_changes.append(ResolvedVipChange(vip_name=vip_name, effective=effective))

    resolved_node_changes = resolve_node_changes(plan.node_changes, nodes_by_name, graph)

    resolved_pool_member_changes = resolve_pool_member_edits(
        plan.pool_member_edits, vips_by_name, pools_by_name, nodes_by_name
    )

    resolved_vlan_changes: List[ResolvedVlanChange] = []
    for vc in vip_changes:
        vlan_payload = vc.effective.get(ChangeType.VLANS)
        if not vlan_payload:
            continue
        vip = vips_by_name[vc.vip_name]
        old_vlan = vlan_payload.get("old_vlan")
        new_vlan = vlan_payload.get("new_vlan")
        action = vlan_payload.get("action")  # "replace" | "remove" | "add"; inferred if omitted
        if action is None:
            if old_vlan and new_vlan:
                action = "replace"
            elif old_vlan:
                action = "remove"
            elif new_vlan:
                action = "add"
            else:
                action = "noop"

        if action == "replace" and old_vlan and new_vlan:
            new_vlans = [new_vlan if v == old_vlan else v for v in vip.vlans]
        elif action == "remove" and old_vlan:
            # Real gap this fixes: a VLAN-only-remove request (old_vlan set,
            # no new_vlan) used to fall through to the no-op branch below
            # and silently do nothing -- the operator's remove request was
            # dropped with zero indication anything was wrong.
            new_vlans = [v for v in vip.vlans if v != old_vlan]
        elif action == "add" and new_vlan:
            new_vlans = list(vip.vlans) if new_vlan in vip.vlans else list(vip.vlans) + [new_vlan]
        else:
            new_vlans = list(vip.vlans)
        resolved_vlan_changes.append(
            ResolvedVlanChange(
                vip_name=vc.vip_name,
                old_vlans=list(vip.vlans),
                new_vlans=new_vlans,
                vlans_enabled=vip.vlans_enabled,
            )
        )

    return ResolvedMigrationPlan(
        session_id=plan.session_id,
        vip_changes=vip_changes,
        resolved_node_changes=resolved_node_changes,
        resolved_pool_member_changes=resolved_pool_member_changes,
        resolved_vlan_changes=resolved_vlan_changes,
        create_network_objects=plan.create_network_objects,
    )
