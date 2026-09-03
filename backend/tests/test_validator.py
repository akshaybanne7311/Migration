from app.generation.emit_order import build_migration_context
from app.migration.change_engine import resolve
from app.models.change_set import (
    ChangeType,
    CommonChange,
    MigrationPlan,
    PoolMemberEdit,
    VipException,
)
from app.models.validation import Severity
from app.validation.context import ValidationInput
from app.validation.validator import run_validation


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


def test_external_vlan_warns_not_blocks_by_default(session_maps):
    # VS-WEB-HTTP-8080 references /Common/EXTERNAL-VLAN-9000, which has no
    # local net vlan object in the fixture -- must WARN, not BLOCK, when
    # create_network_objects is off (the default).
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-8080"],
        common_changes=[
            CommonChange(
                change_type=ChangeType.VLANS,
                payload={
                    "old_vlan": "/Common/WEB-VLAN-200",
                    "new_vlan": "/Common/WEB-VLAN-200",
                },
            )
        ],
        create_network_objects=False,
    )
    result = _validate(session_maps, plan)
    vlan_check = next(c for c in result.checks if c.id == "vlan_refs")
    assert vlan_check.severity == Severity.WARN
    assert result.overall == "READY"


def test_external_vlan_blocks_when_create_network_objects_true(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-8080"],
        common_changes=[
            CommonChange(
                change_type=ChangeType.VLANS,
                payload={
                    "old_vlan": "/Common/WEB-VLAN-200",
                    "new_vlan": "/Common/WEB-VLAN-200",
                },
            )
        ],
        create_network_objects=True,
    )
    result = _validate(session_maps, plan)
    vlan_check = next(c for c in result.checks if c.id == "vlan_refs")
    assert vlan_check.severity == Severity.BLOCKED
    assert result.overall == "BLOCKED"


def test_blocked_on_duplicate_name_conflict(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80", "/Common/VS-WEB-HTTP-8080"],
        common_changes=[CommonChange(change_type=ChangeType.VIP_NAME, payload={"find": "VS-WEB-HTTP", "replace": "VS-WEB"})],
        exceptions=[
            VipException(
                vip_name="/Common/VS-WEB-HTTP-8080",
                overrides={ChangeType.VIP_NAME: {"find": "VS-WEB-HTTP-8080", "replace": "VS-WEB-DUP"}},
            )
        ],
    )
    # force a real collision: both VIPs renamed to the exact same name
    plan.exceptions[0].overrides[ChangeType.VIP_NAME] = {"find": "VS-WEB-HTTP-8080", "replace": "VS-WEB-80"}
    result = _validate(session_maps, plan)
    dup_check = next(c for c in result.checks if c.id == "duplicates")
    assert dup_check.severity == Severity.BLOCKED
    assert result.overall == "BLOCKED"


def test_blocked_on_duplicate_pool_rename_target(session_maps):
    # WEB-POOL-1 and WEB-POOL-2 are distinct pools; renaming both to the
    # same target name must be blocked rather than silently colliding.
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80", "/Common/VS-WEB-HTTP-8080"],
        exceptions=[
            VipException(
                vip_name="/Common/VS-WEB-HTTP-80",
                overrides={
                    ChangeType.POOL_NAME: {"find": "/Common/WEB-POOL-1", "replace": "/Common/WEB-POOL-SHARED"}
                },
            ),
            VipException(
                vip_name="/Common/VS-WEB-HTTP-8080",
                overrides={
                    ChangeType.POOL_NAME: {"find": "/Common/WEB-POOL-2", "replace": "/Common/WEB-POOL-SHARED"}
                },
            ),
        ],
    )
    result = _validate(session_maps, plan)
    dup_check = next(c for c in result.checks if c.id == "duplicates")
    assert dup_check.severity == Severity.BLOCKED
    assert result.overall == "BLOCKED"


def test_blocked_on_empty_pool_members_when_source_had_members(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        pool_member_edits=[
            PoolMemberEdit(vip_name="/Common/VS-WEB-HTTP-80", action="replace_all", new_refs=[])
        ],
    )
    result = _validate(session_maps, plan)
    pm_check = next(c for c in result.checks if c.id == "pool_members")
    assert pm_check.severity == Severity.BLOCKED
    assert result.overall == "BLOCKED"


def test_ready_when_no_issues(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-REJECT"],
        common_changes=[
            CommonChange(change_type=ChangeType.PERSISTENCE, payload={"new_persistence": "/Common/source_addr"})
        ],
    )
    result = _validate(session_maps, plan)
    assert result.overall == "READY"
    assert all(c.severity != Severity.BLOCKED for c in result.checks)


def test_blocked_on_unresolvable_monitor_reference(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        common_changes=[
            CommonChange(change_type=ChangeType.MONITOR, payload={"new_monitor": "/Common/DOES-NOT-EXIST"})
        ],
    )
    result = _validate(session_maps, plan)
    monitor_check = next(c for c in result.checks if c.id == "monitor_refs")
    assert monitor_check.severity == Severity.BLOCKED
    assert result.overall == "BLOCKED"
    assert any("DOES-NOT-EXIST" in a for a in monitor_check.affected)


def test_ready_when_monitor_reference_exists(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        common_changes=[
            CommonChange(change_type=ChangeType.MONITOR, payload={"new_monitor": "/Common/WEB-HTTP-Monitor"})
        ],
    )
    result = _validate(session_maps, plan)
    monitor_check = next(c for c in result.checks if c.id == "monitor_refs")
    assert monitor_check.severity == Severity.PASS
    assert result.overall == "READY"


def test_migration_summary_counts_real_changes(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80", "/Common/VS-WEB-REJECT"],
        common_changes=[
            CommonChange(
                change_type=ChangeType.VLANS,
                payload={"old_vlan": "/Common/WEB-VLAN-200", "new_vlan": "/Common/WEB-VLAN-201"},
            )
        ],
    )
    result = _validate(session_maps, plan)
    summary = result.summary
    assert summary is not None
    assert summary.vips_selected == 2
    # only VS-WEB-HTTP-80 actually has WEB-VLAN-200 bound -- VS-WEB-REJECT
    # has no vlans at all, so the common change is a real no-op for it
    assert summary.vips_changed == 2  # both get the effective payload...
    assert summary.vlan_bindings_changed == 1  # ...but only one is a real delta
    # WEB-VLAN-201 has no local net vlan object in the fixture -- a real WARN
    assert summary.warnings == 1
    assert summary.errors == 0
