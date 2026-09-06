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
import tarfile
from pathlib import Path
from typing import List

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
