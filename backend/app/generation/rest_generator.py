"""Renders the same MigrationContext as a list of iControl REST calls, in
the same Node -> Pool -> Vip order as the TMSH generator, so the two
outputs can never disagree about what's being changed.
"""
from typing import Any, Dict, List

from pydantic import BaseModel

from app.generation.emit_order import MigrationContext
from app.models.domain import Vip


class RestCall(BaseModel):
    method: str
    path: str
    body: Dict[str, Any]


def _rest_encode(name: str) -> str:
    return name.replace("/", "~")


def generate_rest(context: MigrationContext, vips_by_name: Dict[str, Vip]) -> List[RestCall]:
    calls: List[RestCall] = []

    for rnc in context.new_nodes.values():
        calls.append(
            RestCall(
                method="POST",
                path="/mgmt/tm/ltm/node",
                body={"name": rnc.new_node_name, "address": rnc.new_address},
            )
        )

    for pool_name, members in context.pool_effective_members.items():
        calls.append(
            RestCall(
                method="PATCH",
                path="/mgmt/tm/ltm/pool/%s" % _rest_encode(pool_name),
                body={"members": [{"name": "%s:%d" % (m.node_name, m.port)} for m in members]},
            )
        )

    for old_name, new_name in context.pool_renames.items():
        calls.append(
            RestCall(
                method="PATCH",
                path="/mgmt/tm/ltm/pool/%s" % _rest_encode(old_name),
                body={"name": new_name},
            )
        )

    for vip_name, effective in context.vip_effective.items():
        if not effective:
            continue
        vip = vips_by_name[vip_name]
        body: Dict[str, Any] = {}

        if "name" in effective and effective["name"] != vip.name:
            body["name"] = effective["name"]
        if "destination_address" in effective or "destination_port" in effective:
            from app.ingest.net_address import format_destination

            address = effective.get("destination_address", vip.destination_address)
            port = effective.get("destination_port", vip.destination_port)
            body["destination"] = "/%s/%s" % (
                vip.partition,
                format_destination(address, port, vip.address_family, vip.route_domain),
            )
        if "pool_name" in effective:
            body["pool"] = effective["pool_name"]
        if "vlans" in effective:
            body["vlans"] = effective["vlans"]
            body["vlansEnabled"] = effective.get("vlans_enabled", True)
        if "persistence" in effective:
            body["persist"] = [{"name": effective["persistence"]}]
        if "monitor_names" in effective:
            body["monitor"] = " and ".join(effective["monitor_names"])
        if "profile_names" in effective:
            body["profiles"] = [{"name": p} for p in effective["profile_names"]]

        if body:
            calls.append(
                RestCall(
                    method="PATCH",
                    path="/mgmt/tm/ltm/virtual/%s" % _rest_encode(vip.name),
                    body=body,
                )
            )

    for node_name in context.node_deletions:
        calls.append(
            RestCall(method="DELETE", path="/mgmt/tm/ltm/node/%s" % _rest_encode(node_name), body={})
        )

    return calls
