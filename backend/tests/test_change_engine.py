import pytest

from app.migration.change_engine import ChangeEngineError, resolve
from app.models.change_set import (
    ChangeType,
    CommonChange,
    MemberRef,
    MigrationPlan,
    PoolMemberEdit,
    VipException,
)


def test_resolve_plan_single_vip(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-REJECT"],
        common_changes=[
            CommonChange(change_type=ChangeType.PERSISTENCE, payload={"new_persistence": "/Common/source_addr"})
        ],
    )
    resolved = resolve(
        plan,
        session_maps["nodes_by_name"],
        session_maps["pools_by_name"],
        session_maps["vips_by_name"],
        session_maps["graph"],
    )
    assert len(resolved.vip_changes) == 1
    assert resolved.vip_changes[0].effective[ChangeType.PERSISTENCE]["new_persistence"] == "/Common/source_addr"


def test_resolve_plan_bulk_vips_shared_pool(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=[
            "/Common/VS-MNP-BL-SIP-5060-IPv6",
            "/Common/VS-MNP-BL-SIP-5070-IPv6",
        ],
        common_changes=[
            CommonChange(
                change_type=ChangeType.VLANS,
                payload={"old_vlan": "/Common/MNP-VLAN-1699", "new_vlan": "/Common/MNP-VLAN-1700"},
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
    assert len(resolved.resolved_vlan_changes) == 2


def test_common_change_applies_to_all_selected(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80", "/Common/VS-WEB-HTTP-8080"],
        common_changes=[
            CommonChange(change_type=ChangeType.MONITOR, payload={"new_monitor": "/Common/WEB-HTTP-Monitor-New"})
        ],
    )
    resolved = resolve(
        plan,
        session_maps["nodes_by_name"],
        session_maps["pools_by_name"],
        session_maps["vips_by_name"],
        session_maps["graph"],
    )
    for vc in resolved.vip_changes:
        assert vc.effective[ChangeType.MONITOR]["new_monitor"] == "/Common/WEB-HTTP-Monitor-New"


def test_exception_overrides_common_change_field_only(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80", "/Common/VS-WEB-HTTP-8080"],
        common_changes=[
            CommonChange(
                change_type=ChangeType.VLANS,
                payload={"old_vlan": "/Common/WEB-VLAN-200", "new_vlan": "/Common/WEB-VLAN-201"},
            ),
            CommonChange(change_type=ChangeType.MONITOR, payload={"new_monitor": "/Common/WEB-HTTP-Monitor-New"}),
        ],
        exceptions=[
            VipException(
                vip_name="/Common/VS-WEB-HTTP-8080",
                overrides={
                    ChangeType.VLANS: {
                        "old_vlan": "/Common/WEB-VLAN-200",
                        "new_vlan": "/Common/WEB-VLAN-999-EXCEPTION",
                    }
                },
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
    by_vip = {vc.vip_name: vc for vc in resolved.vip_changes}
    # exception VIP gets its own VLAN target...
    assert (
        by_vip["/Common/VS-WEB-HTTP-8080"].effective[ChangeType.VLANS]["new_vlan"]
        == "/Common/WEB-VLAN-999-EXCEPTION"
    )
    # ...but still inherits the common MONITOR change, since the exception
    # only overrode VLANS.
    assert (
        by_vip["/Common/VS-WEB-HTTP-8080"].effective[ChangeType.MONITOR]["new_monitor"]
        == "/Common/WEB-HTTP-Monitor-New"
    )
    # the non-exception VIP keeps the plain common VLAN change.
    assert (
        by_vip["/Common/VS-WEB-HTTP-80"].effective[ChangeType.VLANS]["new_vlan"]
        == "/Common/WEB-VLAN-201"
    )


def test_exception_for_unselected_vip_raises(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        exceptions=[VipException(vip_name="/Common/VS-WEB-HTTP-8080", overrides={})],
    )
    with pytest.raises(ChangeEngineError):
        resolve(
            plan,
            session_maps["nodes_by_name"],
            session_maps["pools_by_name"],
            session_maps["vips_by_name"],
            session_maps["graph"],
        )


def test_pool_member_replace_selected_vs_replace_all(session_maps):
    plan_selected = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        pool_member_edits=[
            PoolMemberEdit(
                vip_name="/Common/VS-WEB-HTTP-80",
                action="replace_selected",
                old_refs=[MemberRef(node_name="/Common/WEB-Node-1", port=80)],
                new_refs=[MemberRef(address="10.20.30.55", new_node_name="/Common/WEB-Node-1-NEW", port=80)],
            )
        ],
    )
    resolved = resolve(
        plan_selected,
        session_maps["nodes_by_name"],
        session_maps["pools_by_name"],
        session_maps["vips_by_name"],
        session_maps["graph"],
    )
    rpmc = resolved.resolved_pool_member_changes[0]
    new_names = {m.node_name for m in rpmc.new_members}
    # WEB-Node-2 and the orphan node are untouched, WEB-Node-1 is replaced
    assert "/Common/WEB-Node-2" in new_names
    assert "/Common/10.20.30.99" in new_names
    assert "/Common/WEB-Node-1-NEW" in new_names
    assert "/Common/WEB-Node-1" not in new_names

    plan_all = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        pool_member_edits=[
            PoolMemberEdit(
                vip_name="/Common/VS-WEB-HTTP-80",
                action="replace_all",
                new_refs=[MemberRef(address="10.20.30.60", port=80)],
            )
        ],
    )
    resolved_all = resolve(
        plan_all,
        session_maps["nodes_by_name"],
        session_maps["pools_by_name"],
        session_maps["vips_by_name"],
        session_maps["graph"],
    )
    rpmc_all = resolved_all.resolved_pool_member_changes[0]
    assert len(rpmc_all.new_members) == 1
    assert rpmc_all.new_members[0].address == "10.20.30.60"


def test_conflicting_pool_member_edits_for_shared_pool_raises(session_maps):
    """Real gap found via manual testing: VS-MNP-BL-SIP-5060-IPv6 and
    VS-MNP-BL-SIP-5061-IPv6-RD share one pool in the fixture. Giving each a
    different per-VIP replace_all edit used to resolve silently -- only the
    last-processed edit's members survived in emit_order's pool-name-keyed
    dict, so the pool ended up with only one VIP's intended members and the
    generated TMSH never even hinted the other VIP's edit was dropped."""
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-MNP-BL-SIP-5060-IPv6", "/Common/VS-MNP-BL-SIP-5061-IPv6-RD"],
        pool_member_edits=[
            PoolMemberEdit(
                vip_name="/Common/VS-MNP-BL-SIP-5060-IPv6",
                action="replace_all",
                new_refs=[MemberRef(address="2001:db8::aaaa", port=5060)],
            ),
            PoolMemberEdit(
                vip_name="/Common/VS-MNP-BL-SIP-5061-IPv6-RD",
                action="replace_all",
                new_refs=[MemberRef(address="2001:db8::bbbb", port=5061)],
            ),
        ],
    )
    with pytest.raises(ChangeEngineError):
        resolve(
            plan,
            session_maps["nodes_by_name"],
            session_maps["pools_by_name"],
            session_maps["vips_by_name"],
            session_maps["graph"],
        )


def test_identical_pool_member_edits_for_shared_pool_does_not_raise(session_maps):
    """The wizard's own 'apply to all selected VIPs' UI path always issues
    one identical edit per selected VIP -- that must keep working."""
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-MNP-BL-SIP-5060-IPv6", "/Common/VS-MNP-BL-SIP-5061-IPv6-RD"],
        pool_member_edits=[
            PoolMemberEdit(
                vip_name="/Common/VS-MNP-BL-SIP-5060-IPv6",
                action="replace_all",
                new_refs=[MemberRef(address="2001:db8::aaaa", port=5060)],
            ),
            PoolMemberEdit(
                vip_name="/Common/VS-MNP-BL-SIP-5061-IPv6-RD",
                action="replace_all",
                new_refs=[MemberRef(address="2001:db8::aaaa", port=5060)],
            ),
        ],
    )
    resolved = resolve(
        plan,
        session_maps["nodes_by_name"],
        session_maps["pools_by_name"],
        session_maps["vips_by_name"],
        session_maps["graph"],
    )
    assert len(resolved.resolved_pool_member_changes) == 2


def test_vlan_common_change_preserves_vlans_enabled(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-MNP-BL-SIP-5060-IPv6"],
        common_changes=[
            CommonChange(
                change_type=ChangeType.VLANS,
                payload={"old_vlan": "/Common/MNP-VLAN-1699", "new_vlan": "/Common/MNP-VLAN-1700"},
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
    rv = resolved.resolved_vlan_changes[0]
    assert rv.new_vlans == ["/Common/MNP-VLAN-1700"]
    assert rv.vlans_enabled is True


def test_vlan_remove_only_actually_removes(session_maps):
    """Real gap found comparing against another implementation's docs: a
    remove-only VLAN request (old_vlan set, no new_vlan) used to silently
    fall through to a no-op branch and do nothing."""
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-MNP-BL-SIP-5060-IPv6"],
        common_changes=[
            CommonChange(change_type=ChangeType.VLANS, payload={"old_vlan": "/Common/MNP-VLAN-1699"})
        ],
    )
    resolved = resolve(
        plan,
        session_maps["nodes_by_name"],
        session_maps["pools_by_name"],
        session_maps["vips_by_name"],
        session_maps["graph"],
    )
    rv = resolved.resolved_vlan_changes[0]
    assert rv.new_vlans == []


def test_vlan_add_only_appends_without_duplicating(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-MNP-BL-SIP-5060-IPv6"],
        common_changes=[
            CommonChange(change_type=ChangeType.VLANS, payload={"new_vlan": "/Common/EXTRA-VLAN"})
        ],
    )
    resolved = resolve(
        plan,
        session_maps["nodes_by_name"],
        session_maps["pools_by_name"],
        session_maps["vips_by_name"],
        session_maps["graph"],
    )
    rv = resolved.resolved_vlan_changes[0]
    assert rv.new_vlans == ["/Common/MNP-VLAN-1699", "/Common/EXTRA-VLAN"]

    # adding a VLAN that's already bound must not duplicate it
    plan_dup = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-MNP-BL-SIP-5060-IPv6"],
        common_changes=[
            CommonChange(change_type=ChangeType.VLANS, payload={"new_vlan": "/Common/MNP-VLAN-1699"})
        ],
    )
    resolved_dup = resolve(
        plan_dup,
        session_maps["nodes_by_name"],
        session_maps["pools_by_name"],
        session_maps["vips_by_name"],
        session_maps["graph"],
    )
    assert resolved_dup.resolved_vlan_changes[0].new_vlans == ["/Common/MNP-VLAN-1699"]


def test_vlan_explicit_action_overrides_inference(session_maps):
    """Passing both old_vlan and new_vlan but action='remove' should remove
    old_vlan and ignore new_vlan, not infer a replace."""
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-MNP-BL-SIP-5060-IPv6"],
        common_changes=[
            CommonChange(
                change_type=ChangeType.VLANS,
                payload={"old_vlan": "/Common/MNP-VLAN-1699", "new_vlan": "/Common/IGNORED", "action": "remove"},
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
    assert resolved.resolved_vlan_changes[0].new_vlans == []
