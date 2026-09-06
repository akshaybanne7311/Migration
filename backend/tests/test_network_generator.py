import json

from app.generation.network_generator import generate_network_rest, generate_network_tmsh
from app.models.domain import SystemObject, Vlan


def _vlan(name="/Common/JIO-MNP-VLAN-699", tag=699, iface="MNP-VLAN-1699", mode="tagged"):
    stanza = {"tag": str(tag), "interfaces": {iface: [mode]}, "dag-adjustment": "none"}
    return Vlan(name=name, tag=tag, interfaces=[iface], source_stanza_json=json.dumps(stanza))


def _self_ip(name, address, vlan, traffic_group="/Common/traffic-group-local-only", allow_service=None):
    entries = {"address": address, "vlan": vlan, "traffic-group": traffic_group}
    if allow_service is not None:
        entries["allow-service"] = allow_service
    return SystemObject(object_type="net self", name=name, entries_json=json.dumps(entries))


def test_vlan_and_matching_self_ips_are_emitted_as_real_tmsh():
    vlan = _vlan()
    floating = _self_ip("/Common/JIO-MNP-FLOATING-IP", "10.55.26.132/29", vlan.name, "/Common/traffic-group-1")
    non_floating = _self_ip("/Common/JIO-MNP-SELF-IP", "10.55.26.134/29", vlan.name)
    unrelated = _self_ip("/Common/OTHER-SELF-IP", "10.1.1.1/24", "/Common/some-other-vlan")

    tmsh = generate_network_tmsh({vlan.name}, {vlan.name: vlan}, [floating, non_floating, unrelated])

    assert "tmsh create net vlan /Common/JIO-MNP-VLAN-699 { tag 699 interfaces { MNP-VLAN-1699 { tagged } } }" in tmsh
    assert "tmsh create net self /Common/JIO-MNP-FLOATING-IP address 10.55.26.132/29 vlan /Common/JIO-MNP-VLAN-699 traffic-group /Common/traffic-group-1" in tmsh
    assert "tmsh create net self /Common/JIO-MNP-SELF-IP address 10.55.26.134/29 vlan /Common/JIO-MNP-VLAN-699 traffic-group /Common/traffic-group-local-only" in tmsh
    assert "OTHER-SELF-IP" not in tmsh


def test_self_ip_with_port_lockdown_list_renders_as_brace_list():
    vlan = _vlan()
    ha_self = _self_ip("/Common/HA-MNP", "192.168.1.101/24", vlan.name, allow_service=["tcp:1026", "udp:1026"])
    tmsh = generate_network_tmsh({vlan.name}, {vlan.name: vlan}, [ha_self])
    assert "allow-service { tcp:1026 udp:1026 }" in tmsh


def test_route_domain_included_only_when_it_covers_a_selected_vlan():
    vlan = _vlan()
    rd_covering = SystemObject(
        object_type="net route-domain",
        name="/Common/0",
        entries_json=json.dumps({"id": "0", "vlans": [vlan.name, "/Common/other-vlan"]}),
    )
    rd_unrelated = SystemObject(
        object_type="net route-domain",
        name="/Common/5",
        entries_json=json.dumps({"id": "5", "vlans": ["/Common/totally-different"]}),
    )
    tmsh = generate_network_tmsh({vlan.name}, {vlan.name: vlan}, [rd_covering, rd_unrelated])
    assert "/Common/0" in tmsh
    assert "vlans { %s /Common/other-vlan }" % vlan.name in tmsh
    assert "/Common/5" not in tmsh


def test_static_routes_are_always_included_when_present():
    route = SystemObject(
        object_type="net route",
        name="/Common/Jio_MNP_Route_V4",
        entries_json=json.dumps({"network": "10.55.83.0/27", "gw": "10.55.26.129", "mtu": "1500", "description": "x"}),
    )
    tmsh = generate_network_tmsh(set(), {}, [route])
    assert "tmsh create net route /Common/Jio_MNP_Route_V4 network 10.55.83.0/27 gw 10.55.26.129 mtu 1500" in tmsh
    assert "description" not in tmsh  # explicitly skipped, cosmetic-only field


def test_empty_input_produces_empty_string():
    assert generate_network_tmsh(set(), {}, []) == ""


def test_rest_calls_use_camel_case_fields_and_real_paths():
    vlan = _vlan()
    self_ip = _self_ip("/Common/JIO-MNP-FLOATING-IP", "10.55.26.132/29", vlan.name, "/Common/traffic-group-1")
    calls = generate_network_rest({vlan.name}, {vlan.name: vlan}, [self_ip])

    vlan_call = next(c for c in calls if c.path == "/mgmt/tm/net/vlan")
    assert vlan_call.body["tag"] == 699
    assert vlan_call.body["interfaces"] == [{"name": "MNP-VLAN-1699", "tagged": True}]

    self_call = next(c for c in calls if c.path == "/mgmt/tm/net/self")
    assert self_call.body["trafficGroup"] == "/Common/traffic-group-1"
    assert "traffic-group" not in self_call.body
