import sqlite3

from app.models.graph import DependencyGraph
from app.storage.repositories import NodeRepository, PoolRepository, VipRepository, VlanRepository


def build_dependency_graph(conn: sqlite3.Connection) -> DependencyGraph:
    graph = DependencyGraph()

    for node in NodeRepository.list(conn):
        graph.add_object("node", node.name, address=node.address, family=node.address_family.value)

    for vlan in VlanRepository.list(conn):
        graph.add_object("vlan", vlan.name, tag=vlan.tag)

    for pool in PoolRepository.list(conn):
        graph.add_object("pool", pool.name)
        for monitor_name in pool.monitor_names:
            graph.add_object("monitor", monitor_name)
            graph.add_edge(("pool", pool.name), ("monitor", monitor_name), "uses_monitor")
        for member in pool.members:
            if ("node", member.node_name) not in graph.g:
                graph.add_object("node", member.node_name)
            graph.add_edge(
                ("pool", pool.name),
                ("node", member.node_name),
                "has_member",
                port=member.port,
            )

    for vip in VipRepository.list(conn):
        graph.add_object("vip", vip.name, destination=vip.destination_address, port=vip.destination_port)
        if vip.pool_name:
            if ("pool", vip.pool_name) not in graph.g:
                graph.add_object("pool", vip.pool_name)
            graph.add_edge(("vip", vip.name), ("pool", vip.pool_name), "uses_pool")
        for vlan_name in vip.vlans:
            if ("vlan", vlan_name) not in graph.g:
                graph.add_object("vlan", vlan_name)
            graph.add_edge(("vip", vip.name), ("vlan", vlan_name), "uses_vlan")
        for profile in vip.profiles:
            graph.add_object("profile", profile.name, context=profile.context)
            graph.add_edge(("vip", vip.name), ("profile", profile.name), "uses_profile")
        for monitor_name in vip.monitor_names:
            graph.add_object("monitor", monitor_name)
            graph.add_edge(("vip", vip.name), ("monitor", monitor_name), "uses_monitor")

    return graph
