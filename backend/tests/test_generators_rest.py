from app.generation.emit_order import build_migration_context
from app.generation.rest_generator import generate_rest
from app.migration.change_engine import resolve
from app.models.change_set import MigrationPlan, NodeChange


def test_rest_calls_cover_all_emit_units(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        node_changes=[NodeChange(old_node_ref="/Common/WEB-Node-1", new_ip="10.20.30.200")],
    )
    resolved = resolve(
        plan,
        session_maps["nodes_by_name"],
        session_maps["pools_by_name"],
        session_maps["vips_by_name"],
        session_maps["graph"],
    )
    context = build_migration_context(
        resolved,
        session_maps["nodes_by_name"],
        session_maps["pools_by_name"],
        session_maps["vips_by_name"],
    )
    calls = generate_rest(context, session_maps["vips_by_name"])

    node_calls = [c for c in calls if c.path == "/mgmt/tm/ltm/node"]
    assert len(node_calls) == 1
    assert node_calls[0].body == {"name": "/Common/WEB-Node-1", "address": "10.20.30.200"}

    # WEB-Node-1 is shared by WEB-POOL-1 and WEB-POOL-2 in the fixture, so
    # the rename cascade correctly touches both pools -- not a duplication
    # bug, this is the dedup-across-pools behavior working as intended.
    pool_calls = [c for c in calls if c.path.startswith("/mgmt/tm/ltm/pool/")]
    assert len(pool_calls) == 2
    assert {c.path for c in pool_calls} == {
        "/mgmt/tm/ltm/pool/~Common~WEB-POOL-1",
        "/mgmt/tm/ltm/pool/~Common~WEB-POOL-2",
    }
    for call in pool_calls:
        assert call.method == "PATCH"
        assert any(m["name"].startswith("/Common/WEB-Node-1:") for m in call.body["members"])
