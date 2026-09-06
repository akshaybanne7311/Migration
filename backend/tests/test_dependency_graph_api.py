def test_dependency_graph_for_real_fixture_vip(client, ready_session_id: str):
    vips_resp = client.get("/api/v1/sessions/%s/vips" % ready_session_id).json()
    vip_with_pool = next(v for v in vips_resp["items"] if v["pool_name"])

    resp = client.get(
        "/api/v1/sessions/%s/dependency-graph" % ready_session_id, params={"vip": vip_with_pool["name"]}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["vip"]["name"] == vip_with_pool["name"]
    assert body["vip"]["type"] == "vip"
    assert any(p["name"] == vip_with_pool["pool_name"] for p in body["pools"])
    assert all(n["type"] == "node" for n in body["nodes"])
    if body["nodes"]:
        assert body["nodes"][0]["attrs"].get("port") is not None


def test_dependency_graph_404_for_unknown_vip(client, ready_session_id: str):
    resp = client.get(
        "/api/v1/sessions/%s/dependency-graph" % ready_session_id, params={"vip": "/Common/does-not-exist"}
    )
    assert resp.status_code == 404
