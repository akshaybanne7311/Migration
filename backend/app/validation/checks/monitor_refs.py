from app.models.validation import Severity, ValidationCheck
from app.validation.context import ValidationInput


def check(vi: ValidationInput) -> ValidationCheck:
    """Only checks monitor names this plan is actually setting (via the
    monitor change type) -- an existing VIP's untouched monitor reference
    is left as-is by every generator, so re-validating it here would just
    flag pre-existing device state this migration never claims to fix.
    """
    affected = []
    for vip_name, effective in vi.context.vip_effective.items():
        monitor_names = effective.get("monitor_names")
        if not monitor_names:
            continue
        for name in monitor_names:
            if name not in vi.monitors_by_name:
                affected.append("%s -> monitor %s" % (vip_name, name))

    severity = Severity.BLOCKED if affected else Severity.PASS
    return ValidationCheck(
        id="monitor_refs",
        label="Monitor references",
        severity=severity,
        details="unresolved monitor reference(s)" if affected else "monitor references resolve",
        affected=affected,
    )
