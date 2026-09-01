"""The mandatory end-to-end regression from the spec (Section 19/20):

Select a VIP with multiple pool members, change every node's IP (with a
new node name), change the VLAN, generate TMSH, and inspect the ACTUAL
generated text -- not just that the API call succeeded.

Verifies: new node names/IPs exist, old node names are absent from any
newly-created `ltm node` block, pool members reference only new nodes
with correct ports and the member block is never empty, the old VLAN is
removed from the VIP while the new one is present, `vlans-enabled` is
preserved, and Node -> Pool -> Vip ordering holds in the output.
"""
import re

from app.generation.emit_order import build_migration_context
from app.generation.tmsh_generator import generate_tmsh
from app.migration.change_engine import resolve
from app.models.change_set import ChangeType, CommonChange, MigrationPlan, NodeChange
from app.models.validation import Severity
from app.validation.context import ValidationInput
from app.validation.validator import run_validation

VIP_NAME = "/Common/VS-MNP-BL-SIP-5060-IPv6"
POOL_NAME = "/Common/TEST_POOL-JIO-MNP-BL-SIP-5060-IPv6"

OLD_NODES = [
    ("/Common/MNP-Node-1", "2001:db8:55::1", "/Common/MNP-Node-1-NEW"),
    ("/Common/MNP-Node-2", "2001:db8:55::2", "/Common/MNP-Node-2-NEW"),
    ("/Common/MNP-Node-3", "2001:db8:55::3", "/Common/MNP-Node-3-NEW"),
    ("/Common/MNP-Node-4", "2001:db8:55::4", "/Common/MNP-Node-4-NEW"),
    ("/Common/MNP-Node-5", "2001:db8:55::5", "/Common/MNP-Node-5-NEW"),
]
OLD_VLAN = "/Common/MNP-VLAN-1699"
NEW_VLAN = "/Common/MNP-VLAN-1700"


def test_section19_full_regression(session_maps):
    pool = session_maps["pools_by_name"][POOL_NAME]
    assert len(pool.members) == 5, "fixture VIP must have multiple pool members"

    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=[VIP_NAME],
        node_changes=[
            NodeChange(old_node_ref=old_name, new_ip=new_ip, new_node_name=new_name)
            for old_name, new_ip, new_name in OLD_NODES
        ],
        common_changes=[
            CommonChange(
                change_type=ChangeType.VLANS,
                payload={"old_vlan": OLD_VLAN, "new_vlan": NEW_VLAN},
            )
        ],
        create_network_objects=False,
    )

    resolved = resolve(
        plan,
        session_maps["nodes_by_name"],
        session_maps["pools_by_name"],
        session_maps["vips_by_name"],
        session_maps["graph"],
    )
    assert len(resolved.resolved_node_changes) == 5

    context = build_migration_context(
        resolved,
        session_maps["nodes_by_name"],
        session_maps["pools_by_name"],
        session_maps["vips_by_name"],
    )

    # --- validate: must be READY (external/undeclared new VLAN warns only) ---
    vi = ValidationInput(
        resolved=resolved,
        context=context,
        nodes_by_name=session_maps["nodes_by_name"],
        pools_by_name=session_maps["pools_by_name"],
        vips_by_name=session_maps["vips_by_name"],
        vlans_by_name=session_maps["vlans_by_name"],
    )
    validation = run_validation(vi)
    assert validation.overall == "READY", validation.model_dump()
    vlan_check = next(c for c in validation.checks if c.id == "vlan_refs")
    assert vlan_check.severity == Severity.WARN
    pool_members_check = next(c for c in validation.checks if c.id == "pool_members")
    assert pool_members_check.severity == Severity.PASS

    # --- generate and inspect the ACTUAL TMSH text ---
    text = generate_tmsh(context, session_maps["vips_by_name"])
    lines = [l for l in text.splitlines() if l.strip()]

    # 1. new node names + IPs exist; old node names never appear in a
    #    newly-created ltm node line.
    node_create_lines = [l for l in lines if l.startswith("tmsh create ltm node")]
    assert len(node_create_lines) == 5
    old_names = {old_name for old_name, _ip, _new in OLD_NODES}
    for old_name, new_ip, new_name in OLD_NODES:
        matching = [l for l in node_create_lines if new_name in l]
        assert len(matching) == 1, "expected exactly one create for %s" % new_name
        assert matching[0] == "tmsh create ltm node %s address %s" % (new_name, new_ip)
        # the OLD node is never itself created as a separate object (no
        # "create ltm node <old_name> address ..." line for the literal old
        # name -- note new names intentionally contain the old name as a
        # prefix, e.g. MNP-Node-1 -> MNP-Node-1-NEW, so this checks for an
        # exact old-name create rather than a substring).
        assert not any(l.startswith("tmsh create ltm node %s " % old_name) for l in node_create_lines)
    assert old_names.isdisjoint({l.split()[4] for l in node_create_lines})

    # 2. exactly one node create per physical node (dedup, not per-VIP or
    #    per-pool duplication even though MNP-Node-1/2 are shared across 2
    #    pools in the fixture).
    assert len({l for l in node_create_lines}) == 5

    # 3. pool members block: non-empty, references only new nodes, correct
    #    ports, no old node names remain.
    pool_line = next(l for l in lines if l.startswith("tmsh modify ltm pool %s" % POOL_NAME))
    assert "replace-all-with {  }" not in pool_line
    member_refs = re.findall(r"(/Common/[\w-]+):(\d+)", pool_line.split("replace-all-with", 1)[1])
    assert len(member_refs) == 5
    assert all(port == "5060" for _name, port in member_refs)
    member_names = {name for name, _port in member_refs}
    assert member_names == {new_name for _old, _ip, new_name in OLD_NODES}
    assert old_names.isdisjoint(member_names)  # no old node name still referenced

    # 4. VLAN: old removed, new present, vlans-enabled preserved.
    vip_line = next(l for l in lines if l.startswith("tmsh modify ltm virtual %s vlans" % VIP_NAME))
    assert OLD_VLAN not in vip_line
    assert NEW_VLAN in vip_line
    assert "vlans-enabled" in vip_line
    assert "vlans-disabled" not in vip_line

    # 5. dependency ordering: every node create precedes the pool modify,
    #    which precedes the vip modify.
    node_idx = max(i for i, l in enumerate(lines) if l.startswith("tmsh create ltm node"))
    pool_idx = next(i for i, l in enumerate(lines) if l.startswith("tmsh modify ltm pool"))
    vip_idx = next(i for i, l in enumerate(lines) if l.startswith("tmsh modify ltm virtual"))
    assert node_idx < pool_idx < vip_idx
