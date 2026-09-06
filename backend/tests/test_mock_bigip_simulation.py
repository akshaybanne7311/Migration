from app.generation.rest_generator import RestCall
from app.simulation.mock_bigip import simulate


def test_well_ordered_full_recreate_calls_all_succeed():
    calls = [
        RestCall(method="POST", path="/mgmt/tm/ltm/monitor/http", body={"name": "/Common/mon1"}),
        RestCall(method="POST", path="/mgmt/tm/ltm/node", body={"name": "/Common/n1", "address": "10.0.0.1"}),
        RestCall(method="POST", path="/mgmt/tm/ltm/pool", body={"name": "/Common/p1", "members": [{"name": "/Common/n1:80"}], "monitor": "/Common/mon1"}),
        RestCall(method="POST", path="/mgmt/tm/ltm/virtual", body={"name": "/Common/v1", "destination": "/Common/1.2.3.4:80", "pool": "/Common/p1"}),
    ]
    result = simulate(calls)
    assert result.overall == "PASS"
    assert result.succeeded == 4
    assert result.failed == 0


def test_pool_referencing_a_node_that_was_never_created_fails():
    calls = [
        RestCall(method="POST", path="/mgmt/tm/ltm/pool", body={"name": "/Common/p1", "members": [{"name": "/Common/ghost-node:80"}]}),
    ]
    result = simulate(calls)
    assert result.overall == "FAILED"
    assert "ghost-node" in result.steps[0].message


def test_virtual_referencing_a_pool_created_out_of_order_fails():
    calls = [
        RestCall(method="POST", path="/mgmt/tm/ltm/virtual", body={"name": "/Common/v1", "destination": "/Common/1.2.3.4:80", "pool": "/Common/p1"}),
        RestCall(method="POST", path="/mgmt/tm/ltm/pool", body={"name": "/Common/p1", "members": []}),
    ]
    result = simulate(calls)
    assert result.steps[0].outcome == "error"
    assert "p1" in result.steps[0].message
    assert result.steps[1].outcome == "ok"  # the pool itself has no missing deps


def test_duplicate_create_is_flagged():
    calls = [
        RestCall(method="POST", path="/mgmt/tm/ltm/node", body={"name": "/Common/n1", "address": "10.0.0.1"}),
        RestCall(method="POST", path="/mgmt/tm/ltm/node", body={"name": "/Common/n1", "address": "10.0.0.1"}),
    ]
    result = simulate(calls)
    assert result.steps[0].outcome == "ok"
    assert result.steps[1].outcome == "error"
    assert "duplicate" in result.steps[1].message


def test_patch_against_seeded_existing_object_succeeds():
    seed = {"ltm/pool": {"/Common/p1": {}}}
    calls = [RestCall(method="PATCH", path="/mgmt/tm/ltm/pool/~Common~p1", body={"members": []})]
    result = simulate(calls, seed=seed)
    assert result.overall == "PASS"


def test_patch_against_object_that_was_never_seeded_or_created_fails():
    calls = [RestCall(method="PATCH", path="/mgmt/tm/ltm/pool/~Common~never-existed", body={"members": []})]
    result = simulate(calls)
    assert result.overall == "FAILED"
    assert "not found" in result.steps[0].message


def test_self_ip_referencing_vlan_created_earlier_succeeds():
    calls = [
        RestCall(method="POST", path="/mgmt/tm/net/vlan", body={"name": "/Common/vlan1", "tag": 100}),
        RestCall(method="POST", path="/mgmt/tm/net/self", body={"name": "/Common/self1", "address": "10.0.0.1/24", "vlan": "/Common/vlan1"}),
    ]
    result = simulate(calls)
    assert result.overall == "PASS"


def test_self_ip_referencing_missing_vlan_fails():
    calls = [RestCall(method="POST", path="/mgmt/tm/net/self", body={"name": "/Common/self1", "address": "10.0.0.1/24", "vlan": "/Common/never-created"})]
    result = simulate(calls)
    assert result.overall == "FAILED"
    assert "never-created" in result.steps[0].message


def test_empty_call_list_is_a_trivial_pass():
    result = simulate([])
    assert result.overall == "PASS"
    assert result.total == 0
