"""Resolves node-level changes exactly once per physical node, even when
the wizard's NodeChange list is driven by 100 VIPs sharing that node --
this is a dependency-level operation, not a per-VIP one.
"""
from typing import Dict, List

from app.ingest.net_address import parse_node_address
from app.models.change_set import NodeChange, ResolvedNodeChange
from app.models.domain import Node
from app.models.graph import DependencyGraph


class NodeCascadeError(Exception):
    pass


def resolve_node_changes(
    node_changes: List[NodeChange],
    nodes_by_name: Dict[str, Node],
    graph: DependencyGraph,
) -> List[ResolvedNodeChange]:
    by_address = {n.address: n.name for n in nodes_by_name.values()}
    resolved: Dict[str, ResolvedNodeChange] = {}

    for nc in node_changes:
        if nc.old_node_ref in nodes_by_name:
            old_node_name = nc.old_node_ref
        elif nc.old_node_ref in by_address:
            old_node_name = by_address[nc.old_node_ref]
        else:
            raise NodeCascadeError(
                "cannot resolve node reference %r to a known node name or "
                "address" % nc.old_node_ref
            )

        old_node = nodes_by_name[old_node_name]
        new_address, _family = parse_node_address(nc.new_ip)
        new_node_name = nc.new_node_name or old_node_name

        existing = resolved.get(old_node_name)
        if existing is not None and (
            existing.new_address != new_address or existing.new_node_name != new_node_name
        ):
            raise NodeCascadeError(
                "conflicting node changes for %s: one change asks for %s/%s, "
                "another asks for %s/%s -- resolve this to a single change "
                "before generating" % (
                    old_node_name,
                    existing.new_node_name,
                    existing.new_address,
                    new_node_name,
                    new_address,
                )
            )

        resolved[old_node_name] = ResolvedNodeChange(
            old_node_name=old_node_name,
            old_address=old_node.address,
            new_address=new_address,
            new_node_name=new_node_name,
            affected_pools=graph.pools_using_node(old_node_name),
            affected_vips=graph.vips_using_node(old_node_name),
        )

    return list(resolved.values())
