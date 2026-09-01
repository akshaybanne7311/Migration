import pytest

from app.ingest.net_address import (
    AddressParseError,
    format_destination,
    is_valid_ip,
    parse_destination,
    parse_node_address,
    split_ref_port,
)
from app.models.domain import AddressFamily


def test_parse_ipv4_destination():
    d = parse_destination("/Common/10.10.10.10:443")
    assert d.address == "10.10.10.10"
    assert d.port == 443
    assert d.family == AddressFamily.IPV4
    assert d.route_domain is None


def test_parse_ipv4_destination_with_route_domain():
    d = parse_destination("/Common/10.10.10.10%1:443")
    assert d.address == "10.10.10.10"
    assert d.port == 443
    assert d.route_domain == 1


def test_parse_ipv6_destination_dot_separator():
    d = parse_destination("/Common/2405:200:642:a699::76.5060")
    assert d.address == "2405:200:642:a699::76"
    assert d.port == 5060
    assert d.family == AddressFamily.IPV6
    assert d.route_domain is None


def test_parse_ipv6_destination_with_route_domain():
    d = parse_destination("/Common/2405:200:642:a699::78%10.5061")
    assert d.address == "2405:200:642:a699::78"
    assert d.port == 5061
    assert d.route_domain == 10


def test_parse_ipv4_mapped_ipv6_edge_case():
    d = parse_destination("/Common/::ffff:192.168.1.1.443")
    assert d.family == AddressFamily.IPV6
    assert d.port == 443
    # ipaddress.IPv6Address canonicalizes ::ffff:192.168.1.1 to hex form;
    # the important assertion is that the split found the real address
    # (which round-trips to the same numeric value), not a mangled one.
    import ipaddress

    assert ipaddress.IPv6Address(d.address) == ipaddress.IPv6Address(
        "::ffff:192.168.1.1"
    )


def test_parse_destination_invalid_address_raises():
    with pytest.raises(AddressParseError):
        parse_destination("/Common/not-an-address:443")


def test_parse_node_address_ipv4():
    address, family = parse_node_address("10.20.30.11")
    assert address == "10.20.30.11"
    assert family == AddressFamily.IPV4


def test_parse_node_address_ipv6():
    address, family = parse_node_address("2405:200:642:a699:22:0:25:1")
    assert address == "2405:200:642:a699:22:0:25:1"
    assert family == AddressFamily.IPV6


def test_parse_node_address_never_carries_port():
    # node addresses have no port at all; passing a bare address must not
    # accidentally treat any trailing digits as a port.
    address, family = parse_node_address("2001:db8::55")
    assert address == "2001:db8::55"
    assert family == AddressFamily.IPV6


def test_split_ref_port_ipv4_named_member():
    name, port = split_ref_port("/Common/WEB-Node-1:80")
    assert name == "/Common/WEB-Node-1"
    assert port == 80


def test_split_ref_port_ipv6_named_member():
    name, port = split_ref_port("/Common/MNP-Node-1:5060")
    assert name == "/Common/MNP-Node-1"
    assert port == 5060


def test_split_ref_port_no_port():
    name, port = split_ref_port("/Common/some-name")
    assert name == "/Common/some-name"
    assert port is None


def test_is_valid_ip():
    assert is_valid_ip("10.1.1.1") is True
    assert is_valid_ip("2001:db8::1") is True
    assert is_valid_ip("MNP-Node-1") is False


def test_format_destination_round_trip_ipv4():
    d = parse_destination("/Common/10.10.10.10%1:443")
    formatted = format_destination(d.address, d.port, d.family, d.route_domain)
    assert formatted == "10.10.10.10%1:443"


def test_format_destination_round_trip_ipv6():
    d = parse_destination("/Common/2405:200:642:a699::76.5060")
    formatted = format_destination(d.address, d.port, d.family, d.route_domain)
    assert formatted == "2405:200:642:a699::76.5060"


def test_format_destination_never_emits_bogus_ipv6_colon_port():
    formatted = format_destination("2001:db8::55", 5060, AddressFamily.IPV6)
    assert formatted == "2001:db8::55.5060"
    assert not formatted.endswith(":5060")
