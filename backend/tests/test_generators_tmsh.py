from app.generation.emit_order import build_migration_context
from app.generation.tmsh_generator import generate_tmsh
from app.migration.change_engine import resolve
from app.models.change_set import ChangeType, CommonChange, MemberRef, MigrationPlan, NodeChange, PoolMemberEdit


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


def test_tmsh_output_matches_resolved_plan(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        node_changes=[NodeChange(old_node_ref="/Common/WEB-Node-1", new_ip="10.20.30.200")],
    )
    text = _generate(session_maps, plan)
    assert "tmsh create ltm node /Common/WEB-Node-1 address 10.20.30.200" in text
    assert "tmsh modify ltm pool /Common/WEB-POOL-1 members replace-all-with" in text


def test_emit_order_nodes_before_pools_before_vips(session_maps):
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
    )
    text = _generate(session_maps, plan)
    lines = [l for l in text.splitlines() if l.strip()]
    node_idx = next(i for i, l in enumerate(lines) if l.startswith("tmsh create ltm node"))
    pool_idx = next(i for i, l in enumerate(lines) if l.startswith("tmsh modify ltm pool"))
    vip_idx = next(i for i, l in enumerate(lines) if l.startswith("tmsh modify ltm virtual"))
    assert node_idx < pool_idx < vip_idx


def test_ipv6_node_object_address_only_no_bogus_port_suffix(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-MNP-BL-SIP-5060-IPv6"],
        node_changes=[
            NodeChange(old_node_ref="/Common/MNP-Node-1", new_ip="2001:db8:55::1", new_node_name="/Common/MNP-Node-1-NEW")
        ],
    )
    text = _generate(session_maps, plan)
    node_line = next(l for l in text.splitlines() if "MNP-Node-1-NEW" in l and l.startswith("tmsh create"))
    assert node_line == "tmsh create ltm node /Common/MNP-Node-1-NEW address 2001:db8:55::1"
    # never "address:port" or "address.port" as a node identity
    assert ":5060" not in node_line
    assert ".5060" not in node_line

    pool_line = next(
        l for l in text.splitlines() if l.startswith("tmsh modify ltm pool /Common/TEST_POOL-JIO-MNP-BL-SIP-5060-IPv6")
    )
    assert "/Common/MNP-Node-1-NEW:5060" in pool_line


def test_pool_member_block_never_empty_when_source_had_members(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        pool_member_edits=[
            PoolMemberEdit(
                vip_name="/Common/VS-WEB-HTTP-80",
                action="replace_all",
                new_refs=[MemberRef(address="10.20.30.70", port=80)],
            )
        ],
    )
    text = _generate(session_maps, plan)
    pool_line = next(l for l in text.splitlines() if l.startswith("tmsh modify ltm pool /Common/WEB-POOL-1"))
    assert "replace-all-with {  }" not in pool_line  # not an empty member block
    assert "/Common/10.20.30.70:80 { }" in pool_line
