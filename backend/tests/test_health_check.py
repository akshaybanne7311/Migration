def test_health_check_runs_and_returns_all_checks(client, ready_session_id: str):
    resp = client.get("/api/v1/sessions/%s/health-check" % ready_session_id)
    assert resp.status_code == 200
    body = resp.json()
    assert body["overall"] in ("CLEAN", "MINOR_FINDINGS", "NEEDS_ATTENTION")
    check_ids = {c["id"] for c in body["checks"]}
    assert check_ids == {
        "pools_without_monitor",
        "pools_all_members_disabled",
        "vips_without_pool",
        "orphaned_nodes",
        "vip_vlan_refs",
        "self_ip_vlan_refs",
        "duplicate_vip_destinations",
        "ntp_configured",
        "dns_configured",
        "snmp_access_scope",
        "ha_group_membership",
        "certificates_expired",
        "certificates_expiring_soon",
        "license_evaluation",
        "duplicate_node_addresses",
        "vip_persistence_refs",
        "vip_irule_refs",
    }
    for c in body["checks"]:
        assert c["severity"] in ("pass", "warn", "blocked")


def test_health_check_flags_duplicate_vip_destination(client, synthetic_conf_text):
    import re

    match = re.search(r"ltm virtual (\S+) \{[^}]*?destination (\S+)[^}]*?\}", synthetic_conf_text, re.DOTALL)
    assert match, "fixture must contain at least one ltm virtual stanza"
    dest = match.group(2)
    dup_stanza = (
        "\nltm virtual /Common/DUP-VIP-TEST {\n"
        "    destination %s\n"
        "    ip-protocol tcp\n"
        "}\n" % dest
    )
    patched = synthetic_conf_text + dup_stanza

    resp = client.post(
        "/api/v1/sessions",
        files={"file": ("synthetic_with_dup.conf", patched.encode(), "text/plain")},
    )
    session_id = resp.json()["id"]
    hc = client.get("/api/v1/sessions/%s/health-check" % session_id).json()
    dup_check = next(c for c in hc["checks"] if c["id"] == "duplicate_vip_destinations")
    assert dup_check["severity"] == "blocked"
    assert dup_check["affected"]


def test_health_check_flags_duplicate_node_address(client, synthetic_conf_text):
    dup_node = "\nltm node /Common/DUP-NODE-TEST {\n    address 10.20.30.11\n    state user-up\n}\n"
    patched = synthetic_conf_text + dup_node

    resp = client.post("/api/v1/sessions", files={"file": ("synthetic_with_dup_node.conf", patched.encode(), "text/plain")})
    session_id = resp.json()["id"]
    hc = client.get("/api/v1/sessions/%s/health-check" % session_id).json()
    check = next(c for c in hc["checks"] if c["id"] == "duplicate_node_addresses")
    assert check["severity"] == "warn"
    assert any("10.20.30.11" in a for a in check["affected"])


def test_health_check_flags_orphaned_persistence_and_irule_refs(client, synthetic_conf_text):
    bogus_stanza = (
        "\nltm virtual /Common/DANGLING-REFS-TEST {\n"
        "    destination /Common/10.99.99.99:9999\n"
        "    ip-protocol tcp\n"
        "    persist {\n"
        "        /Common/NONEXISTENT-PERSIST { }\n"
        "    }\n"
        "    rules {\n"
        "        /Common/NONEXISTENT-IRULE\n"
        "    }\n"
        "}\n"
    )
    patched = synthetic_conf_text + bogus_stanza

    resp = client.post("/api/v1/sessions", files={"file": ("synthetic_with_dangling.conf", patched.encode(), "text/plain")})
    session_id = resp.json()["id"]
    hc = client.get("/api/v1/sessions/%s/health-check" % session_id).json()

    persist_check = next(c for c in hc["checks"] if c["id"] == "vip_persistence_refs")
    assert persist_check["severity"] == "blocked"
    assert any("NONEXISTENT-PERSIST" in a for a in persist_check["affected"])

    irule_check = next(c for c in hc["checks"] if c["id"] == "vip_irule_refs")
    assert irule_check["severity"] == "blocked"
    assert any("NONEXISTENT-IRULE" in a for a in irule_check["affected"])
