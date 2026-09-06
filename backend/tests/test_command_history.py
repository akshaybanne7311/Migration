from app.ingest.command_history import parse_command_history


def test_parses_real_format_and_flags_mutating_commands():
    raw = (
        "[Sep  8 14:38:37] create sys management-route 56.5.65.3/32 gateway 10.59.235.1 \n"
        "[Sep  8 14:38:53] save sys config \n"
        "[Apr 17 13:17:13] sleep\n"
        "[Apr 17 13:17:13] list auth user \n"
        "[Apr 17 13:17:13] echo\n"
    )
    entries = parse_command_history(raw, user="admin")
    assert len(entries) == 3  # sleep/echo dropped as CLI noise
    assert entries[0].command == "create sys management-route 56.5.65.3/32 gateway 10.59.235.1"
    assert entries[0].is_mutating is True
    assert entries[0].user == "admin"
    assert entries[0].timestamp == "Sep  8 14:38:37"
    assert entries[1].command == "save sys config"
    assert entries[1].is_mutating is True
    assert entries[2].command == "list auth user"
    assert entries[2].is_mutating is False


def test_ignores_lines_that_are_not_history_entries():
    raw = "not a history line\n[Jan 1 00:00:00] show sys version\n\n"
    entries = parse_command_history(raw, user="root")
    assert len(entries) == 1
    assert entries[0].command == "show sys version"
    assert entries[0].is_mutating is False


def test_password_typed_on_the_command_line_is_redacted_before_storage():
    raw = "[Apr 19 12:16:49] modify auth password hunter2\n"
    entries = parse_command_history(raw, user="rj55024673")
    assert len(entries) == 1
    assert entries[0].contains_secret is True
    assert "hunter2" not in entries[0].command
    assert entries[0].command == "modify auth password [REDACTED]"


def test_redaction_covers_other_secret_keywords_not_just_password():
    raw = (
        "[Jan 1 00:00:00] create auth radius-server rs1 secret s3cr3t123\n"
        "[Jan 1 00:00:01] modify net tunnels ipsec ike-peer p1 preshared-key mysharedkey\n"
        "[Jan 1 00:00:02] modify sys snmp communities community_1 community-name public123\n"
    )
    entries = parse_command_history(raw, user="admin")
    assert len(entries) == 3
    for e in entries:
        assert e.contains_secret is True
        assert "[REDACTED]" in e.command
    assert "s3cr3t123" not in entries[0].command
    assert "mysharedkey" not in entries[1].command
    assert "public123" not in entries[2].command


def test_commands_without_secret_keywords_are_untouched():
    raw = "[Jan 1 00:00:00] create ltm pool /Common/my-pool\n"
    entries = parse_command_history(raw, user="admin")
    assert entries[0].contains_secret is False
    assert entries[0].command == "create ltm pool /Common/my-pool"
