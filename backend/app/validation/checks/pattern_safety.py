from app.models.change_set import ChangeType
from app.models.validation import Severity, ValidationCheck
from app.validation.context import ValidationInput

_CHECKED_TYPES = (ChangeType.VIP_NAME, ChangeType.POOL_NAME)


def check(vi: ValidationInput) -> ValidationCheck:
    """A Replace value with no Find pattern is never a useful rename --
    the engine now treats it as a safe no-op rather than corrupting the
    name (str.replace("", x) mangles every character), but a no-op that
    looks like a real, checked change should still be surfaced clearly
    instead of only failing later as a generic "no output" error.
    """
    affected = []
    for vc in vi.resolved.vip_changes:
        for change_type in _CHECKED_TYPES:
            payload = vc.effective.get(change_type)
            if not payload:
                continue
            find = payload.get("find")
            replace = payload.get("replace")
            if replace and not find:
                affected.append(
                    "%s -> %s has a Replace value (%r) but no Find pattern to match, "
                    "so nothing will actually be renamed" % (vc.vip_name, change_type.value, replace)
                )

    severity = Severity.BLOCKED if affected else Severity.PASS
    return ValidationCheck(
        id="pattern_safety",
        label="Find/replace safety",
        severity=severity,
        details=(
            "Replace value set without a matching Find pattern"
            if affected
            else "find/replace patterns are well-formed"
        ),
        affected=affected,
    )
