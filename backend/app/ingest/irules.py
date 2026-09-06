"""Extract iRule TCL script bodies verbatim.

`ltm rule NAME { <TCL script> }` is NOT TMOS key-value syntax -- it's an
opaque TCL script that happens to be brace-delimited the same way TMOS
stanzas are. Running it through the generic tokenizer/parser (which treats
every `{`/`}` as block structure) shreds the script into a meaningless
nested dict and loses the actual logic (confirmed on real iRules: a
20-line if/else script collapses to a single `{"when": ...}` entry).
Since valid TCL requires balanced braces, a depth counter over the raw
text correctly finds the real end of the script -- this bypasses the
tokenizer entirely and captures the script as-is, which is what a
migration actually needs (you can't recreate a VIP's traffic behavior on
a new device without the real iRule body).

A naive counter breaks on real-world iRules though: a `#`-comment or a
quoted string can contain a lone, prose `{` or `}` with no matching
partner (e.g. `# note: opening brace {` or `log local0. "missing close {"`)
-- counted literally, that throws the depth off and either truncates the
script early or swallows the next iRule into it. So comments (a `#` that
starts a line, ignoring leading whitespace -- the common iRule style) and
double-quoted strings are skipped over without counting braces inside
them, without needing a full TCL parser.
"""
import re
from typing import Dict, Optional

_RULE_HEADER = re.compile(r"^ltm rule (\S+)\s*\{", re.MULTILINE)


def _find_matching_brace(text: str, start: int) -> Optional[int]:
    """`start` is the index just after the opening `{`. Returns the index
    just past the matching `}`, or None if the braces never balance."""
    depth = 1
    i = start
    n = len(text)
    at_line_start = True  # only whitespace seen since the last newline so far
    while i < n and depth > 0:
        ch = text[i]
        if ch == "#" and at_line_start:
            nl = text.find("\n", i)
            i = n if nl == -1 else nl + 1
            at_line_start = True
            continue
        if ch == '"':
            i += 1
            while i < n and text[i] != '"':
                i += 2 if text[i] == "\\" and i + 1 < n else 1
            i += 1  # consume closing quote (or run off the end, harmless)
            at_line_start = False
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == "\n":
            at_line_start = True
            i += 1
            continue
        elif ch not in " \t\r":
            at_line_start = False
        i += 1
    return i if depth == 0 else None


def extract_irule_scripts(text: str) -> Dict[str, str]:
    scripts: Dict[str, str] = {}
    for match in _RULE_HEADER.finditer(text):
        name = match.group(1)
        start = match.end()  # just past the opening "{"
        end = _find_matching_brace(text, start)
        if end is None:
            # Unbalanced braces (malformed/truncated export) -- skip rather
            # than guess at a boundary and hand back a silently-truncated
            # script.
            continue
        body = text[start : end - 1]
        scripts[name] = body.strip("\n")
    return scripts
