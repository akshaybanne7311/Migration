from app.models.validation import Severity, ValidationCheck
from app.validation.context import ValidationInput


def check(vi: ValidationInput) -> ValidationCheck:
    affected = []

    new_names = {}
    for vip_name, effective in vi.context.vip_effective.items():
        new_name = effective.get("name")
        if new_name:
            new_names.setdefault(new_name, []).append(vip_name)
    for new_name, sources in new_names.items():
        if len(sources) > 1:
            affected.append("multiple VIPs renamed to %s: %s" % (new_name, ", ".join(sources)))

    target_to_sources = {}
    for rnc in vi.resolved.resolved_node_changes:
        target_to_sources.setdefault(rnc.new_node_name, []).append(rnc.old_node_name)
    for target, sources in target_to_sources.items():
        if len(set(sources)) > 1:
            affected.append(
                "multiple nodes (%s) mapped to the same new node name %s"
                % (", ".join(sources), target)
            )

    pool_target_to_sources = {}
    for old_pool, new_pool in vi.context.pool_renames.items():
        pool_target_to_sources.setdefault(new_pool, []).append(old_pool)
    for target, sources in pool_target_to_sources.items():
        if len(set(sources)) > 1:
            affected.append(
                "multiple pools (%s) renamed to the same new pool name %s"
                % (", ".join(sources), target)
            )

    severity = Severity.BLOCKED if affected else Severity.PASS
    return ValidationCheck(
        id="duplicates",
        label="Duplicate objects",
        severity=severity,
        details="conflicting duplicate target name(s)" if affected else "no duplicate targets",
        affected=affected,
    )
