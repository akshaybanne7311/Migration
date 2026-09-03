import pytest

from app.migration.csv_import import (
    CsvImportError,
    parse_node_changes_csv,
    parse_pool_member_rules_csv,
    parse_vip_changes_csv,
    parse_vlan_rules_csv,
)
from app.models.domain import AddressFamily, Pool, Vip


def _vip(name, pool_name="/Common/POOL-A", vlans=None):
    return Vip(
        name=name,
        destination_address="203.0.113.10",
        destination_port=443,
        address_family=AddressFamily.IPV4,
        pool_name=pool_name,
        vlans=vlans or ["/Common/VLAN-OLD"],
    )


VIPS_BY_NAME = {
    "/Common/VS-A": _vip("/Common/VS-A"),
    "/Common/VS-B": _vip("/Common/VS-B", pool_name="/Common/POOL-B"),
    "/Common/VS-NO-POOL": _vip("/Common/VS-NO-POOL", pool_name=None),
}

POOLS_BY_NAME = {
    "/Common/POOL-A": Pool(name="/Common/POOL-A"),
    "/Common/POOL-B": Pool(name="/Common/POOL-B"),
}


class TestParseVipChangesCsv:
    def test_renames_name_ip_port_and_pool(self):
        csv_content = (
            "source_vip,target_vip_name,target_vip_ip,target_vip_port,target_pool_name\n"
            "/Common/VS-A,/Common/VS-A-NEW,203.0.113.99,8443,/Common/POOL-A-NEW\n"
        )
        result = parse_vip_changes_csv(csv_content, VIPS_BY_NAME)
        assert len(result) == 1
        exc = result[0]
        assert exc.vip_name == "/Common/VS-A"
        assert exc.overrides["vip_name"] == {"find": "/Common/VS-A", "replace": "/Common/VS-A-NEW"}
        assert exc.overrides["vip_ip_port"] == {"new_address": "203.0.113.99", "new_port": 8443}
        assert exc.overrides["pool_name"] == {"find": "/Common/POOL-A", "replace": "/Common/POOL-A-NEW"}

    def test_blank_target_columns_are_skipped(self):
        csv_content = "source_vip,target_vip_name,target_vip_ip,target_vip_port,target_pool_name\n/Common/VS-A,/Common/VS-A-NEW,,,\n"
        result = parse_vip_changes_csv(csv_content, VIPS_BY_NAME)
        assert list(result[0].overrides.keys()) == ["vip_name"]

    def test_unknown_vip_raises(self):
        csv_content = "source_vip,target_vip_name\n/Common/NOT-REAL,/Common/X\n"
        with pytest.raises(CsvImportError, match="does not exist"):
            parse_vip_changes_csv(csv_content, VIPS_BY_NAME)

    def test_no_target_columns_raises(self):
        csv_content = "source_vip,target_vip_name\n/Common/VS-A,\n"
        with pytest.raises(CsvImportError, match="no target_"):
            parse_vip_changes_csv(csv_content, VIPS_BY_NAME)

    def test_pool_rename_without_current_pool_raises(self):
        csv_content = "source_vip,target_pool_name\n/Common/VS-NO-POOL,/Common/POOL-X\n"
        with pytest.raises(CsvImportError, match="no current pool"):
            parse_vip_changes_csv(csv_content, VIPS_BY_NAME)


class TestParseVlanRulesCsv:
    def test_blank_vip_name_applies_to_all_selected(self):
        csv_content = "vip_name,action,old_vlan,new_vlan\n,replace,/Common/VLAN-OLD,/Common/VLAN-NEW\n"
        result = parse_vlan_rules_csv(csv_content, ["/Common/VS-A", "/Common/VS-B"])
        assert {e.vip_name for e in result} == {"/Common/VS-A", "/Common/VS-B"}
        assert all(e.overrides["vlans"]["action"] == "replace" for e in result)

    def test_specific_vip_name_targets_only_that_vip(self):
        csv_content = "vip_name,action,old_vlan\n/Common/VS-A,remove,/Common/VLAN-OLD\n"
        result = parse_vlan_rules_csv(csv_content, ["/Common/VS-A", "/Common/VS-B"])
        assert len(result) == 1
        assert result[0].vip_name == "/Common/VS-A"
        assert result[0].overrides["vlans"] == {"action": "remove", "old_vlan": "/Common/VLAN-OLD"}

    def test_remove_without_old_vlan_raises(self):
        csv_content = "action,new_vlan\nremove,/Common/VLAN-NEW\n"
        with pytest.raises(CsvImportError, match="requires old_vlan"):
            parse_vlan_rules_csv(csv_content, ["/Common/VS-A"])

    def test_invalid_action_raises(self):
        csv_content = "action,old_vlan\nrename,/Common/VLAN-OLD\n"
        with pytest.raises(CsvImportError, match="action must be"):
            parse_vlan_rules_csv(csv_content, ["/Common/VS-A"])

    def test_no_selected_vips_with_blank_vip_name_raises(self):
        csv_content = "action,old_vlan,new_vlan\nreplace,/Common/VLAN-OLD,/Common/VLAN-NEW\n"
        with pytest.raises(CsvImportError, match="no VIPs are selected"):
            parse_vlan_rules_csv(csv_content, [])


class TestParsePoolMemberRulesCsv:
    def test_add_fans_out_to_all_selected_vips_sharing_pool(self):
        csv_content = "source_pool,action,target_node,target_address,target_port\n/Common/POOL-A,add,,203.0.113.50,80\n"
        result = parse_pool_member_rules_csv(
            csv_content, ["/Common/VS-A"], VIPS_BY_NAME, POOLS_BY_NAME
        )
        assert len(result) == 1
        assert result[0].vip_name == "/Common/VS-A"
        assert result[0].new_refs[0].address == "203.0.113.50"

    def test_remove_all_maps_to_replace_all_with_no_members(self):
        csv_content = "source_pool,action\n/Common/POOL-A,remove_all\n"
        result = parse_pool_member_rules_csv(
            csv_content, ["/Common/VS-A"], VIPS_BY_NAME, POOLS_BY_NAME
        )
        assert result[0].action == "replace_all"
        assert result[0].new_refs == []

    def test_unknown_pool_raises(self):
        csv_content = "source_pool,action\n/Common/NOT-REAL,remove_all\n"
        with pytest.raises(CsvImportError, match="does not exist"):
            parse_pool_member_rules_csv(csv_content, ["/Common/VS-A"], VIPS_BY_NAME, POOLS_BY_NAME)

    def test_pool_not_used_by_selected_vips_raises(self):
        csv_content = "source_pool,action\n/Common/POOL-B,remove_all\n"
        with pytest.raises(CsvImportError, match="not used by any currently selected VIP"):
            parse_pool_member_rules_csv(csv_content, ["/Common/VS-A"], VIPS_BY_NAME, POOLS_BY_NAME)


class TestParseNodeChangesCsv:
    def test_parses_ip_and_optional_rename(self):
        csv_content = "source_node,new_ip,new_node_name\n/Common/NODE-1,203.0.113.20,/Common/NODE-1-NEW\n"
        result = parse_node_changes_csv(csv_content)
        assert result[0].old_node_ref == "/Common/NODE-1"
        assert result[0].new_ip == "203.0.113.20"
        assert result[0].new_node_name == "/Common/NODE-1-NEW"

    def test_missing_new_ip_raises(self):
        csv_content = "source_node,new_ip\n/Common/NODE-1,\n"
        with pytest.raises(CsvImportError, match="both required"):
            parse_node_changes_csv(csv_content)


def test_empty_csv_raises():
    with pytest.raises(CsvImportError, match="no data rows"):
        parse_node_changes_csv("source_node,new_ip\n")
