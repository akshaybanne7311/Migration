"""Regression test for a real bug the mock BIG-IP simulator caught during
development: a route-domain's real vlans list is device-wide, but VLAN
creation is scoped to only the VLANs the selected VIPs use -- so the
route-domain create referenced VLANs this migration never creates. Caught
by running the actual simulator against real device data, not by
inspection.
"""
import json

from app.generation.network_generator import generate_network_rest, generate_network_tmsh
from app.models.domain import SystemObject, Vlan
from app.simulation.mock_bigip import simulate


def test_route_domain_with_partially_out_of_scope_vlans_still_simulates_clean():
    in_scope_vlan = Vlan(
        name="/Common/in-scope-vlan",
        tag=100,
        interfaces=["iface1"],
        source_stanza_json=json.dumps({"tag": "100", "interfaces": {"iface1": ["tagged"]}}),
    )
    route_domain = SystemObject(
        object_type="net route-domain",
        name="/Common/0",
        entries_json=json.dumps(
            {
                "id": "0",
                # real device: this route-domain spans several VLANs, only
                # one of which is in scope for this migration
                "vlans": ["/Common/in-scope-vlan", "/Common/out-of-scope-vlan-1", "/Common/out-of-scope-vlan-2"],
            }
        ),
    )

    vlan_names = {in_scope_vlan.name}
    tmsh = generate_network_tmsh(vlan_names, {in_scope_vlan.name: in_scope_vlan}, [route_domain])
    assert "out-of-scope" not in tmsh

    rest_calls = generate_network_rest(vlan_names, {in_scope_vlan.name: in_scope_vlan}, [route_domain])
    result = simulate(rest_calls)
    assert result.overall == "PASS", result.steps
