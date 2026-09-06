from app.ingest.config_revisions import parse_config_revision_patches

_REAL_STYLE_PATCH = """--- /config/bigip_base.conf	2026-03-24 15:48:13.000000000 +0530
+++ /config/.diffVersions//config/bigip_base.conf/bigip_base.conf	2026-03-24 15:48:02.000000000 +0530
@@ -771,6 +771,10 @@ sys snmp {
     }
     sys-contact prem.gautam@ril.com
     traps {
+        /Common/i10_137_8_112_1 {
+            community OnM4G@Ge0
+            host 10.137.8.112
+        }
     }
"""


def test_parses_timestamp_from_mtime_and_counts_added_removed_lines():
    raw = [{"config_file": "bigip_base.conf", "patch_number": 28369, "mtime": 1774359493.0, "text": _REAL_STYLE_PATCH}]
    revisions = parse_config_revision_patches(raw)
    assert len(revisions) == 1
    r = revisions[0]
    assert r.config_file == "bigip_base.conf"
    assert r.patch_number == 28369
    assert r.timestamp.startswith("2026-")
    assert r.lines_added == 4
    assert r.lines_removed == 0


def test_secret_value_in_a_diff_line_is_redacted_before_storage():
    raw = [{"config_file": "bigip_base.conf", "patch_number": 1, "mtime": 0.0, "text": _REAL_STYLE_PATCH}]
    revisions = parse_config_revision_patches(raw)
    r = revisions[0]
    assert r.contains_secret is True
    assert "OnM4G@Ge0" not in r.diff_text
    assert "community [REDACTED]" in r.diff_text
    # everything else in the diff (headers, hunk markers, unrelated lines)
    # is untouched
    assert "host 10.137.8.112" in r.diff_text
    assert "@@ -771,6 +771,10 @@ sys snmp {" in r.diff_text


def test_patches_without_secrets_are_untouched_and_sorted_by_file_then_number():
    raw = [
        {"config_file": "bigip.conf", "patch_number": 5, "mtime": 0.0, "text": "--- a\n+++ b\n+ltm pool foo { }\n"},
        {"config_file": "bigip.conf", "patch_number": 2, "mtime": 0.0, "text": "--- a\n+++ b\n-ltm pool bar { }\n"},
        {"config_file": "bigip_base.conf", "patch_number": 1, "mtime": 0.0, "text": "--- a\n+++ b\n net vlan x { }\n"},
    ]
    revisions = parse_config_revision_patches(raw)
    assert [(r.config_file, r.patch_number) for r in revisions] == [
        ("bigip.conf", 2),
        ("bigip.conf", 5),
        ("bigip_base.conf", 1),
    ]
    assert all(not r.contains_secret for r in revisions)


def test_empty_patch_list_returns_empty():
    assert parse_config_revision_patches([]) == []
