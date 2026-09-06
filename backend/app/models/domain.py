"""Typed domain objects for parsed TMOS configuration.

Python-3.9-compatible typing throughout (Optional/Union, not `X | Y`).
"""
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class AddressFamily(str, Enum):
    IPV4 = "ipv4"
    IPV6 = "ipv6"


class Node(BaseModel):
    name: str
    address: str
    address_family: AddressFamily
    partition: str = "Common"
    state: Optional[str] = None
    source_stanza_json: str = "{}"


class Monitor(BaseModel):
    name: str
    monitor_type: Optional[str] = None
    interval: Optional[int] = None
    timeout: Optional[int] = None
    source_stanza_json: str = "{}"


class PoolMember(BaseModel):
    pool_name: str
    node_name: str
    port: int
    session_state: Optional[str] = None
    connection_limit: Optional[int] = None
    source_stanza_json: str = "{}"


class Pool(BaseModel):
    name: str
    partition: str = "Common"
    monitor_names: List[str] = Field(default_factory=list)
    members: List[PoolMember] = Field(default_factory=list)
    source_stanza_json: str = "{}"


class Vlan(BaseModel):
    name: str
    tag: Optional[int] = None
    interfaces: List[str] = Field(default_factory=list)
    source_stanza_json: str = "{}"


class Profile(BaseModel):
    name: str
    context: Optional[str] = None


class Vip(BaseModel):
    name: str
    partition: str = "Common"
    destination_address: str
    destination_port: int
    address_family: AddressFamily
    route_domain: Optional[int] = None
    ip_protocol: Optional[str] = None
    pool_name: Optional[str] = None
    vlans: List[str] = Field(default_factory=list)
    vlans_enabled: bool = True
    profiles: List[Profile] = Field(default_factory=list)
    persistence: Optional[str] = None
    snat_type: Optional[str] = None
    irules: List[str] = Field(default_factory=list)
    mask: Optional[str] = None
    monitor_names: List[str] = Field(default_factory=list)
    source_stanza_json: str = "{}"


class SystemObject(BaseModel):
    """A network/system-layer stanza (self IP, trunk, route, route domain,
    hostname, NTP, management IP, ...) kept as its raw parsed entries --
    there's no dedicated typed model per stanza kind, unlike Vip/Pool/Node,
    because these are surfaced read-only (GUI Preview's Network/System
    sections) rather than fed into the change engine."""

    object_type: str
    name: str
    entries_json: str = "{}"


class CommandHistoryEntry(BaseModel):
    """One real tmsh command from a `.tmsh-history-<user>` file inside the
    archive -- shell history, not device config, so it lives outside
    ParsedConfig/system_objects and is written via its own table."""

    user: str
    timestamp: str
    command: str
    is_mutating: bool
    contains_secret: bool = False


class ParsedConfig(BaseModel):
    """Everything extracted from one bigip.conf, before any DB write."""

    nodes: Dict[str, Node] = Field(default_factory=dict)
    monitors: Dict[str, Monitor] = Field(default_factory=dict)
    pools: Dict[str, Pool] = Field(default_factory=dict)
    vlans: Dict[str, Vlan] = Field(default_factory=dict)
    vips: Dict[str, Vip] = Field(default_factory=dict)
    system_objects: List[SystemObject] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
