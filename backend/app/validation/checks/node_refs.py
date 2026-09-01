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

    severity = Severity.BLOCKED if affected else Severity.PASS
    return ValidationCheck(
        id="node_refs",
        label="Node references",
        severity=severity,
        details=(
            "new node address collides with an existing, unrelated node"
            if affected
            else "node references resolve without collision"
        ),
        affected=affected,
    )
