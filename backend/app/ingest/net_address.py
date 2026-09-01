"""IPv4/IPv6 address + port parsing and canonicalization for TMOS objects.

F5 TMOS convention (bigip.conf / tmsh): the address/port separator in a
`destination` (and in bare pool-member / node-reference tokens that embed
a port) is `:` for IPv4 and `.` for IPv6 -- because an IPv6 address
already contains `:`. Examples:
    IPv4:              /Common/10.10.10.10:443
    IPv4 + route dom:  /Common/10.10.10.10%1:443
    IPv6:              /Common/2405:200:642:a699::76.5060
    IPv6 + route dom:  /Common/2405:200:642:a699::76%1.5060

Node identity is always the bare canonical address string -- never
"address:port" or "address.port". This module is the single choke point
for that rule: every other module reaches addresses/ports only through
these functions, in both parse and format directions, so encode/decode
cannot drift from each other.
"""
import ipaddress
from dataclasses import dataclass
from typing import Optional, Tuple

from app.models.domain import AddressFamily


class AddressParseError(Exception):
    pass


@dataclass
class ParsedDestination:
    address: str
    port: Optional[int]
    family: AddressFamily
    route_domain: Optional[int] = None


def strip_partition(raw: str) -> str:
    s = raw.strip()
    if s.startswith("/"):
        parts = s[1:].split("/", 1)
        return parts[1] if len(parts) == 2 else parts[0]
    return s


def split_ref_port(raw: str) -> Tuple[str, Optional[int]]:
    """Split a partition-stripped '<name-or-addr><sep><port>' token into
    (name_or_address, port). Uses '.' as the separator when the left side
    looks IPv6-shaped (>=2 colons present), else ':'. port is None if no
    digit suffix is found after the chosen separator.
    """
    colon_count = raw.count(":")
    if colon_count >= 2:
        parts = raw.rsplit(".", 1)
    else:
        parts = raw.rsplit(":", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0], int(parts[1])
    return raw, None


def _split_route_domain(addr_part: str) -> Tuple[str, Optional[int]]:
    if "%" in addr_part:
        addr, rd = addr_part.split("%", 1)
        if rd.isdigit():
            return addr, int(rd)
    return addr_part, None


def parse_destination(raw: str) -> ParsedDestination:
    """Parse a `destination` value from `ltm virtual` into a canonical
    address, port, address family, and optional route domain.
    """
    s = strip_partition(raw)
    name_or_addr, port = split_ref_port(s)
    addr_part, route_domain = _split_route_domain(name_or_addr)
    try:
        ip_obj = ipaddress.ip_address(addr_part)
    except ValueError as exc:
        raise AddressParseError(
            "invalid destination address %r (from %r)" % (addr_part, raw)
        ) from exc
    family = AddressFamily.IPV4 if ip_obj.version == 4 else AddressFamily.IPV6
    return ParsedDestination(
        address=str(ip_obj), port=port, family=family, route_domain=route_domain
    )


def parse_node_address(raw: str) -> Tuple[str, AddressFamily]:
    """Parse a plain `ltm node ... { address <addr> }` value. No port is
    ever involved here -- this is the enforcement point for "node identity
    is the canonical address, never address:port".
    """
    s = strip_partition(raw)
    addr_part, _route_domain = _split_route_domain(s)
    try:
        ip_obj = ipaddress.ip_address(addr_part)
    except ValueError as exc:
        raise AddressParseError("invalid node address %r" % raw) from exc
    family = AddressFamily.IPV4 if ip_obj.version == 4 else AddressFamily.IPV6
    return str(ip_obj), family


def is_valid_ip(raw: str) -> bool:
    try:
        ipaddress.ip_address(raw)
        return True
    except ValueError:
        return False


def format_destination(
    address: str,
    port: Optional[int],
    family: AddressFamily,
    route_domain: Optional[int] = None,
) -> str:
    """Inverse of parse_destination -- used by generators so encode/decode
    can never disagree on separator convention.
    """
    addr = address
    if route_domain is not None:
        addr = "%s%%%d" % (addr, route_domain)
    if port is None:
        return addr
    sep = ":" if family == AddressFamily.IPV4 else "."
    return "%s%s%d" % (addr, sep, port)
