from app.models.validation import Severity, ValidationCheck
from app.validation.context import ValidationInput


def check(vi: ValidationInput) -> ValidationCheck:
    affected = []

    for pool_name, members in vi.context.pool_effective_members.items():
        original_pool = vi.pools_by_name.get(pool_name)
        had_members = bool(original_pool and original_pool.members)
        if had_members and not members:
            affected.append(pool_name)

    severity = Severity.BLOCKED if affected else Severity.PASS
    return ValidationCheck(
        id="pool_members",
        label="Pool members",
        severity=severity,
        details=(
            "pool(s) resolve to an empty member list despite the source "
            "pool having members"
            if affected
            else "no pool unexpectedly loses all members"
        ),
        affected=affected,
    )
