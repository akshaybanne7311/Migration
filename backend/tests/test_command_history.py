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
