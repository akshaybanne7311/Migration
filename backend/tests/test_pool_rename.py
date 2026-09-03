from app.generation.as3_generator import generate_as3
from app.generation.emit_order import build_migration_context
from app.generation.rest_generator import generate_rest
from app.generation.tmsh_generator import generate_tmsh
from app.migration.change_engine import ChangeEngineError, resolve
from app.models.change_set import ChangeType, CommonChange, MigrationPlan, VipException


def _resolve_and_build(session_maps, plan: MigrationPlan):
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
    return resolved, context


def test_pool_rename_produces_mv_command_and_updated_vip_pointer(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        exceptions=[
            VipException(
                vip_name="/Common/VS-WEB-HTTP-80",
                overrides={
                    ChangeType.POOL_NAME: {
                        "find": "/Common/WEB-POOL-1",
                        "replace": "/Common/WEB-POOL-1-NEW",
                    }
                },
            )
        ],
    )
    resolved, context = _resolve_and_build(session_maps, plan)
    assert resolved.pool_renames == {"/Common/WEB-POOL-1": "/Common/WEB-POOL-1-NEW"}

    tmsh = generate_tmsh(context, session_maps["vips_by_name"])
    assert "tmsh mv ltm pool /Common/WEB-POOL-1 /Common/WEB-POOL-1-NEW" in tmsh
    assert "tmsh modify ltm virtual /Common/VS-WEB-HTTP-80 pool /Common/WEB-POOL-1-NEW" in tmsh
    # rename must come after any member modification, before the VIP is repointed
    lines = [l for l in tmsh.splitlines() if l.strip()]
    mv_idx = next(i for i, l in enumerate(lines) if l.startswith("tmsh mv ltm pool"))
    vip_idx = next(i for i, l in enumerate(lines) if l.startswith("tmsh modify ltm virtual"))
    assert mv_idx < vip_idx


def test_pool_rename_rest_call_patches_name(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        exceptions=[
            VipException(
                vip_name="/Common/VS-WEB-HTTP-80",
                overrides={
                    ChangeType.POOL_NAME: {
                        "find": "/Common/WEB-POOL-1",
                        "replace": "/Common/WEB-POOL-1-NEW",
                    }
                },
            )
        ],
    )
    _resolved, context = _resolve_and_build(session_maps, plan)
    calls = generate_rest(context, session_maps["vips_by_name"])
    rename_calls = [c for c in calls if c.body.get("name") == "/Common/WEB-POOL-1-NEW"]
    assert len(rename_calls) == 1
    assert rename_calls[0].method == "PATCH"
    assert "WEB-POOL-1" in rename_calls[0].path


def test_pool_rename_validates_ready_not_blocked(session_maps):
    from app.validation.context import ValidationInput
    from app.validation.validator import run_validation

    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        exceptions=[
            VipException(
                vip_name="/Common/VS-WEB-HTTP-80",
                overrides={
                    ChangeType.POOL_NAME: {
                        "find": "/Common/WEB-POOL-1",
                        "replace": "/Common/WEB-POOL-1-NEW",
                    }
                },
            )
        ],
    )
    resolved, context = _resolve_and_build(session_maps, plan)
    vi = ValidationInput(
        resolved=resolved,
        context=context,
        nodes_by_name=session_maps["nodes_by_name"],
        pools_by_name=session_maps["pools_by_name"],
        vips_by_name=session_maps["vips_by_name"],
        vlans_by_name=session_maps["vlans_by_name"],
    )
    result = run_validation(vi)
    assert result.overall == "READY", [c for c in result.checks if c.severity != "pass"]


def test_conflicting_pool_renames_blocked(session_maps):
    # VS-MNP-BL-SIP-5060-IPv6 and VS-MNP-BL-SIP-5061-IPv6-RD share the same
    # pool in the fixture; giving them different rename targets must be
    # rejected rather than silently picking one.
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-MNP-BL-SIP-5060-IPv6", "/Common/VS-MNP-BL-SIP-5061-IPv6-RD"],
        exceptions=[
            VipException(
                vip_name="/Common/VS-MNP-BL-SIP-5060-IPv6",
                overrides={
                    ChangeType.POOL_NAME: {
                        "find": "/Common/TEST_POOL-JIO-MNP-BL-SIP-5060-IPv6",
                        "replace": "/Common/POOL-A",
                    }
                },
            ),
            VipException(
                vip_name="/Common/VS-MNP-BL-SIP-5061-IPv6-RD",
                overrides={
                    ChangeType.POOL_NAME: {
                        "find": "/Common/TEST_POOL-JIO-MNP-BL-SIP-5060-IPv6",
                        "replace": "/Common/POOL-B",
                    }
                },
            ),
        ],
    )
    try:
        resolve(
            plan,
            session_maps["nodes_by_name"],
            session_maps["pools_by_name"],
            session_maps["vips_by_name"],
            session_maps["graph"],
        )
        assert False, "expected ChangeEngineError"
    except ChangeEngineError as exc:
        assert "conflicting pool renames" in str(exc)


def test_as3_untouched_pool_keeps_real_members_not_empty(session_maps):
    """Regression: AS3 is a full-state declaration. A pool this migration
    never edited must still carry its real current members in the
    declaration -- an empty members list here would delete production
    pool members when the declaration is applied.
    """
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        common_changes=[
            CommonChange(change_type=ChangeType.MONITOR, payload={"new_monitor": "/Common/WEB-HTTP-Monitor-New"})
        ],
    )
    resolved, context = _resolve_and_build(session_maps, plan)
    output = generate_as3(
        context, session_maps["vips_by_name"], session_maps["pools_by_name"], session_maps["nodes_by_name"]
    )
    pool_obj = output["declaration"]["Tenant_Migration"]["VS-WEB-HTTP-80"]["WEB-POOL-1_pool"]
    assert len(pool_obj["members"]) > 0
