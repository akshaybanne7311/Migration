"""Generates real network-layer tmsh `create` commands -- VLANs, self IPs
(including floating self IPs on a shared traffic-group), route domains,
and static routes -- for the VLANs actually referenced by the selected
VIPs of a migration plan.

Gap this closes: `MigrationPlan.create_network_objects` already existed
and changed *validation* strictness (see
app/validation/checks/vlan_refs.py -- an unresolved VLAN reference is
BLOCKED instead of WARN when this is set), but nothing ever generated the
network objects it implies. The LTM generators (tmsh/rest/as3) only ever
emit monitors/nodes/pools/virtuals -- standing those up on a brand new
device with no VLANs/self-IPs/routes leaves the migrated virtuals with no
network layer to actually pass traffic on.

Self IPs, route domains, and routes are serialized generically straight
from their parsed entries_json: those keys were captured verbatim from
bigip_base.conf by the tokenizer, so they already ARE real tmsh property
names (address, vlan, traffic-group, allow-service, gw, network, id,
vlans) -- no need to hand-map each field. VLANs get dedicated handling
because their real `interfaces` shape is a nested dict (interface ->
[tagged|untagged]) that wouldn't round-trip through that generic path.

Scope decision: static routes are emitted whenever any are present and
create_network_objects is set, not filtered to the selected VLANs --
routes carry a gateway and destination network, not a VLAN reference, so
there's no reliable way to scope them to "only the ones this migration
needs" from the parsed data. Real device routing tables are typically
small; including all of them is safer than a migrated VIP working but
its return traffic having nowhere to go.
"""
import json
from typing import Any, Dict, Iterable, List, Set

from app.generation.rest_generator import RestCall
from app.models.domain import SystemObject, Vlan


def _parse(json_str: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(json_str)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _tmsh_value(value: Any) -> str:
    if isinstance(value, list):
        return "{ %s }" % " ".join(str(v) for v in value)
    return str(value)


def _generic_create(obj_type: str, name: str, entries: Dict[str, Any], skip: Iterable[str] = ()) -> str:
    """Renders `tmsh create <type> <name> <field> <value> ...` straight
    from a parsed entries dict -- skips nested dict values (none of net
    self/route/route-domain's real fields are nested, but this guards
    against emitting malformed syntax if a future object type has one)."""
    skip_set = set(skip)
    parts = ["tmsh create", obj_type, name]
    for key, value in entries.items():
        if key in skip_set or value is None or isinstance(value, dict):
            continue
        parts.append(key)
        parts.append(_tmsh_value(value))
    return " ".join(parts)


def _render_vlan_create(vlan: Vlan) -> str:
    entries = _parse(vlan.source_stanza_json)
    body: List[str] = []
    if vlan.tag is not None:
        body.append("tag %d" % vlan.tag)
    interfaces = entries.get("interfaces")
    iface_parts: List[str] = []
    if isinstance(interfaces, dict) and interfaces:
        for iface, modes in interfaces.items():
            mode = None
            if isinstance(modes, list):
                if "tagged" in modes:
                    mode = "tagged"
                elif "untagged" in modes:
                    mode = "untagged"
            iface_parts.append("%s { %s }" % (iface, mode) if mode else "%s { }" % iface)
    elif vlan.interfaces:
        iface_parts = ["%s { }" % i for i in vlan.interfaces]
    if iface_parts:
        body.append("interfaces { %s }" % " ".join(iface_parts))
    if body:
        return "tmsh create net vlan %s { %s }" % (vlan.name, " ".join(body))
    return "tmsh create net vlan %s" % vlan.name


def generate_network_tmsh(
    vlan_names: Set[str],
    vlans_by_name: Dict[str, Vlan],
    system_objects: List[SystemObject],
) -> str:
    """`vlan_names` is the resolved set of VLAN names actually referenced
    by the selected VIPs (post any VLAN change in the plan) -- VLANs and
    self IPs are scoped to exactly that set, not the whole device."""
    lines: List[str] = []

    for name in sorted(vlan_names):
        vlan = vlans_by_name.get(name)
        if vlan is not None:
            lines.append(_render_vlan_create(vlan))

    self_ips = sorted(
        (o for o in system_objects if o.object_type == "net self" and _parse(o.entries_json).get("vlan") in vlan_names),
        key=lambda o: o.name,
    )
    for o in self_ips:
        lines.append(_generic_create("net self", o.name, _parse(o.entries_json)))

    route_domains = sorted(
        (
            o
            for o in system_objects
            if o.object_type == "net route-domain" and any(v in vlan_names for v in (_parse(o.entries_json).get("vlans") or []))
        ),
        key=lambda o: o.name,
    )
    for o in route_domains:
        entries = _parse(o.entries_json)
        # The real route-domain's vlans list is device-wide; this migration
        # only creates the subset of VLANs the selected VIPs actually use
        # (by design -- see the module docstring). Referencing a VLAN this
        # run never creates would fail against a real device (caught by
        # app/simulation/mock_bigip.py during development), so the vlans
        # list is trimmed to exactly what's actually being created here.
        entries["vlans"] = [v for v in (entries.get("vlans") or []) if v in vlan_names]
        lines.append(_generic_create("net route-domain", o.name, entries))

    routes = sorted((o for o in system_objects if o.object_type == "net route"), key=lambda o: o.name)
    for o in routes:
        lines.append(_generic_create("net route", o.name, _parse(o.entries_json), skip=("description",)))

    return "\n".join(lines) + ("\n" if lines else "")


# iControl REST uses camelCase field names where tmsh uses kebab-case for
# the same property -- this is the same translation rest_generator.py
# already does by hand for ipProtocol/vlansEnabled; kept as a small map
# here since self-IP/route-domain fields are read generically rather than
# named individually.
_REST_KEY_MAP = {"traffic-group": "trafficGroup", "allow-service": "allowService"}


def _rest_body(entries: Dict[str, Any], name: str, skip: Iterable[str] = ()) -> Dict[str, Any]:
    skip_set = set(skip)
    body: Dict[str, Any] = {"name": name}
    for key, value in entries.items():
        if key in skip_set or value is None or isinstance(value, dict):
            continue
        body[_REST_KEY_MAP.get(key, key)] = value
    return body


def generate_network_rest(
    vlan_names: Set[str],
    vlans_by_name: Dict[str, Vlan],
    system_objects: List[SystemObject],
) -> List[RestCall]:
    calls: List[RestCall] = []

    for name in sorted(vlan_names):
        vlan = vlans_by_name.get(name)
        if vlan is None:
            continue
        entries = _parse(vlan.source_stanza_json)
        interfaces = entries.get("interfaces")
        iface_list = []
        if isinstance(interfaces, dict):
            for iface, modes in interfaces.items():
                tagged = isinstance(modes, list) and "tagged" in modes
                iface_list.append({"name": iface, "tagged": tagged})
        body: Dict[str, Any] = {"name": name}
        if vlan.tag is not None:
            body["tag"] = vlan.tag
        if iface_list:
            body["interfaces"] = iface_list
        calls.append(RestCall(method="POST", path="/mgmt/tm/net/vlan", body=body))

    self_ips = sorted(
        (o for o in system_objects if o.object_type == "net self" and _parse(o.entries_json).get("vlan") in vlan_names),
        key=lambda o: o.name,
    )
    for o in self_ips:
        calls.append(RestCall(method="POST", path="/mgmt/tm/net/self", body=_rest_body(_parse(o.entries_json), o.name)))

    route_domains = sorted(
        (
            o
            for o in system_objects
            if o.object_type == "net route-domain" and any(v in vlan_names for v in (_parse(o.entries_json).get("vlans") or []))
        ),
        key=lambda o: o.name,
    )
    for o in route_domains:
        entries = _parse(o.entries_json)
        entries["vlans"] = [v for v in (entries.get("vlans") or []) if v in vlan_names]  # see tmsh generator for why
        calls.append(RestCall(method="POST", path="/mgmt/tm/net/route-domain", body=_rest_body(entries, o.name)))

    routes = sorted((o for o in system_objects if o.object_type == "net route"), key=lambda o: o.name)
    for o in routes:
        calls.append(RestCall(method="POST", path="/mgmt/tm/net/route", body=_rest_body(_parse(o.entries_json), o.name, skip=("description",))))

    return calls
