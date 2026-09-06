def test_traffic_flow_for_real_fixture_vip_with_pool(client, ready_session_id: str):
    vips_resp = client.get("/api/v1/sessions/%s/vips" % ready_session_id).json()
    vip_with_pool = next(v for v in vips_resp["items"] if v["pool_name"])

    resp = client.get(
        "/api/v1/sessions/%s/traffic-flow" % ready_session_id,
        params={"vip": vip_with_pool["name"], "requests": 8},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["vip_name"] == vip_with_pool["name"]
    assert body["pool_name"] == vip_with_pool["pool_name"]
    assert body["destination"] == "%s:%d" % (vip_with_pool["destination_address"], vip_with_pool["destination_port"])
    assert len(body["simulated_requests"]) <= 8
    assert isinstance(body["note"], str) and body["note"]


def test_traffic_flow_404_for_unknown_vip(client, ready_session_id: str):
    resp = client.get(
        "/api/v1/sessions/%s/traffic-flow" % ready_session_id, params={"vip": "/Common/does-not-exist"}
    )
    assert resp.status_code == 404
