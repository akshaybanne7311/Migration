"""Migration plan models: what the wizard builds (MigrationPlan) and what
the change engine produces after merging common changes + exceptions and
cascading node/pool-member changes (ResolvedMigrationPlan).
"""
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ChangeType(str, Enum):
    VIP_NAME = "vip_name"
    VIP_IP_PORT = "vip_ip_port"
    POOL_NAME = "pool_name"
    POOL_MEMBERS = "pool_members"
    VLANS = "vlans"
    PROFILES = "profiles"
    PERSISTENCE = "persistence"
    MONITOR = "monitor"


class CommonChange(BaseModel):
    change_type: ChangeType
    payload: Dict[str, Any] = Field(default_factory=dict)


class MemberRef(BaseModel):
    node_name: Optional[str] = None
    address: Optional[str] = None
    new_node_name: Optional[str] = None
    port: int


class PoolMemberEdit(BaseModel):
    vip_name: str
    action: Literal["add", "remove", "replace_selected", "replace_all"]
    old_refs: List[MemberRef] = Field(default_factory=list)
    new_refs: List[MemberRef] = Field(default_factory=list)


class NodeChange(BaseModel):
    old_node_ref: str  # node name OR old IP address
    new_ip: str
    new_node_name: Optional[str] = None


class VipException(BaseModel):
    vip_name: str
    overrides: Dict[ChangeType, Dict[str, Any]] = Field(default_factory=dict)


class MigrationPlan(BaseModel):
    session_id: str
    selected_vips: List[str] = Field(default_factory=list)
    common_changes: List[CommonChange] = Field(default_factory=list)
    node_changes: List[NodeChange] = Field(default_factory=list)
    pool_member_edits: List[PoolMemberEdit] = Field(default_factory=list)
    exceptions: List[VipException] = Field(default_factory=list)
    create_network_objects: bool = False
    # "changes_only" patches fields the plan actually changes and assumes
    # every referenced node/monitor/pool/virtual already exists on the
    # target (in-place edit on the same device). "full_recreate" emits a
    # complete script to stand the selected VIPs' whole dependency closure
    # up on a target device that doesn't have any of it yet -- see
    # generation/full_recreate.py.
    output_mode: Literal["changes_only", "full_recreate"] = "changes_only"


class ResolvedVipChange(BaseModel):
    vip_name: str
    effective: Dict[ChangeType, Dict[str, Any]] = Field(default_factory=dict)


class ResolvedNodeChange(BaseModel):
    old_node_name: str
    old_address: str
    new_address: str
    new_node_name: str
    affected_pools: List[str] = Field(default_factory=list)
    affected_vips: List[str] = Field(default_factory=list)


class ResolvedMember(BaseModel):
    node_name: str
    address: Optional[str] = None
    is_new_node: bool = False
    port: int


class ResolvedPoolMemberChange(BaseModel):
    vip_name: str
    pool_name: str
    action: str
    old_members: List[ResolvedMember] = Field(default_factory=list)
    new_members: List[ResolvedMember] = Field(default_factory=list)


class ResolvedVlanChange(BaseModel):
    vip_name: str
    old_vlans: List[str] = Field(default_factory=list)
    new_vlans: List[str] = Field(default_factory=list)
    vlans_enabled: bool = True


class ResolvedMigrationPlan(BaseModel):
    session_id: str
    vip_changes: List[ResolvedVipChange] = Field(default_factory=list)
    resolved_node_changes: List[ResolvedNodeChange] = Field(default_factory=list)
    resolved_pool_member_changes: List[ResolvedPoolMemberChange] = Field(default_factory=list)
    resolved_vlan_changes: List[ResolvedVlanChange] = Field(default_factory=list)
    create_network_objects: bool = False
