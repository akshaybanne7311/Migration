"""Orchestrates: raw bigip.conf text -> tokens -> stanzas -> typed objects.

Ingest order matters: nodes -> monitors -> vlans -> pools -> virtuals.
Pools resolve pool-member references against the already-populated node
table (name lookup first, address-shaped parsing as fallback), which is
why nodes must be mapped in an earlier pass.
"""
import dataclasses
from typing import List, Optional

from app.ingest.parser import TmosStanza, parse_text
from app.ingest.stanza_mappers import (
    MappingError,
    map_monitor,
    map_node,
    map_pool,
    map_system_object,
    map_vlan,
    map_virtual,
)
from app.models.domain import ParsedConfig

# Network/system-layer stanzas (from bigip_base.conf) surfaced read-only in
# GUI Preview's Network/System sections -- everything a real device's
# Network and System admin pages would show beyond VLANs (which already
# have their own typed model/table). These have a real (partition-prefixed)
# object name so the parser's generic type/name split already works.
_SYSTEM_OBJECT_EXACT_TYPES = (
    "net self",
    "net route",
    "net route-domain",
    "net dns-resolver",
    "ltm virtual-address",
    "cm device",
    "cm device-group",
    "cm traffic-group",
    "sys global-settings",
    "sys management-route",
    "sys ntp",
    "sys dns",
    "sys snmp",
    "sys syslog",
)

# These are named without a leading "/" (`net trunk HA-TRUNK { }`,
# `sys management-ip 10.59.235.25/28 { }`, `sys provision ltm { }`) -- the
# parser's type/name splitter only stops accumulating type tokens at a
# token starting with "/", so the name ends up folded into object_type
# (e.g. object_type becomes "net trunk HA-TRUNK", object_name ""). Matched
# by prefix here and the real name recovered from what follows the prefix.
_SYSTEM_OBJECT_PREFIX_TYPES = (
    "net trunk",
    "sys management-ip",
    "sys provision",
)


def _match_system_stanza(stanza: TmosStanza) -> Optional[TmosStanza]:
    if stanza.object_type in _SYSTEM_OBJECT_EXACT_TYPES:
        return stanza
    for prefix in _SYSTEM_OBJECT_PREFIX_TYPES:
        if stanza.object_type == prefix:
            return stanza
        if stanza.object_type.startswith(prefix + " "):
            recovered_name = stanza.object_type[len(prefix) :].strip()
            return dataclasses.replace(stanza, object_type=prefix, object_name=recovered_name)
    return None


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

    for stanza in stanzas:
        matched = _match_system_stanza(stanza)
        if matched is None:
            continue
        config.system_objects.append(map_system_object(matched))

    return config
