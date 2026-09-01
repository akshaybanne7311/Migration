"""Dependency graph wrapper.

Node identity is a (object_type, canonical_name) tuple, which is what
makes a Node/Pool/Vlan shared by many VIPs collapse to exactly one graph
node "for free" -- networkx's add_node is idempotent on a repeated key,
so no manual "have I seen this before" bookkeeping is needed anywhere
that builds or walks this graph.
"""
from typing import Dict, List, Set, Tuple

import networkx as nx
from pydantic import BaseModel

NodeKey = Tuple[str, str]  # (object_type, canonical_name) e.g. ("node", "/Common/n1")


class SelectionCounts(BaseModel):
    vips: int = 0
    pools: int = 0
    pool_members: int = 0
    nodes: int = 0
    vlan_refs: int = 0


class DependencyGraph:
    def __init__(self) -> None:
        self.g = nx.MultiDiGraph()

    # -- construction -----------------------------------------------
    def add_object(self, object_type: str, name: str, **data) -> NodeKey:
        key: NodeKey = (object_type, name)
        self.g.add_node(key, **data)
        return key

    def add_edge(self, src: NodeKey, dst: NodeKey, relation: str, **data) -> None:
        self.g.add_edge(src, dst, relation=relation, **data)

    # -- queries ------------------------------------------------------
    def edges_from(self, key: NodeKey, relation: str = None) -> List[Tuple[NodeKey, dict]]:
        result = []
        if key not in self.g:
            return result
        for _, dst, data in self.g.out_edges(key, data=True):
            if relation is None or data.get("relation") == relation:
                result.append((dst, data))
        return result

    def edges_to(self, key: NodeKey, relation: str = None) -> List[Tuple[NodeKey, dict]]:
        result = []
        if key not in self.g:
            return result
        for src, _, data in self.g.in_edges(key, data=True):
            if relation is None or data.get("relation") == relation:
                result.append((src, data))
        return result

    def counts_for_selection(self, vip_names: List[str]) -> SelectionCounts:
        vip_keys = [("vip", n) for n in vip_names if ("vip", n) in self.g]

        pool_keys: Set[NodeKey] = set()
        vlan_ref_count = 0
        for vk in vip_keys:
            for dst, data in self.edges_from(vk, "uses_pool"):
                pool_keys.add(dst)
            for _dst, _data in self.edges_from(vk, "uses_vlan"):
                vlan_ref_count += 1

        node_keys: Set[NodeKey] = set()
        member_count = 0
        for pk in pool_keys:
            for dst, _data in self.edges_from(pk, "has_member"):
                node_keys.add(dst)
                member_count += 1

        return SelectionCounts(
            vips=len(vip_keys),
            pools=len(pool_keys),
            pool_members=member_count,
            nodes=len(node_keys),
            vlan_refs=vlan_ref_count,
        )

    def vips_using_node(self, node_name: str) -> List[str]:
        node_key: NodeKey = ("node", node_name)
        pool_keys = [src for src, _ in self.edges_to(node_key, "has_member")]
        vip_names: Set[str] = set()
        for pk in pool_keys:
            for src, _ in self.edges_to(pk, "uses_pool"):
                vip_names.add(src[1])
        return sorted(vip_names)

    def pools_using_node(self, node_name: str) -> List[str]:
        node_key: NodeKey = ("node", node_name)
        return sorted({src[1] for src, _ in self.edges_to(node_key, "has_member")})
