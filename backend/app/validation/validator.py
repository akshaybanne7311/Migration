from app.models.validation import Severity, ValidationResult
from app.validation.checks import (
    dependencies,
    duplicates,
    ipv4_syntax,
    ipv6_syntax,
    monitor_refs,
    node_refs,
    pattern_safety,
    pool_members,
    tmsh_syntax,
    vlan_refs,
)
from app.validation.context import ValidationInput
from app.validation.summary import build_migration_summary


def run_validation(vi: ValidationInput) -> ValidationResult:
    checks = [
        dependencies.check(vi),
        duplicates.check(vi),
        ipv4_syntax.check(vi),
        ipv6_syntax.check(vi),
        vlan_refs.check(vi),
        pool_members.check(vi),
        node_refs.check(vi),
        monitor_refs.check(vi),
        pattern_safety.check(vi),
        tmsh_syntax.check(vi),
    ]
    overall = "BLOCKED" if any(c.severity == Severity.BLOCKED for c in checks) else "READY"
    summary = build_migration_summary(vi.resolved, checks)
    return ValidationResult(checks=checks, overall=overall, summary=summary)
