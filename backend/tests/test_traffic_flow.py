from app.models.domain import Node, Pool, PoolMember, Vip
from app.simulation.traffic_flow import simulate_traffic_flow


def _vip(**overrides):
    defaults = dict(
        name="/Common/vip1",
        partition="Common",
        destination_address="10.0.0.1",
        destination_port=80,
        address_family="ipv4",
        route_domain=None,
        ip_protocol="tcp",
        pool_name="/Common/pool1",
        vlans=[],
        vlans_enabled=True,
        profiles=[],
        persistence=None,
        snat_type=None,
        irules=[],
        mask=None,
        monitor_names=[],
        source_stanza_json="{}",
    )
    defaults.update(overrides)
    return Vip(**defaults)


def _pool_with_members(n=3, disabled_indices=()):
    members = []
    nodes_by_name = {}
    for i in range(n):
        node_name = "/Common/node%d" % i
        members.append(
            PoolMember(
                pool_name="/Common/pool1",
                node_name=node_name,
                port=80,
                session_state="user-disabled" if i in disabled_indices else None,
            )
        )
        nodes_by_name[node_name] = Node(name=node_name, address="10.0.1.%d" % i, address_family="ipv4", partition="Common")
    pool = Pool(name="/Common/pool1", partition="Common", monitor_names=["/Common/mon1"], members=members)
    return pool, nodes_by_name


def test_round_robin_distributes_evenly_across_enabled_members():
    vip = _vip()
    pool, nodes_by_name = _pool_with_members(3)
    result = simulate_traffic_flow(vip, pool, "round-robin", nodes_by_name, request_count=6)
    assert [r.member_name for r in result.simulated_requests] == [
        "/Common/node0",
        "/Common/node1",
        "/Common/node2",
        "/Common/node0",
        "/Common/node1",
        "/Common/node2",
    ]
    assert result.load_balancing_is_simulated_as_round_robin is False


def test_disabled_members_are_skipped_in_the_rotation():
    vip = _vip()
    pool, nodes_by_name = _pool_with_members(3, disabled_indices=(1,))
    result = simulate_traffic_flow(vip, pool, "round-robin", nodes_by_name, request_count=4)
    names = {r.member_name for r in result.simulated_requests}
    assert "/Common/node1" not in names
    assert names == {"/Common/node0", "/Common/node2"}


def test_non_round_robin_method_is_flagged_as_simulated():
    vip = _vip()
    pool, nodes_by_name = _pool_with_members(2)
    result = simulate_traffic_flow(vip, pool, "least-connections-member", nodes_by_name, request_count=2)
    assert result.load_balancing_is_simulated_as_round_robin is True
    assert "least-connections-member" in result.note
    assert result.simulated_requests  # still produces a sequence, just labeled honestly


def test_no_pool_produces_no_requests_and_an_explanatory_note():
    vip = _vip(pool_name=None)
    result = simulate_traffic_flow(vip, None, "round-robin", {}, request_count=5)
    assert result.simulated_requests == []
    assert "no pool assigned" in result.note


def test_all_members_disabled_produces_no_requests():
    vip = _vip()
    pool, nodes_by_name = _pool_with_members(2, disabled_indices=(0, 1))
    result = simulate_traffic_flow(vip, pool, "round-robin", nodes_by_name, request_count=5)
    assert result.simulated_requests == []
    assert "administratively disabled" in result.note
