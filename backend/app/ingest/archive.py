"""Extract the TMOS config text out of a UCS or QKView archive.

UCS/QKView archives are tar(.gz) files that split TMOS config across two
files: `config/bigip.conf` holds LTM/APM/security objects (virtuals, pools,
monitors, ...), while `config/bigip_base.conf` holds the *network and
system* layer -- VLANs, self IPs, trunks, routes, route domains, hostname,
NTP, management IP. A device's VLANs/self-IPs live in bigip_base.conf, not
bigip.conf; verified against real UCS/QKView samples where bigip.conf alone
parsed 0 VLANs even though the device clearly had them configured, and
bigip_base.conf turned out to hold 4 vlans / 11 self IPs / 3 trunks for
that same device. Both are concatenated into one text so the parser sees
every object regardless of which file it lives in. QKView layout varies by
F5 tooling version; this uses filename-pattern matching rather than one
hardcoded path.
"""
import re
import tarfile
from pathlib import Path
from typing import Dict, List

_MEMBER_SUFFIXES = ("config/bigip_base.conf", "config/bigip.conf", "config/bigip_user.conf")
_FALLBACK_SUFFIX = "bigip.conf"


class ArchiveError(Exception):
    pass


def _find_all_members(names: List[str]) -> List[str]:
    found = []
    for suffix in _MEMBER_SUFFIXES:
        for name in names:
            if name.endswith(suffix) and name not in found:
                found.append(name)
                break
    if found:
        return found
    for name in names:
        if name.endswith(_FALLBACK_SUFFIX):
            return [name]
    raise ArchiveError(
        "no bigip.conf-like file found in archive (looked for: %s)"
        % ", ".join(_MEMBER_SUFFIXES + (_FALLBACK_SUFFIX,))
    )


def extract_config_text(archive_path: Path) -> str:
    path = Path(archive_path)

    if path.suffix.lower() == ".conf":
        return path.read_text(errors="replace")

    if not tarfile.is_tarfile(path):
        raise ArchiveError("%s is not a recognized UCS/QKView (tar) archive" % path)

    with tarfile.open(path, "r:*") as tar:
        names = [m.name for m in tar.getmembers() if m.isfile()]
        member_names = _find_all_members(names)
        texts = []
        for member_name in member_names:
            extracted = tar.extractfile(member_name)
            if extracted is None:
                raise ArchiveError("could not read %s from archive" % member_name)
            texts.append(extracted.read().decode("utf-8", errors="replace"))
        return "\n".join(texts)


_TMSH_HISTORY_RE = re.compile(r"\.tmsh-history-(\S+)$")


def extract_command_history(archive_path: Path) -> Dict[str, str]:
    """Every `.tmsh-history-<user>` file in the archive, keyed by username.

    These are TMOS's own per-user shell history for the tmsh CLI --
    `[Mon DD HH:MM:SS] <command>` per line, real timestamps, real commands
    (confirmed on real QKViews: actual `create`/`modify`/`save sys config`
    entries alongside routine monitoring `show`/`list` noise). Best-effort:
    a raw `.conf` upload or an archive that simply doesn't have these files
    (older TMOS, or a UCS that never captured `/home`) returns {} rather
    than failing the whole upload -- this is bonus data, not required for
    the app's core parsing.
    """
    path = Path(archive_path)
    if path.suffix.lower() == ".conf" or not tarfile.is_tarfile(path):
        return {}
    result: Dict[str, str] = {}
    with tarfile.open(path, "r:*") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            match = _TMSH_HISTORY_RE.search(member.name)
            if not match:
                continue
            user = match.group(1)
            extracted = tar.extractfile(member)
            if extracted is None:
                continue
            result[user] = extracted.read().decode("utf-8", errors="replace")
    return result


_CERT_PATH_HINTS = ("ssl.crt/", "certificate_d/")
_PEM_CERT_HEADER = b"-----BEGIN CERTIFICATE-----"


def extract_certificate_files(archive_path: Path) -> Dict[str, bytes]:
    """Every real PEM-encoded X.509 certificate file in the archive, keyed
    by its path inside the archive. `cm cert` stanzas in bigip.conf only
    carry a cache-path/checksum/revision -- no expiration date, since that's
    a property of the actual certificate bytes, not the TMOS object. The
    real cert files live elsewhere in the archive (config/ssl/ssl.crt/ and
    the filestore certificate_d/ paths) and are genuinely parseable PEM.
    Filters by path hint first (cheap), then confirms by content (a real
    PEM header) before accepting -- path naming isn't reliable enough alone
    (filestore entries have no .crt suffix on their own, e.g.
    ":Common:f5_api_com.crt_79943_1").
    """
    path = Path(archive_path)
    if path.suffix.lower() == ".conf" or not tarfile.is_tarfile(path):
        return {}
    result: Dict[str, bytes] = {}
    with tarfile.open(path, "r:*") as tar:
        for member in tar.getmembers():
            if not member.isfile() or member.size == 0 or member.size > 1_000_000:
                continue
            if not any(hint in member.name for hint in _CERT_PATH_HINTS):
                continue
            extracted = tar.extractfile(member)
            if extracted is None:
                continue
            content = extracted.read()
            if content.lstrip().startswith(_PEM_CERT_HEADER):
                result[member.name] = content
    return result
