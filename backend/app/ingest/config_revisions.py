"""Parse TMOS's own numbered config patches (`config/.diffVersions/config/
<file>/<N>.patch`) into structured, timestamped revisions -- a real,
per-save history of what actually changed in bigip.conf/bigip_base.conf/
bigip_user.conf/bigip_script.conf, independent of tmsh shell history and
far more granular (it shows the actual config lines added/removed, not
just the command that was run).

Same secret-handling policy as command history, applied to a different
shape of text: a diff line can carry a real secret value (confirmed on
real data -- an SNMP trap community string appeared in an added line), so
every line is redacted *before* the entry is ever built, not at display
time.
"""
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.models.domain import ConfigRevision

_SECRET_LINE_RE = re.compile(
    r"^(?P<indent>\s*)(?P<keyword>password|passphrase|secret|shared-secret|pre-?shared-key|community|private-key)"
    r"(?P<sep>\s+)(?P<value>\S.*)$",
    re.IGNORECASE,
)


def _redact_line_content(content: str) -> str:
    match = _SECRET_LINE_RE.match(content)
    if not match:
        return content
    return "%s%s%s[REDACTED]" % (match.group("indent"), match.group("keyword"), match.group("sep"))


def _redact_patch_text(text: str) -> tuple:
    out_lines: List[str] = []
    contains_secret = False
    lines_added = 0
    lines_removed = 0
    for line in text.splitlines():
        if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
            out_lines.append(line)
            continue
        if line[:1] in ("+", "-", " "):
            marker, content = line[0], line[1:]
            if marker == "+":
                lines_added += 1
            elif marker == "-":
                lines_removed += 1
            redacted = _redact_line_content(content)
            if redacted != content:
                contains_secret = True
            out_lines.append(marker + redacted)
        else:
            out_lines.append(line)
    return "\n".join(out_lines), contains_secret, lines_added, lines_removed


def parse_config_revision_patches(raw_patches: List[Dict[str, Any]]) -> List[ConfigRevision]:
    revisions: List[ConfigRevision] = []
    for raw in raw_patches:
        diff_text, contains_secret, lines_added, lines_removed = _redact_patch_text(raw["text"])
        timestamp = datetime.fromtimestamp(raw["mtime"], tz=timezone.utc).isoformat()
        revisions.append(
            ConfigRevision(
                config_file=raw["config_file"],
                patch_number=raw["patch_number"],
                timestamp=timestamp,
                lines_added=lines_added,
                lines_removed=lines_removed,
                diff_text=diff_text,
                contains_secret=contains_secret,
            )
        )
    revisions.sort(key=lambda r: (r.config_file, r.patch_number))
    return revisions
