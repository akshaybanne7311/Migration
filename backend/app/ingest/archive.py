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
from typing import Dict, List, Optional

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


_LICENSE_MEMBER_NAMES = (
    "config/bigip.license",
    "config/RegKey.license",
    "config/ucs_version",
    "config/.ucs_platform",
)
_LICENSE_HISTORY_RE = re.compile(r"^config/bigip\.license\.(\d{8})$")


def extract_license_and_platform_files(archive_path: Path) -> Dict[str, str]:
    """The device's real license (module entitlements, Production vs
    Evaluation, licensed/service-check dates), software version/build, and
    hardware platform ID -- three small plain-text files real UCS/QKView
    archives carry that aren't TMOS config stanzas at all, so bigip.conf
    parsing never sees them. Also picks up any `config/bigip.license.<date>`
    backups TMOS keeps from earlier re-licensing events -- confirmed on a
    real archive going back to 2019 -- for a lightweight license history.
    Best-effort, like the other bonus extractors: {} for a raw .conf upload
    or an archive that simply doesn't have these files.
    """
    path = Path(archive_path)
    if path.suffix.lower() == ".conf" or not tarfile.is_tarfile(path):
        return {}
    result: Dict[str, str] = {}
    with tarfile.open(path, "r:*") as tar:
        names = {m.name: m for m in tar.getmembers() if m.isfile()}
        wanted = [n for n in names if n in _LICENSE_MEMBER_NAMES or _LICENSE_HISTORY_RE.match(n)]
        for name in wanted:
            extracted = tar.extractfile(names[name])
            if extracted is None:
                continue
            result[name] = extracted.read().decode("utf-8", errors="replace")
    return result


_DIFF_VERSIONS_PATCH_RE = re.compile(r"^config/\.diffVersions/config/([^/]+)/(\d+)\.patch$")
# BigDB.dat is TMOS's internal runtime key/value database, not
# human-authored config -- it patches on practically every request and
# would drown out every real config change (confirmed on a real archive:
# 246 BigDB.dat patches vs 76 for bigip.conf on the same device). Excluded
# rather than surfaced as noise, the same call already made for tmsh's own
# sleep/echo bookkeeping lines in command history.
_DIFF_VERSIONS_EXCLUDED_FILES = {"BigDB.dat"}


def extract_config_revision_patches(archive_path: Path) -> List[Dict[str, object]]:
    """TMOS keeps a numbered unified-diff patch (`config/.diffVersions/config/
    <file>/<N>.patch`) for every save to bigip.conf/bigip_base.conf/
    bigip_user.conf/bigip_script.conf -- a real, timestamped (via the tar
    member's own mtime) history of exactly what changed in the device's
    config over its lifetime, independent of and more granular than tmsh
    shell history. Confirmed on a real archive: standard `diff -u` format,
    real content (e.g. an SNMP trap community string appearing in an added
    line) -- so this is read but never surfaced un-redacted; redaction
    happens in app/ingest/config_revisions.py, not here.
    """
    path = Path(archive_path)
    if path.suffix.lower() == ".conf" or not tarfile.is_tarfile(path):
        return []
    results: List[Dict[str, object]] = []
    with tarfile.open(path, "r:*") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            match = _DIFF_VERSIONS_PATCH_RE.match(member.name)
            if not match:
                continue
            config_file, patch_number = match.group(1), match.group(2)
            if config_file in _DIFF_VERSIONS_EXCLUDED_FILES:
                continue
            extracted = tar.extractfile(member)
            if extracted is None:
                continue
            results.append(
                {
                    "config_file": config_file,
                    "patch_number": int(patch_number),
                    "mtime": member.mtime,
                    "text": extracted.read().decode("utf-8", errors="replace"),
                }
            )
    return results


def extract_archive_member(archive_path: Path, member_name: str) -> Optional[bytes]:
    """Re-extracts one exact file (by its archive-internal path, e.g. one of
    the `source_paths` recorded on a parsed certificate) so the original
    bytes -- not the parsed-out fields -- can be handed back for download.
    Returns None if the archive or member is gone rather than raising, since
    a session's original archive is deleted when the session is deleted.
    """
    path = Path(archive_path)
    if not path.exists() or not tarfile.is_tarfile(path):
        return None
    with tarfile.open(path, "r:*") as tar:
        try:
            member = tar.getmember(member_name)
        except KeyError:
            return None
        if not member.isfile():
            return None
        extracted = tar.extractfile(member)
        return extracted.read() if extracted is not None else None
