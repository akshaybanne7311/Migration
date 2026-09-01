"""VLAN reference check -- the fix for "misleading BLOCKED status for
externally managed F5OS VLANs". A VLAN with no local `net vlan` object is
only ever BLOCKED when the plan explicitly opted into owning VLAN
lifecycle (create_network_objects=True); by default (rSeries/F5OS, where
VLANs are typically externally managed) it is a WARN, never BLOCKED.
"""
from app.models.validation import Severity, ValidationCheck
from app.validation.context import ValidationInput


def check(vi: ValidationInput) -> ValidationCheck:
    warned = []
    blocked = []

    for vip_name, effective in vi.context.vip_effective.items():
        vlans = effective.get("vlans")
        if not vlans:
            continue
        for vlan_name in vlans:
            if vlan_name in vi.vlans_by_name:
                continue
            if vi.context.create_network_objects:
                blocked.append("%s -> %s" % (vip_name, vlan_name))
            else:
                warned.append("%s -> %s" % (vip_name, vlan_name))

    if blocked:
        return ValidationCheck(
            id="vlan_refs",
            label="VLAN references",
            severity=Severity.BLOCKED,
            details="VLAN(s) missing a local net vlan object while "
            "create_network_objects is enabled",
            affected=blocked,
        )
    if warned:
        return ValidationCheck(
            id="vlan_refs",
            label="VLAN references",
            severity=Severity.WARN,
            details="externally managed (rSeries/F5OS) -- no local net vlan "
            "object expected",
            affected=warned,
        )
    return ValidationCheck(
        id="vlan_refs",
        label="VLAN references",
        severity=Severity.PASS,
        details="all VLAN references resolve locally",
        affected=[],
    )
