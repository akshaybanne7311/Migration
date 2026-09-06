"""Parse tmsh shell history into structured, timestamped command entries.

Real format confirmed on real QKViews: `[Mon DD HH:MM:SS] <command>` per
line (no year -- tmsh's own history file doesn't record one). Most lines
are routine monitoring noise the CLI itself generates on every prompt
redraw (`show cm failover-status`, `sleep`, `echo`, blank) repeated every
few minutes for months -- real files run past 400K characters, almost
entirely this. Only the *mutating* commands (create/modify/delete/save/...)
are what a migration or incident review actually cares about, so each
entry is flagged rather than making the caller re-derive it.
"""
import re
from typing import List

from app.models.domain import CommandHistoryEntry

_LINE_RE = re.compile(r"^\[(?P<ts>[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\]\s*(?P<cmd>.*)$")

# The tmsh CLI itself injects "sleep"/"echo" between real commands for
# prompt/redraw bookkeeping -- not something the user typed, never useful.
_NOISE_COMMANDS = {"sleep", "echo", ""}

# First word of the command -> whether it actually changes device state.
# Everything else (show/list/tmsh's many read-only verbs, bash builtins
# like "route"/"bash" the user dropped to a shell for) is left as
# non-mutating rather than guessed at.
_MUTATING_VERBS = {
    "create",
    "modify",
    "delete",
    "save",
    "load",
    "install",
    "reset",
    "reboot",
    "edit",
    "move",
    "run",
    "reload",
    "upgrade",
    "enable",
    "disable",
    "restart",
    "flush",
    "generate",
    "publish",
    "revoke",
    "shutdown",
    "start",
    "stop",
    "sync",
}


def _is_mutating(command: str) -> bool:
    first_word = command.strip().split(" ", 1)[0].lower() if command.strip() else ""
    return first_word in _MUTATING_VERBS


# Real tmsh history has been observed containing the literal secret value on
# the command line (e.g. an admin ran `modify auth password <newpass>`
# instead of the interactive prompt) -- shell history captures exactly what
# was typed, keystrokes included. Everything after one of these keywords is
# redacted *before* the entry is ever built, so the plaintext is never
# stored in the session DB or returned by the API, only the fact that a
# credential was changed, by whom, and when.
_SECRET_KEYWORD_RE = re.compile(
    r"\b(password|passphrase|secret|shared-secret|pre-?shared-key|community|private-key)\b",
    re.IGNORECASE,
)


def _redact_secret(command: str) -> str:
    match = _SECRET_KEYWORD_RE.search(command)
    if not match:
        return command
    return command[: match.end()] + " [REDACTED]"


def parse_command_history(raw_text: str, user: str) -> List[CommandHistoryEntry]:
    entries: List[CommandHistoryEntry] = []
    for line in raw_text.splitlines():
        match = _LINE_RE.match(line)
        if not match:
            continue
        cmd = match.group("cmd").strip()
        if cmd in _NOISE_COMMANDS:
            continue
        contains_secret = bool(_SECRET_KEYWORD_RE.search(cmd))
        entries.append(
            CommandHistoryEntry(
                user=user,
                timestamp=match.group("ts"),
                command=_redact_secret(cmd) if contains_secret else cmd,
                is_mutating=_is_mutating(cmd),
                contains_secret=contains_secret,
            )
        )
    return entries
