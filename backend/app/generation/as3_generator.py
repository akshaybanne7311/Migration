"""Renders the same MigrationContext as an AS3 declaration.

AS3 is not a 1:1 representation of every TMOS object -- any field with no
clean AS3 equivalent is called out under `x-tmos-notes` rather than being
silently dropped, so the output is explicitly marked as a transformation
artifact wherever that applies (e.g. route-domain destinations, and
custom/compound persistence or monitor setups AS3 can't express exactly
the same way TMOS does).
"""
from typing import Any, Dict, List, Optional

from app.generation.emit_order import MigrationContext
from app.models.domain import Node, Pool, Vip


def _tenant_and_app_from_pool_or_vip_name(name: str) -> str:
    parts = [p for p in name.split("/") if p]
    return parts[-1] if parts else name


def generate_as3(
    context: MigrationContext,
    vips_by_name: Dict[str, Vip],
    pools_by_name: Optional[Dict[str, Pool]] = None,
    nodes_by_name: Optional[Dict[str, Node]] = None,
) -> Dict[str, Any]:
    notes: List[Dict[str, str]] = []
    pools_by_name = pools_by_name or {}
    nodes_by_name = nodes_by_name or {}

    def _as3_members(pool_name: str, addr_port_pairs: List[tuple]) -> List[Dict[str, Any]]:
        out = [
            {"servicePort": port, "serverAddresses": [address] if address else []}
            for address, port in addr_port_pairs
        ]
        if any(address is None for address, _port in addr_port_pairs):
            notes.append(
                {
                    "object": pool_name,
                    "field": "members",
                    "note": "one or more members reference a node with no "
                    "resolvable address in this plan; review before applying",
                }
            )
        return out

    members_by_pool = {}
    for pool_name, members in context.pool_effective_members.items():
        members_by_pool[pool_name] = _as3_members(pool_name, [(m.address, m.port) for m in members])

    # AS3 is a full-state declaration, not a diff of commands -- a pool
    # this migration never touched still has to appear with its real,
    # current members here. Without this, any pool not directly edited by
    # the plan came out as an empty Pool object, and applying that
    # declaration to a real device would delete its production members.
    for pool_name, pool in pools_by_name.items():
        if pool_name in members_by_pool:
            continue
        members_by_pool[pool_name] = _as3_members(
            pool_name,
            [
                (nodes_by_name[m.node_name].address if m.node_name in nodes_by_name else None, m.port)
                for m in pool.members
            ],
        )

    new_to_old_pool = {new: old for old, new in context.pool_renames.items()}

    applications: Dict[str, Any] = {}
    for vip_name, effective in context.vip_effective.items():
        if not effective:
            continue
        vip = vips_by_name[vip_name]
        app_name = _tenant_and_app_from_pool_or_vip_name(effective.get("name", vip.name))

        service: Dict[str, Any] = {
            "class": "Service_Generic" if vip.ip_protocol != "udp" else "Service_UDP",
            "virtualAddresses": [effective.get("destination_address", vip.destination_address)],
            "virtualPort": effective.get("destination_port", vip.destination_port),
        }
        if vip.route_domain is not None:
            notes.append(
                {
                    "object": vip.name,
                    "field": "route_domain",
                    "note": "AS3 does not model TMOS route domains directly; "
                    "route-domain routing must be handled via AS3 Tenant "
                    "/ RouteDomain configuration outside this declaration",
                }
            )
        if vip.persistence or "persistence" in effective:
            notes.append(
                {
                    "object": vip.name,
                    "field": "persistence",
                    "note": "persistence profile mapped by name only; verify "
                    "AS3 persistenceMethods semantics match the source TMOS "
                    "profile configuration",
                }
            )
        if vip.irules:
            notes.append(
                {
                    "object": vip.name,
                    "field": "irules",
                    "note": "iRules are referenced by name in AS3 (iRule "
                    "class) but their logic is not represented in this "
                    "declaration",
                }
            )

        pool_name = effective.get("pool_name", vip.pool_name)
        if pool_name:
            # member lookups are always keyed by the pool's current
            # (pre-rename) name, since that's what the parsed session
            # data and any explicit member edits are keyed by
            member_lookup_name = new_to_old_pool.get(pool_name, pool_name)
            service["pool"] = _tenant_and_app_from_pool_or_vip_name(pool_name) + "_pool"
            applications.setdefault(app_name, {"class": "Application"})[
                _tenant_and_app_from_pool_or_vip_name(pool_name) + "_pool"
            ] = {
                "class": "Pool",
                "members": members_by_pool.get(member_lookup_name, []),
            }

        applications.setdefault(app_name, {"class": "Application"})[app_name] = service

    declaration = {
        "class": "ADC",
        "schemaVersion": "3.0.0",
        "id": "f5-config-intelligence-migration",
        "Tenant_Migration": {"class": "Tenant", **applications},
    }

    return {
        "declaration": declaration,
        "x-tmos-notes": notes,
    }
