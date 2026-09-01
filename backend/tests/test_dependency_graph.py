from app.graph.builder import build_dependency_graph
from app.storage import session_db


def test_shared_node_appears_once_in_graph_and_listing(client, ready_session_id: str):
    conn = session_db.open_session_conn(ready_session_id)
    graph = build_dependency_graph(conn)
    # exactly one graph node for the shared MNP-Node-1, regardless of how
    # many pools/VIPs reference it.
    assert ("node", "/Common/MNP-Node-1") in graph.g
    assert len([n for n in graph.g.nodes if n == ("node", "/Common/MNP-Node-1")]) == 1

    pools = graph.pools_using_node("/Common/MNP-Node-1")
    assert set(pools) == {
        "/Common/TEST_POOL-JIO-MNP-BL-SIP-5060-IPv6",
        "/Common/TEST_POOL-JIO-MNP-BL-SIP-5070-IPv6",
    }
    vips = graph.vips_using_node("/Common/MNP-Node-1")
    # VS-MNP-BL-SIP-5061-IPv6-RD also reuses the 5060 pool in the fixture.
    assert set(vips) == {
        "/Common/VS-MNP-BL-SIP-5060-IPv6",
        "/Common/VS-MNP-BL-SIP-5070-IPv6",
        "/Common/VS-MNP-BL-SIP-5061-IPv6-RD",
    }


def test_selection_counts_are_deduped_not_a_naive_sum(client, ready_session_id: str):
    conn = session_db.open_session_conn(ready_session_id)
    graph = build_dependency_graph(conn)

    counts = graph.counts_for_selection(
        [
            "/Common/VS-MNP-BL-SIP-5060-IPv6",
            "/Common/VS-MNP-BL-SIP-5070-IPv6",
            "/Common/VS-MNP-BL-SIP-5061-IPv6-RD",
        ]
    )
    assert counts.vips == 3
    # 5060 and 5061-RD both use the same pool -> 2 distinct pools, not 3
    assert counts.pools == 2
    # nodes: pool-5060 has 5 members, pool-5070 has 2 (MNP-Node-1, MNP-Node-2,
    # both already counted) -> 5 distinct nodes total, not 7
    assert counts.nodes == 5


def test_selection_kpi_endpoint_matches_graph(client, ready_session_id: str):
    resp = client.post(
        "/api/v1/sessions/%s/vips/kpis" % ready_session_id,
        json={
            "vip_names": [
                "/Common/VS-WEB-HTTP-80",
                "/Common/VS-WEB-HTTP-8080",
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["vips"] == 2
    assert body["pools"] == 2
    # WEB-Node-1 is shared by WEB-POOL-1 and WEB-POOL-2, WEB-Node-2 and the
    # orphan 10.20.30.99 node are only in WEB-POOL-1 -> 3 distinct nodes.
    assert body["nodes"] == 3


def test_selecting_all_vips_is_pure_selection_not_all_changes(client, ready_session_id: str):
    all_vips = client.get("/api/v1/sessions/%s/vips" % ready_session_id).json()["items"]
    names = [v["name"] for v in all_vips]
    resp = client.post(
        "/api/v1/sessions/%s/vips/kpis" % ready_session_id, json={"vip_names": names}
    )
    body = resp.json()
    assert body["vips"] == 6
    # this endpoint only ever returns counts -- it carries no "changes"
    # field, which is the structural guarantee that selecting all VIPs
    # cannot be misread as "apply changes to all VIPs".
    assert set(body.keys()) == {"vips", "pools", "pool_members", "nodes", "vlan_refs"}
