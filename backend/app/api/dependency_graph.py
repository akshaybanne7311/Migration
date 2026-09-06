import sqlite3
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.deps import get_session_db
from app.graph.builder import build_dependency_graph

router = APIRouter(prefix="/api/v1/sessions/{session_id}/dependency-graph", tags=["dependency-graph"])


class GraphNode(BaseModel):
    type: str
    name: str
    attrs: Dict[str, Any] = {}


class VipDependencyGraph(BaseModel):
    vip: GraphNode
    pools: List[GraphNode]
    nodes: List[GraphNode]
    vlans: List[GraphNode]
    monitors: List[GraphNode]
    profiles: List[GraphNode]


def _node(key, data: Optional[Dict[str, Any]] = None) -> GraphNode:
    obj_type, name = key
    return GraphNode(type=obj_type, name=name, attrs=data or {})


@router.get("", response_model=VipDependencyGraph)
def get_vip_dependency_graph(
    session_id: str, vip: str = Query(...), conn: sqlite3.Connection = Depends(get_session_db)
) -> VipDependencyGraph:
    """The full real dependency chain for one VIP -- pool, its members
    (nodes), VLANs, monitors (both the VIP's own and its pool's), and
    profiles -- for a visual topology view rather than reading it back out
    of a properties table. Built from the same DependencyGraph the
    selection-count/orphan-detection logic already uses, so this view can
    never disagree with what Smart Migration counts as "affected"."""
    graph = build_dependency_graph(conn)
    vip_key = ("vip", vip)
    if vip_key not in graph.g:
        raise HTTPException(status_code=404, detail="vip not found in this session's parsed config")

    pool_edges = graph.edges_from(vip_key, "uses_pool")
    vlan_edges = graph.edges_from(vip_key, "uses_vlan")
    profile_edges = graph.edges_from(vip_key, "uses_profile")
    vip_monitor_edges = graph.edges_from(vip_key, "uses_monitor")

    node_keys_seen = set()
    monitor_keys_seen = {k for k, _ in vip_monitor_edges}
    nodes: List[GraphNode] = []
    monitors: List[GraphNode] = [_node(k, graph.g.nodes.get(k)) for k, _ in vip_monitor_edges]

    for pool_key, _ in pool_edges:
        for dst, edge_data in graph.edges_from(pool_key, "has_member"):
            if dst in node_keys_seen:
                continue
            node_keys_seen.add(dst)
            attrs = dict(graph.g.nodes.get(dst, {}))
            attrs["port"] = edge_data.get("port")
            nodes.append(_node(dst, attrs))
        for dst, _ in graph.edges_from(pool_key, "uses_monitor"):
            if dst in monitor_keys_seen:
                continue
            monitor_keys_seen.add(dst)
            monitors.append(_node(dst, graph.g.nodes.get(dst)))

    return VipDependencyGraph(
        vip=_node(vip_key, graph.g.nodes.get(vip_key)),
        pools=[_node(k, graph.g.nodes.get(k)) for k, _ in pool_edges],
        nodes=nodes,
        vlans=[_node(k, graph.g.nodes.get(k)) for k, _ in vlan_edges],
        monitors=monitors,
        profiles=[_node(k, graph.g.nodes.get(k)) for k, _ in profile_edges],
    )
