from app.generation.tmsh_generator import generate_tmsh
from app.models.validation import Severity, ValidationCheck
from app.validation.context import ValidationInput


def check(vi: ValidationInput) -> ValidationCheck:
    text = generate_tmsh(vi.context, vi.vips_by_name)
    lines = [l for l in text.splitlines() if l.strip()]

    has_effective_change = bool(
        vi.context.new_nodes
        or vi.context.pool_effective_members
        or any(vi.context.vip_effective.values())
    )

    problems = []
    if has_effective_change and not lines:
        problems.append("no TMSH lines generated despite an effective change being present")
    for line in lines:
        if not line.startswith("tmsh "):
            problems.append("malformed line: %s" % line)
        if line.count("{") != line.count("}"):
            problems.append("unbalanced braces: %s" % line)

    severity = Severity.BLOCKED if problems else Severity.PASS
    return ValidationCheck(
        id="tmsh_syntax",
        label="TMSH syntax",
        severity=severity,
        details="; ".join(problems) if problems else "generated TMSH is well-formed",
        affected=problems,
    )
