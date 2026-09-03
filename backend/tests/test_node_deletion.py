from app.generation.emit_order import build_migration_context
from app.generation.rest_generator import generate_rest
from app.generation.tmsh_generator import generate_tmsh
from app.migration.change_engine import resolve
from app.models.change_set import MemberRef, MigrationPlan, PoolMemberEdit
from app.validation.context import ValidationInput
from app.validation.validator import run_validation


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


def _validate(session_maps, resolved, context):
    vi = ValidationInput(
        resolved=resolved,
        context=context,
        nodes_by_name=session_maps["nodes_by_name"],
        pools_by_name=session_maps["pools_by_name"],
        vips_by_name=session_maps["vips_by_name"],
        vlans_by_name=session_maps["vlans_by_name"],
    )
    return run_validation(vi)


def test_remove_node_blocked_when_still_referenced_by_another_pool(session_maps):
    # MNP-Node-1 is a member of both the 5060 and 5070 MNP pools in the
    # fixture; removing it from just one pool with remove_node=True must
    # be blocked, not silently delete a node another pool still needs.
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-MNP-BL-SIP-5060-IPv6"],
        pool_member_edits=[
            PoolMemberEdit(
                vip_name="/Common/VS-MNP-BL-SIP-5060-IPv6",
                action="remove",
                old_refs=[MemberRef(node_name="/Common/MNP-Node-1", port=5060, remove_node=True)],
            )
        ],
    )
    resolved, context = _resolve_and_build(session_maps, plan)
    assert resolved.node_deletions == ["/Common/MNP-Node-1"]
    result = _validate(session_maps, resolved, context)
    node_check = next(c for c in result.checks if c.id == "node_refs")
    assert node_check.severity == "blocked"
    assert result.overall == "BLOCKED"
    assert any("MNP-Node-1" in a for a in node_check.affected)


def test_remove_node_allowed_when_no_longer_referenced_anywhere(session_maps):
    # WEB-Node-2 is only a member of WEB-POOL-1 in the fixture, so deleting
    # it once removed from that pool's only reference is safe.
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        pool_member_edits=[
            PoolMemberEdit(
                vip_name="/Common/VS-WEB-HTTP-80",
                action="remove",
                old_refs=[MemberRef(node_name="/Common/WEB-Node-2", port=80, remove_node=True)],
            )
        ],
    )
    resolved, context = _resolve_and_build(session_maps, plan)
    result = _validate(session_maps, resolved, context)
    node_check = next(c for c in result.checks if c.id == "node_refs")
    assert node_check.severity == "pass"
    assert result.overall == "READY"

    tmsh = generate_tmsh(context, session_maps["vips_by_name"])
    assert "tmsh delete ltm node /Common/WEB-Node-2" in tmsh
    lines = [l for l in tmsh.splitlines() if l.strip()]
    delete_idx = next(i for i, l in enumerate(lines) if l.startswith("tmsh delete ltm node"))
    assert delete_idx == len(lines) - 1  # deletes always come last

    calls = generate_rest(context, session_maps["vips_by_name"])
    delete_calls = [c for c in calls if c.method == "DELETE"]
    assert len(delete_calls) == 1
    assert "WEB-Node-2" in delete_calls[0].path


def test_remove_without_remove_node_flag_does_not_delete(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        pool_member_edits=[
            PoolMemberEdit(
                vip_name="/Common/VS-WEB-HTTP-80",
                action="remove",
                old_refs=[MemberRef(node_name="/Common/WEB-Node-2", port=80)],
            )
        ],
    )
    resolved, _context = _resolve_and_build(session_maps, plan)
    assert resolved.node_deletions == []
