"""Extract the TMOS config text out of a UCS or QKView archive.

UCS archives are tar(.gz) files with a `config/bigip.conf` (and often a
`config/bigip_base.conf`) inside. QKView layout varies by F5 tooling
version and isn't fully pinned down by the requirements -- this uses a
small filename-pattern locator rather than one hardcoded path, and should
be re-validated against a real QKView sample if one is ever used (open
question carried from the design phase).
"""
import tarfile
from pathlib import Path
from typing import List

_CANDIDATE_SUFFIXES = ("config/bigip.conf", "config/bigip_base.conf", "bigip.conf")


class ArchiveError(Exception):
    pass


def _pick_best_member(names: List[str]) -> str:
    for suffix in _CANDIDATE_SUFFIXES:
        for name in names:
            if name.endswith(suffix):
                return name
    raise ArchiveError(
        "no bigip.conf-like file found in archive (looked for: %s)"
        % ", ".join(_CANDIDATE_SUFFIXES)
    )


def extract_config_text(archive_path: Path) -> str:
    path = Path(archive_path)

    if path.suffix.lower() == ".conf":
        return path.read_text(errors="replace")

    if not tarfile.is_tarfile(path):
        raise ArchiveError("%s is not a recognized UCS/QKView (tar) archive" % path)

    with tarfile.open(path, "r:*") as tar:
        names = [m.name for m in tar.getmembers() if m.isfile()]
        member_name = _pick_best_member(names)
        extracted = tar.extractfile(member_name)
        if extracted is None:
            raise ArchiveError("could not read %s from archive" % member_name)
        return extracted.read().decode("utf-8", errors="replace")
