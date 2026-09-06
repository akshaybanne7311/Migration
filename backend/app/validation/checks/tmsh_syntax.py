from app.generation.full_recreate import build_full_recreate_units, generate_full_recreate_tmsh
from app.generation.tmsh_generator import generate_tmsh
from app.models.validation import Severity, ValidationCheck
from app.validation.context import ValidationInput


def check(vi: ValidationInput) -> ValidationCheck:
    # Real bug this fixes: this check always ran generate_tmsh() (the
    # changes_only generator) regardless of the plan's actual output_mode
    # -- for a full_recreate plan with no field-level changes selected (a
    # valid, common case: "just move these VIPs as-is"), vip_effective is
    # empty, generate_tmsh() produces nothing, and this check trivially
    # passed having validated zero of the dozens of lines
    # generate_full_recreate_tmsh() actually produces for /generate.
    if vi.output_mode == "full_recreate":
        selected_vip_names = [vc.vip_name for vc in vi.resolved.vip_changes]
        units = build_full_recreate_units(
            selected_vip_names, vi.context, vi.nodes_by_name, vi.pools_by_name, vi.vips_by_name, vi.monitors_by_name
        )
        text = generate_full_recreate_tmsh(units)
        has_effective_change = bool(selected_vip_names)
    else:
        text = generate_tmsh(vi.context, vi.vips_by_name)
        has_effective_change = bool(
            vi.context.new_nodes
            or vi.context.pool_effective_members
            or any(vi.context.vip_effective.values())
        )

    lines = [l for l in text.splitlines() if l.strip()]

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
