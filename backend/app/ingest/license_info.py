"""Parse the device's real license, software version, and hardware/VE
platform metadata -- three plain-text files (not TMOS config stanzas) that
real UCS/QKView archives carry alongside bigip.conf. `sys provision` in
bigip.conf says which modules are *turned on*; only the license file says
which modules are actually *entitled* and whether the box is running on a
Production or a time-limited Evaluation license -- a real, concrete risk
for anything being planned as a permanent migration target.
"""
import json
import re
from typing import Any, Dict, List

from app.models.domain import SystemObject

_FIELD_RE = re.compile(r"^([A-Za-z][A-Za-z0-9 /_-]*?)\s*:\s+(.*)$")


def _parse_license_text(text: str) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    active_modules: List[str] = []
    for line in text.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        match = _FIELD_RE.match(line)
        if not match:
            continue
        key, value = match.group(1).strip().lower(), match.group(2).strip()
        if key == "active module":
            active_modules.extend(part.strip() for part in value.split("|") if part.strip())
        elif key not in fields:  # first occurrence wins (e.g. "optional module" repeats)
            fields[key] = value
    return {
        "usage": fields.get("usage"),
        "vendor": fields.get("vendor"),
        "platform_id": fields.get("platform id"),
        "registration_key": fields.get("registration key"),
        "licensed_date": fields.get("licensed date"),
        "service_check_date": fields.get("service check date"),
        "active_modules": active_modules,
    }


def _parse_keyvalue_text(text: str, sep: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for line in text.splitlines():
        if sep not in line:
            continue
        key, _, value = line.partition(sep)
        result[key.strip().lower()] = value.strip()
    return result


def license_bundle_to_system_objects(files: Dict[str, str]) -> List[SystemObject]:
    """`files` is exactly what extract_license_and_platform_files() returns
    -- archive path -> decoded text. Historical `bigip.license.<date>`
    backups become one "sys license-history" object per date rather than
    being dropped, since the sequence of Production/Evaluation usage and
    module changes over time is itself real migration-relevant signal."""
    objects: List[SystemObject] = []

    current_license = files.get("config/bigip.license")
    if current_license:
        parsed = _parse_license_text(current_license)
        objects.append(
            SystemObject(object_type="sys license", name="current", entries_json=json.dumps(parsed))
        )

    reg_key_file = files.get("config/RegKey.license")
    if reg_key_file:
        reg = _parse_keyvalue_text(reg_key_file, ":")
        if reg.get("registrationkey"):
            objects.append(
                SystemObject(
                    object_type="sys license",
                    name="registration-key",
                    entries_json=json.dumps({"registration_key": reg["registrationkey"]}),
                )
            )

    for path, text in files.items():
        match = re.match(r"^config/bigip\.license\.(\d{8})$", path)
        if not match:
            continue
        date = match.group(1)
        parsed = _parse_license_text(text)
        parsed["source_path"] = path
        objects.append(
            SystemObject(object_type="sys license-history", name=date, entries_json=json.dumps(parsed))
        )

    version_text = files.get("config/ucs_version")
    if version_text:
        parsed = _parse_keyvalue_text(version_text, ":")
        objects.append(
            SystemObject(object_type="sys software-version", name="", entries_json=json.dumps(parsed))
        )

    platform_text = files.get("config/.ucs_platform")
    if platform_text:
        parsed = _parse_keyvalue_text(platform_text, "=")
        objects.append(
            SystemObject(object_type="sys platform", name="", entries_json=json.dumps(parsed))
        )

    return objects
