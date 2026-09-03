"""Builds the pre-generate migration summary from the same resolved plan
and checks the generators and validator already computed -- every count
here is real, never estimated separately from what Generate will actually
emit.
"""
from typing import List

from app.models.change_set import ChangeType, ResolvedMigrationPlan
from app.models.validation import MigrationSummary, Severity, ValidationCheck


def build_migration_summary(
    resolved: ResolvedMigrationPlan,
    checks: List[ValidationCheck],
) -> MigrationSummary:
    vips_selected = len(resolved.vip_changes)
    vips_changed = sum(1 for vc in resolved.vip_changes if vc.effective)
    profiles_affected = sum(1 for vc in resolved.vip_changes if ChangeType.PROFILES in vc.effective)

    pools_affected = len(
        {rpmc.pool_name for rpmc in resolved.resolved_pool_member_changes} | set(resolved.pool_renames.keys())
    )
    nodes_affected = len(
        {rnc.old_node_name for rnc in resolved.resolved_node_changes} | set(resolved.node_deletions)
    )
    vlan_bindings_changed = sum(
        1 for rvc in resolved.resolved_vlan_changes if set(rvc.new_vlans) != set(rvc.old_vlans)
    )

    return MigrationSummary(
        vips_selected=vips_selected,
        vips_changed=vips_changed,
        vips_unchanged=vips_selected - vips_changed,
        pools_affected=pools_affected,
        nodes_affected=nodes_affected,
        profiles_affected=profiles_affected,
        vlan_bindings_changed=vlan_bindings_changed,
        pool_member_edits=len(resolved.resolved_pool_member_changes),
        objects_created=len(resolved.resolved_node_changes),
        objects_modified=vips_changed + pools_affected,
        objects_removed=len(resolved.node_deletions),
        warnings=sum(1 for c in checks if c.severity == Severity.WARN),
        errors=sum(1 for c in checks if c.severity == Severity.BLOCKED),
    )
