"""Orchestrates: raw bigip.conf text -> tokens -> stanzas -> typed objects.

Ingest order matters: nodes -> monitors -> vlans -> pools -> virtuals.
Pools resolve pool-member references against the already-populated node
table (name lookup first, address-shaped parsing as fallback), which is
why nodes must be mapped in an earlier pass.
"""
from typing import List

from app.ingest.parser import TmosStanza, parse_text
from app.ingest.stanza_mappers import (
    MappingError,
    map_monitor,
    map_node,
    map_pool,
    map_vlan,
    map_virtual,
)
from app.models.domain import ParsedConfig


def parse_bigip_conf(text: str) -> ParsedConfig:
    stanzas: List[TmosStanza] = parse_text(text)
    config = ParsedConfig()

    for stanza in stanzas:
        if stanza.object_type != "ltm node":
            continue
        try:
            node = map_node(stanza)
            config.nodes[node.name] = node
        except MappingError as exc:
            config.warnings.append(str(exc))

    for stanza in stanzas:
        if not stanza.object_type.startswith("ltm monitor"):
            continue
        try:
            monitor = map_monitor(stanza)
            config.monitors[monitor.name] = monitor
        except MappingError as exc:
            config.warnings.append(str(exc))

    for stanza in stanzas:
        if stanza.object_type != "net vlan":
            continue
        try:
            vlan = map_vlan(stanza)
            config.vlans[vlan.name] = vlan
        except MappingError as exc:
            config.warnings.append(str(exc))

    for stanza in stanzas:
        if stanza.object_type != "ltm pool":
            continue
        try:
            pool, synthesized_nodes, warnings = map_pool(stanza, config.nodes)
            config.pools[pool.name] = pool
            for node in synthesized_nodes:
                config.nodes.setdefault(node.name, node)
            config.warnings.extend(warnings)
        except MappingError as exc:
            config.warnings.append(str(exc))

    for stanza in stanzas:
        if stanza.object_type != "ltm virtual":
            continue
        try:
            vip = map_virtual(stanza)
            config.vips[vip.name] = vip
        except MappingError as exc:
            config.warnings.append(str(exc))

    return config
