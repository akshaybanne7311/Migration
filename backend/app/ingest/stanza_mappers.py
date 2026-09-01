"""Map generic TmosStanza trees into typed domain objects.

Every field pull is an explicit `.get()` against the parsed stanza; a
genuinely missing required field raises MappingError (caught by the
ingest pipeline as a per-object parse warning, object skipped) rather
than silently defaulting to a fabricated placeholder value -- this is
the structural enforcement of "no demo/fake data reaches production
screens."
"""
import json
from typing import Any, Dict, List, Optional, Tuple

from app.ingest.net_address import (
    AddressParseError,
    parse_destination,
    parse_node_address,
    split_ref_port,
    strip_partition,
)
from app.ingest.parser import TmosStanza
from app.models.domain import Monitor, Node, Pool, PoolMember, Profile, Vip, Vlan


class MappingError(Exception):
    pass


def _partition_of(name: str) -> str:
    if name.startswith("/"):
        parts = name[1:].split("/", 1)
        if parts and parts[0]:
            return parts[0]
    return "Common"


def _as_str(val: Any) -> Optional[str]:
    return val if isinstance(val, str) else None


def _as_int(val: Any) -> Optional[int]:
    if isinstance(val, str) and val.lstrip("-").isdigit():
        return int(val)
    return None


def map_node(stanza: TmosStanza) -> Node:
    addr_raw = _as_str(stanza.entries.get("address"))
    if not addr_raw:
        raise MappingError("ltm node %s missing address" % stanza.object_name)
    address, family = parse_node_address(addr_raw)
    return Node(
        name=stanza.object_name,
        address=address,
        address_family=family,
        partition=_partition_of(stanza.object_name),
        state=_as_str(stanza.entries.get("state")),
        source_stanza_json=json.dumps(stanza.entries, default=str),
    )


def map_monitor(stanza: TmosStanza) -> Monitor:
    type_parts = stanza.object_type.split(" ")
    return Monitor(
        name=stanza.object_name,
        monitor_type=type_parts[-1] if type_parts else None,
        interval=_as_int(stanza.entries.get("interval")),
        timeout=_as_int(stanza.entries.get("timeout")),
        source_stanza_json=json.dumps(stanza.entries, default=str),
    )


def map_vlan(stanza: TmosStanza) -> Vlan:
    interfaces_val = stanza.entries.get("interfaces")
    if isinstance(interfaces_val, list):
        interfaces = interfaces_val
    elif isinstance(interfaces_val, dict):
        interfaces = list(interfaces_val.keys())
    else:
        interfaces = []
    return Vlan(
        name=stanza.object_name,
        tag=_as_int(stanza.entries.get("tag")),
        interfaces=interfaces,
        source_stanza_json=json.dumps(stanza.entries, default=str),
    )


def _extract_monitor_names(monitor_val: Any) -> List[str]:
    if isinstance(monitor_val, str):
        return [monitor_val]
    if isinstance(monitor_val, list):
        return monitor_val
    if isinstance(monitor_val, dict) and "_block" in monitor_val:
        block = monitor_val["_block"]
        if isinstance(block, list):
            return block
        if isinstance(block, dict):
            return list(block.keys())
    return []


def map_pool_members(
    stanza: TmosStanza, known_nodes: Dict[str, Node]
) -> Tuple[List[PoolMember], List[Node], List[str]]:
    """Returns (members, synthesized_nodes, warnings). `known_nodes` is
    keyed by full node name (e.g. "/Common/MNP-Node-1") and must already
    be populated -- ingest order is nodes before pools so member refs can
    be resolved against real node objects (node-name lookup first, address
    parsing only as a fallback for implicit/orphan members).
    """
    members: List[PoolMember] = []
    synthesized: Dict[str, Node] = {}
    warnings: List[str] = []

    members_val = stanza.entries.get("members")
    if not isinstance(members_val, dict):
        return members, [], warnings

    for member_key, attrs in members_val.items():
        attrs = attrs if isinstance(attrs, dict) else {}
        name_or_addr, port = split_ref_port(member_key)
        if port is None:
            port_attr = _as_int(attrs.get("port"))
            if port_attr is None:
                warnings.append(
                    "pool %s: member %s has no resolvable port, skipped"
                    % (stanza.object_name, member_key)
                )
                continue
            port = port_attr

        if name_or_addr in known_nodes:
            node_name = known_nodes[name_or_addr].name
        else:
            addr_source = _as_str(attrs.get("address")) or strip_partition(name_or_addr)
            try:
                address, family = parse_node_address(addr_source)
            except AddressParseError:
                # a genuine custom node name with no matching `ltm node`
                # object and no parseable address -- keep the literal
                # reference rather than fabricating an address.
                node_name = name_or_addr
                warnings.append(
                    "pool %s: member %s has no matching node object and no "
                    "parseable address" % (stanza.object_name, member_key)
                )
            else:
                partition = _partition_of(name_or_addr)
                synth_name = (
                    name_or_addr if name_or_addr.startswith("/") else "/%s/%s" % (partition, address)
                )
                if synth_name not in synthesized:
                    synthesized[synth_name] = Node(
                        name=synth_name,
                        address=address,
                        address_family=family,
                        partition=partition,
                        source_stanza_json="{}",
                    )
                node_name = synth_name

        members.append(
            PoolMember(
                pool_name=stanza.object_name,
                node_name=node_name,
                port=port,
                session_state=_as_str(attrs.get("session")),
                connection_limit=_as_int(attrs.get("connection-limit")),
                source_stanza_json=json.dumps(attrs, default=str),
            )
        )

    return members, list(synthesized.values()), warnings


def map_pool(
    stanza: TmosStanza, known_nodes: Dict[str, Node]
) -> Tuple[Pool, List[Node], List[str]]:
    members, synthesized_nodes, warnings = map_pool_members(stanza, known_nodes)
    pool = Pool(
        name=stanza.object_name,
        partition=_partition_of(stanza.object_name),
        monitor_names=_extract_monitor_names(stanza.entries.get("monitor")),
        members=members,
        source_stanza_json=json.dumps(stanza.entries, default=str),
    )
    return pool, synthesized_nodes, warnings


def map_virtual(stanza: TmosStanza) -> Vip:
    dest_raw = _as_str(stanza.entries.get("destination"))
    if not dest_raw:
        raise MappingError("ltm virtual %s missing destination" % stanza.object_name)
    dest = parse_destination(dest_raw)

    vlans_val = stanza.entries.get("vlans")
    vlans = vlans_val if isinstance(vlans_val, list) else []
    vlans_enabled = "vlans-disabled" not in stanza.entries

    profiles_val = stanza.entries.get("profiles")
    profiles: List[Profile] = []
    if isinstance(profiles_val, dict):
        for pname, pattrs in profiles_val.items():
            context = None
            if isinstance(pattrs, dict):
                context = _as_str(pattrs.get("context"))
            profiles.append(Profile(name=pname, context=context))

    persist_val = stanza.entries.get("persist")
    persistence = None
    if isinstance(persist_val, dict) and persist_val:
        persistence = next(iter(persist_val.keys()))

    snat_val = stanza.entries.get("source-address-translation")
    snat_type = None
    if isinstance(snat_val, dict):
        t = _as_str(snat_val.get("type"))
        if t == "snat" and isinstance(snat_val.get("pool"), str):
            snat_type = "snat:%s" % snat_val["pool"]
        elif t:
            snat_type = t

    rules_val = stanza.entries.get("rules")
    irules = rules_val if isinstance(rules_val, list) else []

    return Vip(
        name=stanza.object_name,
        partition=_partition_of(stanza.object_name),
        destination_address=dest.address,
        destination_port=dest.port if dest.port is not None else 0,
        address_family=dest.family,
        route_domain=dest.route_domain,
        ip_protocol=_as_str(stanza.entries.get("ip-protocol")),
        pool_name=_as_str(stanza.entries.get("pool")),
        vlans=vlans,
        vlans_enabled=vlans_enabled,
        profiles=profiles,
        persistence=persistence,
        snat_type=snat_type,
        irules=irules,
        mask=_as_str(stanza.entries.get("mask")),
        monitor_names=_extract_monitor_names(stanza.entries.get("monitor")),
        source_stanza_json=json.dumps(stanza.entries, default=str),
    )
