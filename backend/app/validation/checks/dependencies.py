from app.models.validation import Severity, ValidationCheck
from app.validation.context import ValidationInput


def check(vi: ValidationInput) -> ValidationCheck:
    affected = []

    for vip_name, effective in vi.context.vip_effective.items():
        vip = vi.vips_by_name[vip_name]
        pool_name = effective.get("pool_name") or vip.pool_name
        if pool_name and pool_name not in vi.pools_by_name and pool_name not in vi.context.pool_effective_members:
            affected.append("%s -> pool %s" % (vip_name, pool_name))

    for pool_name, members in vi.context.pool_effective_members.items():
        for m in members:
            if not m.is_new_node and m.node_name not in vi.nodes_by_name and m.node_name not in vi.context.new_nodes:
                affected.append("%s -> node %s" % (pool_name, m.node_name))

    severity = Severity.BLOCKED if affected else Severity.PASS
    return ValidationCheck(
        id="dependencies",
        label="Dependencies",
        severity=severity,
        details="unresolved reference(s) found" if affected else "all references resolve",
        affected=affected,
    )
