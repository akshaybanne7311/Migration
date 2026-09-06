from app.models.change_set import MigrationPlan


def _create_and_validate(client, session_id, plan: MigrationPlan):
    resp = client.post("/api/v1/sessions/%s/migration-plans" % session_id, json=plan.model_dump())
    plan_id = resp.json()["id"]
    client.post("/api/v1/sessions/%s/migration-plans/%s/validate" % (session_id, plan_id))
    return plan_id


def test_simulate_full_recreate_of_real_fixture_vip_passes(client, ready_session_id: str, session_maps):
    vip_name = "/Common/VS-WEB-HTTP-80"
    plan = MigrationPlan(session_id=ready_session_id, selected_vips=[vip_name], output_mode="full_recreate")
    plan_id = _create_and_validate(client, ready_session_id, plan)

    resp = client.post("/api/v1/sessions/%s/migration-plans/%s/simulate" % (ready_session_id, plan_id))
    assert resp.status_code == 200
    body = resp.json()
    assert body["output_mode"] == "full_recreate"
    sim = body["simulation"]
    assert sim["total"] > 0
    assert sim["overall"] == "PASS", sim


def test_simulate_changes_only_seeds_existing_objects_so_patches_succeed(client, ready_session_id: str):
    vip_name = "/Common/VS-WEB-HTTP-80"
    plan = MigrationPlan(
        session_id=ready_session_id,
        selected_vips=[vip_name],
        common_changes=[{"change_type": "monitor", "payload": {"new_monitor": "/Common/WEB-HTTP-Monitor"}}],
        output_mode="changes_only",
    )
    plan_id = _create_and_validate(client, ready_session_id, plan)

    resp = client.post("/api/v1/sessions/%s/migration-plans/%s/simulate" % (ready_session_id, plan_id))
    assert resp.status_code == 200
    sim = resp.json()["simulation"]
    # PATCH targets are real, already-existing objects in this session --
    # the changes_only seed must make them resolve, not fail as "not found"
    assert all(s["outcome"] == "ok" for s in sim["steps"]), sim["steps"]
