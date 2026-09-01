import ipaddress

from app.models.validation import Severity, ValidationCheck
from app.validation.context import ValidationInput


def check(vi: ValidationInput) -> ValidationCheck:
    affected = []

    for vip_name, effective in vi.context.vip_effective.items():
        vip = vi.vips_by_name[vip_name]
        if vip.address_family.value != "ipv4":
            continue
        addr = effective.get("destination_address")
        if addr is not None:
            try:
                ipaddress.IPv4Address(addr)
            except ValueError:
                affected.append("%s -> destination %s" % (vip_name, addr))
        port = effective.get("destination_port")
        if port is not None and not (0 < port <= 65535):
            affected.append("%s -> port %s" % (vip_name, port))

    severity = Severity.BLOCKED if affected else Severity.PASS
    return ValidationCheck(
        id="ipv4_syntax",
        label="IPv4 syntax",
        severity=severity,
        details="invalid IPv4 destination(s)" if affected else "all IPv4 destinations valid",
        affected=affected,
    )
