"""Regression test for a real bug: the tmsh_syntax validation check always
ran generate_tmsh() (the changes_only generator) no matter what mode the
plan was actually in. For a full_recreate plan with no field-level changes
selected -- "just move these VIPs as-is", an explicitly supported case
(see full_recreate.py's own docstring) -- vip_effective comes out empty,
generate_tmsh() produces zero lines, and the check trivially passed having
validated none of the real tmsh /generate would actually produce.
"""
from app.generation.emit_order import build_migration_context
from app.generation.full_recreate import build_full_recreate_units, generate_full_recreate_tmsh
from app.migration.change_engine import resolve
from app.models.change_set import MigrationPlan
from app.validation.context import ValidationInput
from app.validation.checks import tmsh_syntax


def _build_vi(session_maps, plan: MigrationPlan) -> ValidationInput:
    resolved = resolve(
        plan,
        session_maps["nodes_by_name"],
        session_maps["pools_by_name"],
        session_maps["vips_by_name"],
        session_maps["graph"],
    )
    context = build_migration_context(
        resolved, session_maps["nodes_by_name"], session_maps["pools_by_name"], session_maps["vips_by_name"]
    )
    return ValidationInput(
        resolved=resolved,
        context=context,
        nodes_by_name=session_maps["nodes_by_name"],
        pools_by_name=session_maps["pools_by_name"],
        vips_by_name=session_maps["vips_by_name"],
        vlans_by_name=session_maps["vlans_by_name"],
        monitors_by_name=session_maps["monitors_by_name"],
        output_mode=plan.output_mode,
    )


def test_full_recreate_with_no_field_changes_still_gets_its_real_tmsh_checked(session_maps):
    vip_name = "/Common/VS-WEB-HTTP-80"
    plan = MigrationPlan(session_id=session_maps["session_id"], selected_vips=[vip_name], output_mode="full_recreate")
    vi = _build_vi(session_maps, plan)

    # Confirm the premise: with no common_changes/exceptions, vip_effective
    # is genuinely empty for this VIP -- the old code's has_effective_change
    # would have been False here.
    assert vi.context.vip_effective.get(vip_name, {}) == {}

    # What /generate would actually produce for this plan -- real,
    # non-empty tmsh, since full_recreate always emits create commands for
    # every selected VIP's full dependency closure regardless of whether
    # any field was changed.
    units = build_full_recreate_units(
        [vip_name], vi.context, vi.nodes_by_name, vi.pools_by_name, vi.vips_by_name, vi.monitors_by_name
    )
    real_tmsh = generate_full_recreate_tmsh(units)
    assert real_tmsh.strip(), "full_recreate must produce real tmsh even with zero field changes"
    assert "tmsh create ltm virtual %s" % vip_name in real_tmsh

    check = tmsh_syntax.check(vi)
    assert check.severity.value == "pass"
    assert check.details == "generated TMSH is well-formed"


def test_changes_only_mode_is_unaffected_by_the_output_mode_field(session_maps):
    vip_name = "/Common/VS-WEB-HTTP-80"
    plan = MigrationPlan(session_id=session_maps["session_id"], selected_vips=[vip_name], output_mode="changes_only")
    vi = _build_vi(session_maps, plan)
    check = tmsh_syntax.check(vi)
    assert check.severity.value == "pass"
