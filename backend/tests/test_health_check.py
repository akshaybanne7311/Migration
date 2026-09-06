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
