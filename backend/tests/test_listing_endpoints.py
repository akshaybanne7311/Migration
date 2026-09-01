def test_list_vips_search_and_pagination(client, ready_session_id: str):
    resp = client.get("/api/v1/sessions/%s/vips" % ready_session_id)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 6
    assert len(body["items"]) == 6

    search = client.get(
        "/api/v1/sessions/%s/vips" % ready_session_id, params={"search": "MNP"}
    ).json()
    assert search["total"] == 3
    assert all("MNP" in v["name"] for v in search["items"])


def test_vip_detail_shows_real_pool_members_never_empty_when_source_has_them(
    client, ready_session_id: str
):
    detail = client.get(
        "/api/v1/sessions/%s/vips/detail" % ready_session_id,
        params={"name": "/Common/VS-MNP-BL-SIP-5060-IPv6"},
    )
    assert detail.status_code == 200
    vip = detail.json()
    assert vip["destination_address"] == "2405:200:642:a699::76"
    assert vip["destination_port"] == 5060
    assert vip["pool_name"] == "/Common/TEST_POOL-JIO-MNP-BL-SIP-5060-IPv6"

    pool = client.get(
        "/api/v1/sessions/%s/pools/detail" % ready_session_id,
        params={"name": vip["pool_name"]},
    ).json()
    assert len(pool["members"]) == 5
    ipv6_addresses = {
        "2405:200:642:a699:22:0:25:1",
        "2405:200:642:a699:22:0:25:2",
        "2405:200:642:a699:22:0:25:3",
        "2405:200:642:a699:22:0:25:4",
        "2405:200:642:a699:22:0:25:5",
    }
    node_names = [m["node_name"] for m in pool["members"]]
    nodes = client.get("/api/v1/sessions/%s/nodes" % ready_session_id).json()["items"]
    nodes_by_name = {n["name"]: n for n in nodes}
    resolved_addresses = {nodes_by_name[n]["address"] for n in node_names}
    assert resolved_addresses == ipv6_addresses


def test_list_pools_with_members_hydrated(client, ready_session_id: str):
    resp = client.get("/api/v1/sessions/%s/pools" % ready_session_id)
    body = resp.json()
    assert body["total"] == 4
    web_pool_1 = next(
        p for p in body["items"] if p["name"] == "/Common/WEB-POOL-1"
    )
    assert len(web_pool_1["members"]) == 3


def test_list_nodes(client, ready_session_id: str):
    resp = client.get("/api/v1/sessions/%s/nodes" % ready_session_id)
    body = resp.json()
    assert body["total"] == 8
    shared = next(n for n in body["items"] if n["name"] == "/Common/MNP-Node-1")
    assert shared["pool_count"] == 2
    # 3 VIPs reference MNP-Node-1: 5060, 5070, and 5061-IPv6-RD (which
    # reuses the 5060 pool in the fixture).
    assert shared["vip_count"] == 3


def test_list_vlans(client, ready_session_id: str):
    resp = client.get("/api/v1/sessions/%s/vlans" % ready_session_id)
    body = resp.json()
    assert body["total"] == 2
    names = {v["name"] for v in body["items"]}
    assert names == {"/Common/MNP-VLAN-1699", "/Common/WEB-VLAN-200"}
