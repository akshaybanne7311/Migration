import pytest

from app.migration.node_cascade import NodeCascadeError, resolve_node_changes
from app.models.change_set import NodeChange


def test_node_ip_change_emitted_exactly_once_across_shared_pools(session_maps):
    # MNP-Node-1 is shared by 2 pools and 3 VIPs in the fixture; a single
    # NodeChange must resolve to exactly one ResolvedNodeChange regardless.
    changes = [NodeChange(old_node_ref="/Common/MNP-Node-1", new_ip="2001:db8:55::1", new_node_name="/Common/MNP-Node-1-NEW")]
    resolved = resolve_node_changes(changes, session_maps["nodes_by_name"], session_maps["graph"])
    assert len(resolved) == 1
    rnc = resolved[0]
    assert rnc.new_node_name == "/Common/MNP-Node-1-NEW"
    assert rnc.new_address == "2001:db8:55::1"
    assert set(rnc.affected_pools) == {
        "/Common/TEST_POOL-JIO-MNP-BL-SIP-5060-IPv6",
        "/Common/TEST_POOL-JIO-MNP-BL-SIP-5070-IPv6",
    }
    assert len(rnc.affected_vips) == 3


def test_node_change_by_old_ip_resolves_to_same_node_as_by_name(session_maps):
    by_name = resolve_node_changes(
        [NodeChange(old_node_ref="/Common/MNP-Node-2", new_ip="2001:db8:55::2")],
        session_maps["nodes_by_name"],
        session_maps["graph"],
    )
    by_ip = resolve_node_changes(
        [NodeChange(old_node_ref="2405:200:642:a699:22:0:25:2", new_ip="2001:db8:55::2")],
        session_maps["nodes_by_name"],
        session_maps["graph"],
    )
    assert by_name[0].old_node_name == by_ip[0].old_node_name == "/Common/MNP-Node-2"


def test_unresolvable_node_reference_raises(session_maps):
    with pytest.raises(NodeCascadeError):
        resolve_node_changes(
            [NodeChange(old_node_ref="/Common/does-not-exist", new_ip="10.1.1.1")],
            session_maps["nodes_by_name"],
            session_maps["graph"],
        )


def test_conflicting_changes_for_same_node_raises(session_maps):
    """Real gap: two NodeChange entries can reference the same physical
    node (by name vs. by its old IP) with different target IPs. Before this
    was fixed, resolve_node_changes silently kept only the last one --
    the other request vanished with no error."""
    changes = [
        NodeChange(old_node_ref="/Common/WEB-Node-1", new_ip="10.20.30.200"),
        NodeChange(old_node_ref="10.20.30.11", new_ip="10.20.30.201"),  # same node, different target
    ]
    with pytest.raises(NodeCascadeError):
        resolve_node_changes(changes, session_maps["nodes_by_name"], session_maps["graph"])


def test_identical_duplicate_node_change_does_not_raise(session_maps):
    changes = [
        NodeChange(old_node_ref="/Common/WEB-Node-1", new_ip="10.20.30.200"),
        NodeChange(old_node_ref="/Common/WEB-Node-1", new_ip="10.20.30.200"),
    ]
    resolved = resolve_node_changes(changes, session_maps["nodes_by_name"], session_maps["graph"])
    assert len(resolved) == 1
