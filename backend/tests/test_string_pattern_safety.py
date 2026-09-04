"""Regression: an empty `find` on a VIP_NAME/POOL_NAME change must never
fall through to Python's str.replace("", x), which inserts x between
every character of the original string instead of leaving it alone --
str.replace("", "X") on "/Common/VS-A" produces "X/XCXoXmXmXoXnX/..." with
no error and no warning. This is reachable through completely ordinary
UI use: check the VIP Name or Pool Name card, type a Replace value, and
either never type anything into Find or clear it back out.
"""
from app.generation.emit_order import build_migration_context
from app.generation.tmsh_generator import generate_tmsh
from app.migration.change_engine import resolve
from app.models.change_set import ChangeType, CommonChange, MigrationPlan, VipException
from app.validation.context import ValidationInput
from app.validation.validator import run_validation


def _generate(session_maps, plan: MigrationPlan) -> str:
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
    return generate_tmsh(context, session_maps["vips_by_name"])


def test_empty_find_on_vip_name_common_change_is_a_noop(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        common_changes=[
            CommonChange(change_type=ChangeType.VIP_NAME, payload={"find": "", "replace": "MUM"})
        ],
    )
    text = _generate(session_maps, plan)
    assert "MUM" not in text
    assert "tmsh mv ltm virtual" not in text


def test_empty_find_on_vip_name_exception_is_a_noop(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        exceptions=[
            VipException(
                vip_name="/Common/VS-WEB-HTTP-80",
                overrides={ChangeType.VIP_NAME: {"find": "", "replace": "MUM"}},
            )
        ],
    )
    text = _generate(session_maps, plan)
    assert "MUM" not in text


def test_empty_find_on_pool_name_change_is_a_noop_not_a_rename(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        exceptions=[
            VipException(
                vip_name="/Common/VS-WEB-HTTP-80",
                overrides={ChangeType.POOL_NAME: {"find": "", "replace": "MUM"}},
            )
        ],
    )
    resolved = resolve(
        plan,
        session_maps["nodes_by_name"],
        session_maps["pools_by_name"],
        session_maps["vips_by_name"],
        session_maps["graph"],
    )
    assert resolved.pool_renames == {}


def _validate(session_maps, plan: MigrationPlan):
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
    vi = ValidationInput(
        resolved=resolved,
        context=context,
        nodes_by_name=session_maps["nodes_by_name"],
        pools_by_name=session_maps["pools_by_name"],
        vips_by_name=session_maps["vips_by_name"],
        vlans_by_name=session_maps["vlans_by_name"],
        monitors_by_name=session_maps["monitors_by_name"],
    )
    return run_validation(vi)


def test_pattern_safety_check_blocks_with_a_specific_message(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        common_changes=[
            CommonChange(change_type=ChangeType.VIP_NAME, payload={"find": "", "replace": "MUM"})
        ],
    )
    result = _validate(session_maps, plan)
    pattern_check = next(c for c in result.checks if c.id == "pattern_safety")
    assert pattern_check.severity == "blocked"
    assert result.overall == "BLOCKED"
    assert any("VS-WEB-HTTP-80" in a and "vip_name" in a for a in pattern_check.affected)


def test_pattern_safety_check_passes_for_a_normal_find_replace(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        common_changes=[
            CommonChange(
                change_type=ChangeType.VIP_NAME, payload={"find": "VS-WEB-HTTP-80", "replace": "VS-MUM"}
            )
        ],
    )
    result = _validate(session_maps, plan)
    pattern_check = next(c for c in result.checks if c.id == "pattern_safety")
    assert pattern_check.severity == "pass"


def test_non_empty_find_still_replaces_normally(session_maps):
    # guard against over-correcting into a no-op for the real, intended case
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        common_changes=[
            CommonChange(
                change_type=ChangeType.VIP_NAME, payload={"find": "VS-WEB-HTTP-80", "replace": "VS-MUM"}
            )
        ],
    )
    text = _generate(session_maps, plan)
    assert "tmsh mv ltm virtual /Common/VS-WEB-HTTP-80 /Common/VS-MUM" in text
