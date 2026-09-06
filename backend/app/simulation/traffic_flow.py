"""Simulates a connection's real decision path through one VIP's parsed
config -- destination match, load-balancing member selection, persistence,
and SNAT -- and a deterministic trace of where N sequential connections
would land.

This is explicitly NOT packet capture or replay: no real traffic data
exists in any of this tool's real UCS/QKView archives (checked directly
against all of them; the only match for a pcap-like filename was a
cleanup script, not a capture). What this simulates instead is real and
verifiable: the actual pool members, the actual load-balancing method,
the actual persistence/SNAT configuration, parsed straight from the
device's own saved config -- just not live traffic against them, since
none exists to simulate against.

Member "enabled" state reflects the config snapshot's admin session-state
(user-enabled/user-disabled), not live monitor health -- a config export
has no notion of which members are actually passing health checks right
now. Load-balancing beyond round-robin (least-connections, fastest, ratio
without explicit ratios, ...) needs live connection/response-time data
this tool doesn't have; those methods are simulated as round-robin with
an explicit note saying so, not silently misrepresented as accurate.
"""
from typing import Dict, List, Optional

from pydantic import BaseModel

from app.models.domain import Node, Pool, Vip


class FlowMember(BaseModel):
    name: str
    address: str
    port: int
    enabled: bool


class SimulatedRequest(BaseModel):
    sequence: int
    member_name: str
    member_address: str


class TrafficFlowResult(BaseModel):
    vip_name: str
    destination: str
    protocol: str
    pool_name: Optional[str]
    load_balancing_method: str
    load_balancing_is_simulated_as_round_robin: bool
    persistence: Optional[str]
    snat_type: Optional[str]
    monitors: List[str]
    members: List[FlowMember]
    simulated_requests: List[SimulatedRequest]
    note: str


_TRUE_ROUND_ROBIN_METHODS = {"round-robin", "", None}


def simulate_traffic_flow(
    vip: Vip, pool: Optional[Pool], lb_method: str, nodes_by_name: Dict[str, Node], request_count: int = 10
) -> TrafficFlowResult:
    members: List[FlowMember] = []
    if pool is not None:
        for m in pool.members:
            node = nodes_by_name.get(m.node_name)
            members.append(
                FlowMember(
                    name=m.node_name,
                    address=node.address if node else "",
                    port=m.port,
                    enabled=m.session_state != "user-disabled",
                )
            )

    enabled_members = [m for m in members if m.enabled]
    simulated_requests: List[SimulatedRequest] = []
    if enabled_members:
        for i in range(request_count):
            member = enabled_members[i % len(enabled_members)]
            simulated_requests.append(SimulatedRequest(sequence=i + 1, member_name=member.name, member_address=member.address))

    is_simulated_rr = lb_method.lower() not in _TRUE_ROUND_ROBIN_METHODS
    note_parts = []
    if not pool:
        note_parts.append("this VIP has no pool assigned -- nothing to load-balance to.")
    elif not enabled_members:
        note_parts.append("every pool member is administratively disabled in this config snapshot -- no member would receive traffic.")
    if is_simulated_rr:
        note_parts.append(
            "this pool's real load-balancing method is \"%s\", which depends on live connection/response-time data "
            "this tool doesn't have; the sequence below is simulated as round-robin instead, not the real algorithm's output." % lb_method
        )
    if not note_parts:
        note_parts.append("round-robin is this pool's real configured method, so the simulated sequence reflects real behavior.")

    return TrafficFlowResult(
        vip_name=vip.name,
        destination="%s:%d" % (vip.destination_address, vip.destination_port),
        protocol=(vip.ip_protocol or "tcp").upper(),
        pool_name=pool.name if pool else None,
        load_balancing_method=lb_method or "round-robin",
        load_balancing_is_simulated_as_round_robin=is_simulated_rr,
        persistence=vip.persistence,
        snat_type=vip.snat_type,
        monitors=pool.monitor_names if pool else vip.monitor_names,
        members=members,
        simulated_requests=simulated_requests,
        note=" ".join(note_parts),
    )
