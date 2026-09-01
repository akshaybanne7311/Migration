from app.models.validation import Severity, ValidationResult
from app.validation.checks import (
    dependencies,
    duplicates,
    ipv4_syntax,
    ipv6_syntax,
    node_refs,
    pool_members,
    tmsh_syntax,
    vlan_refs,
)
from app.validation.context import ValidationInput


def run_validation(vi: ValidationInput) -> ValidationResult:
    checks = [
        dependencies.check(vi),
        duplicates.check(vi),
        ipv4_syntax.check(vi),
        ipv6_syntax.check(vi),
        vlan_refs.check(vi),
        pool_members.check(vi),
        node_refs.check(vi),
        tmsh_syntax.check(vi),
    ]
    overall = "BLOCKED" if any(c.severity == Severity.BLOCKED for c in checks) else "READY"
    return ValidationResult(checks=checks, overall=overall)
