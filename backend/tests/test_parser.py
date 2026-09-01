from app.ingest.parser import parse_text
from app.models.domain import ParsedConfig  # noqa: F401  (typing context for readers)


def test_bare_word_list_disambiguation():
    stanzas = parse_text(
        "ltm virtual /Common/v1 {\n"
        "    destination /Common/10.1.1.1:443\n"
        "    vlans {\n"
        "        /Common/vlan-a\n"
        "        /Common/vlan-b\n"
        "    }\n"
        "}\n"
    )
    assert len(stanzas) == 1
    vlans = stanzas[0].entries["vlans"]
    assert vlans == ["/Common/vlan-a", "/Common/vlan-b"]


def test_keyed_block_disambiguation():
    stanzas = parse_text(
        "ltm virtual /Common/v1 {\n"
        "    destination /Common/10.1.1.1:443\n"
        "    profiles {\n"
        "        http { context all }\n"
        "        tcp { }\n"
        "    }\n"
        "}\n"
    )
    profiles = stanzas[0].entries["profiles"]
    assert set(profiles.keys()) == {"http", "tcp"}
    assert profiles["http"] == {"context": "all"}
    assert profiles["tcp"] == {}


def test_flag_key_with_no_value():
    stanzas = parse_text(
        "ltm virtual /Common/v1 {\n"
        "    destination /Common/10.1.1.1:443\n"
        "    vlans-enabled\n"
        "}\n"
    )
    assert stanzas[0].entries["vlans-enabled"] is None


def test_scalar_key_value_pairs_not_misread_as_list():
    stanzas = parse_text(
        "ltm node /Common/n1 {\n"
        "    address 10.1.1.1\n"
        "    state user-up\n"
        "}\n"
    )
    entries = stanzas[0].entries
    assert entries["address"] == "10.1.1.1"
    assert entries["state"] == "user-up"


def test_compound_monitor_min_of_value():
    stanzas = parse_text(
        "ltm pool /Common/p1 {\n"
        "    monitor min 1 of {\n"
        "        /Common/m1\n"
        "        /Common/m2\n"
        "    }\n"
        "}\n"
    )
    monitor = stanzas[0].entries["monitor"]
    assert monitor["_prefix"] == ["min", "1", "of"]
    assert monitor["_block"] == ["/Common/m1", "/Common/m2"]


def test_pool_member_keyed_block_with_colon_port_in_key():
    stanzas = parse_text(
        "ltm pool /Common/p1 {\n"
        "    members {\n"
        "        /Common/node1:80 {\n"
        "            address 10.1.1.1\n"
        "            session monitor-enabled\n"
        "        }\n"
        "    }\n"
        "}\n"
    )
    members = stanzas[0].entries["members"]
    assert "/Common/node1:80" in members
    assert members["/Common/node1:80"]["address"] == "10.1.1.1"
    assert members["/Common/node1:80"]["session"] == "monitor-enabled"


def test_object_type_and_name_multiword_type():
    stanzas = parse_text(
        "ltm monitor http /Common/custom-http {\n"
        "    interval 5\n"
        "    timeout 16\n"
        "}\n"
    )
    assert stanzas[0].object_type == "ltm monitor http"
    assert stanzas[0].object_name == "/Common/custom-http"


def test_quoted_description_with_space():
    stanzas = parse_text(
        'ltm virtual /Common/v1 {\n'
        '    description "hello world"\n'
        '    destination /Common/10.1.1.1:443\n'
        "}\n"
    )
    assert stanzas[0].entries["description"] == "hello world"


def test_full_fixture_parses_expected_object_counts(synthetic_conf_text: str):
    stanzas = parse_text(synthetic_conf_text)
    by_type = {}
    for s in stanzas:
        by_type.setdefault(s.object_type, []).append(s)

    assert len(by_type["ltm node"]) == 7
    assert len(by_type["ltm pool"]) == 4
    assert len(by_type["ltm virtual"]) == 6
    assert len(by_type["net vlan"]) == 2
    assert len(by_type["ltm monitor udp"]) == 1
    assert len(by_type["ltm monitor http"]) == 1
