"""Regression coverage for the full-recreate generators (generation/full_recreate.py).

Fixes a real gap found during manual UI testing: selecting VIPs with zero
field-level changes chosen produced a completely empty TMSH/REST/AS3
output with no explanation, because the modify-only generators only ever
emit a *patch* for changed fields and assume every referenced object
already exists on the target. That is correct for "renumber in place on
the same device" but wrong for "stand these VIPs up on a new device" --
which is a normal, valid selection with zero changes chosen.
"""
from app.generation.emit_order import build_migration_context
from app.generation.full_recreate import (
    build_full_recreate_units,
    generate_full_recreate_as3,
    generate_full_recreate_rest,
    generate_full_recreate_tmsh,
)
from app.migration.change_engine import resolve
from app.models.change_set import ChangeType, CommonChange, MigrationPlan, NodeChange
from app.storage.repositories import MonitorRepository


def _units(session_maps, plan: MigrationPlan):
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
    monitors_by_name = {m.name: m for m in MonitorRepository.list(session_maps["conn"])}
    return build_full_recreate_units(
        plan.selected_vips,
        context,
        session_maps["nodes_by_name"],
        session_maps["pools_by_name"],
        session_maps["vips_by_name"],
        monitors_by_name,
    )


def test_zero_changes_still_produces_a_full_script(session_maps):
    """The exact bug report: select a VIP, choose no changes, hit Generate."""
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        output_mode="full_recreate",
    )
    units = _units(session_maps, plan)
    text = generate_full_recreate_tmsh(units)
    assert text.strip() != ""
    assert "tmsh create ltm node /Common/WEB-Node-1 address" in text
    assert "tmsh create ltm pool /Common/WEB-POOL-1" in text
    assert "tmsh create ltm virtual /Common/VS-WEB-HTTP-80" in text
    assert "destination /Common/10.10.10.10:80" in text


def test_creation_order_is_monitor_then_node_then_pool_then_vip(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        output_mode="full_recreate",
    )
    units = _units(session_maps, plan)
    lines = [l for l in generate_full_recreate_tmsh(units).splitlines() if l.strip()]
    node_idx = next(i for i, l in enumerate(lines) if l.startswith("tmsh create ltm node"))
    pool_idx = next(i for i, l in enumerate(lines) if l.startswith("tmsh create ltm pool"))
    vip_idx = next(i for i, l in enumerate(lines) if l.startswith("tmsh create ltm virtual"))
    assert node_idx < pool_idx < vip_idx
    monitor_idxs = [i for i, l in enumerate(lines) if l.startswith("tmsh create ltm monitor")]
    if monitor_idxs:
        assert max(monitor_idxs) < node_idx


def test_shared_node_created_exactly_once_across_selected_vips(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-MNP-BL-SIP-5060-IPv6", "/Common/VS-MNP-BL-SIP-5061-IPv6-RD"],
        output_mode="full_recreate",
    )
    units = _units(session_maps, plan)
    text = generate_full_recreate_tmsh(units)
    assert text.count("tmsh create ltm node /Common/MNP-Node-1 ") == 1


def test_changes_are_applied_to_the_recreated_objects(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        node_changes=[NodeChange(old_node_ref="/Common/WEB-Node-1", new_ip="10.20.30.200")],
        common_changes=[
            CommonChange(
                change_type=ChangeType.VLANS,
                payload={"old_vlan": "/Common/WEB-VLAN-200", "new_vlan": "/Common/WEB-VLAN-201"},
            )
        ],
        output_mode="full_recreate",
    )
    units = _units(session_maps, plan)
    text = generate_full_recreate_tmsh(units)
    assert "tmsh create ltm node /Common/WEB-Node-1 address 10.20.30.200" in text
    vip_line = next(l for l in text.splitlines() if l.startswith("tmsh create ltm virtual /Common/VS-WEB-HTTP-80"))
    assert "/Common/WEB-VLAN-201" in vip_line
    assert "/Common/WEB-VLAN-200" not in vip_line
    pool_line = next(l for l in text.splitlines() if l.startswith("tmsh create ltm pool /Common/WEB-POOL-1"))
    assert "/Common/WEB-Node-1:80" in pool_line  # member ref by name is untouched (no rename requested)
    node_line = next(l for l in text.splitlines() if l.startswith("tmsh create ltm node /Common/WEB-Node-1 "))
    assert node_line.endswith("10.20.30.200")  # but the node object's address itself is updated


def test_rest_and_as3_also_produce_output_for_zero_changes(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        output_mode="full_recreate",
    )
    units = _units(session_maps, plan)
    rest_calls = generate_full_recreate_rest(units)
    assert any(c.path == "/mgmt/tm/ltm/virtual" and c.method == "POST" for c in rest_calls)
    assert any(c.path == "/mgmt/tm/ltm/pool" and c.method == "POST" for c in rest_calls)

    as3 = generate_full_recreate_as3(units)
    apps = as3["declaration"]["Tenant_Migration"]
    assert len(apps) > 1  # more than just the "class" key
