from app.models.validation import Severity, ValidationCheck
from app.validation.context import ValidationInput


def check(vi: ValidationInput) -> ValidationCheck:
    affected = []
    renamed_old_names = {rnc.old_node_name for rnc in vi.resolved.resolved_node_changes}

    for rnc in vi.resolved.resolved_node_changes:
        for existing_name, existing_node in vi.nodes_by_name.items():
            if existing_name in renamed_old_names:
                continue
            if existing_node.address == rnc.new_address and existing_name != rnc.new_node_name:
                affected.append(
                    "%s new address %s collides with existing node %s"
                    % (rnc.new_node_name, rnc.new_address, existing_name)
                )

    for node_name in vi.resolved.node_deletions:
        still_used_by = []
        for pool_name, pool in vi.pools_by_name.items():
            # a pool this plan touched has its final member list in
            # pool_effective_members; an untouched pool's real, current
            # members (pool.members) are still authoritative
            effective_members = vi.context.pool_effective_members.get(pool_name)
            members_to_check = effective_members if effective_members is not None else pool.members
            if any(m.node_name == node_name for m in members_to_check):
                still_used_by.append(pool_name)
        if still_used_by:
            affected.append(
                "%s cannot be deleted: still referenced by %s"
                % (node_name, ", ".join(still_used_by))
            )

    severity = Severity.BLOCKED if affected else Severity.PASS
    return ValidationCheck(
        id="node_refs",
        label="Node references",
        severity=severity,
        details=(
            "new node address collides with an existing, unrelated node, or "
            "a node marked for deletion is still referenced elsewhere"
            if affected
            else "node references resolve without collision"
        ),
        affected=affected,
    )
