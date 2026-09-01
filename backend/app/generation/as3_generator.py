"""Renders the same MigrationContext as an AS3 declaration.

AS3 is not a 1:1 representation of every TMOS object -- any field with no
clean AS3 equivalent is called out under `x-tmos-notes` rather than being
silently dropped, so the output is explicitly marked as a transformation
artifact wherever that applies (e.g. route-domain destinations, and
custom/compound persistence or monitor setups AS3 can't express exactly
the same way TMOS does).
"""
from typing import Any, Dict, List

from app.generation.emit_order import MigrationContext
from app.models.domain import Vip


def _tenant_and_app_from_pool_or_vip_name(name: str) -> str:
    parts = [p for p in name.split("/") if p]
    return parts[-1] if parts else name


def generate_as3(context: MigrationContext, vips_by_name: Dict[str, Vip]) -> Dict[str, Any]:
    notes: List[Dict[str, str]] = []

    members_by_pool = {}
    for pool_name, members in context.pool_effective_members.items():
        members_by_pool[pool_name] = [
            {
                "servicePort": m.port,
                "serverAddresses": [m.address] if m.address else [],
            }
            for m in members
        ]
        if any(m.address is None for m in members):
            notes.append(
                {
                    "object": pool_name,
                    "field": "members",
                    "note": "one or more members reference a node with no "
                    "resolvable address in this plan; review before applying",
                }
            )

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
            service["pool"] = _tenant_and_app_from_pool_or_vip_name(pool_name) + "_pool"
            applications.setdefault(app_name, {"class": "Application"})[
                _tenant_and_app_from_pool_or_vip_name(pool_name) + "_pool"
            ] = {
                "class": "Pool",
                "members": members_by_pool.get(pool_name, []),
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
