import ipaddress

from app.models.validation import Severity, ValidationCheck
from app.validation.context import ValidationInput


def check(vi: ValidationInput) -> ValidationCheck:
    affected = []

    for vip_name, effective in vi.context.vip_effective.items():
        vip = vi.vips_by_name[vip_name]
        if vip.address_family.value != "ipv6":
            continue
        addr = effective.get("destination_address")
        if addr is not None:
            try:
                ipaddress.IPv6Address(addr)
            except ValueError:
                affected.append("%s -> destination %s" % (vip_name, addr))
        port = effective.get("destination_port")
        if port is not None and not (0 < port <= 65535):
            affected.append("%s -> port %s" % (vip_name, port))

    for rnc in vi.resolved.resolved_node_changes:
        try:
            ip_obj = ipaddress.ip_address(rnc.new_address)
        except ValueError:
            affected.append("node %s -> %s" % (rnc.new_node_name, rnc.new_address))
            continue
        if ip_obj.version == 6:
            # already canonicalized by net_address.parse_node_address at
            # resolve time; re-check here is defense in depth against a
            # future regression in that path.
            ipaddress.IPv6Address(rnc.new_address)

    severity = Severity.BLOCKED if affected else Severity.PASS
    return ValidationCheck(
        id="ipv6_syntax",
        label="IPv6 syntax",
        severity=severity,
        details="invalid IPv6 destination(s)" if affected else "all IPv6 destinations valid",
        affected=affected,
    )
