import json

from app.ingest.license_info import license_bundle_to_system_objects

_SAMPLE_LICENSE = """#
Auth vers :                   5b
Usage :                       Production
Vendor :                      F5 Networks, Inc.
active module :               Local Traffic Manager, i4800|RZEXRYJ-MLMRAWB|Rate Shaping|APM, Limited
active module :               Routing Bundle|TDZZBUS-FEINFBF
Licensed date :               20250129
Service check date :          20260313
Registration Key :            PWVMG-HRGZD-BORJQ-GKQZU-EBUHTXX
Platform ID :                 C115
"""

_SAMPLE_EVAL_LICENSE = _SAMPLE_LICENSE.replace("Usage :                       Production", "Usage :                       Evaluation")

_SAMPLE_REGKEY = "RegistrationKey: PWVMG-HRGZD-BORJQ-GKQZU-EBUHTXX\n"

_SAMPLE_VERSION = """Product: BIG-IP
Version: 17.5.1.3
Build: 0.1.19
Edition: Engineering Hotfix
"""

_SAMPLE_PLATFORM = """platform=C115
family=0xF9000000
host=C115
systype=0x9d
"""


def test_parses_current_license_fields_and_flattens_module_list():
    objs = license_bundle_to_system_objects({"config/bigip.license": _SAMPLE_LICENSE})
    current = next(o for o in objs if o.object_type == "sys license" and o.name == "current")
    entries = json.loads(current.entries_json)
    assert entries["usage"] == "Production"
    assert entries["platform_id"] == "C115"
    assert entries["licensed_date"] == "20250129"
    assert entries["service_check_date"] == "20260313"
    assert "Local Traffic Manager, i4800" in entries["active_modules"]
    assert "Routing Bundle" in entries["active_modules"]


def test_registration_key_file_produces_its_own_object():
    objs = license_bundle_to_system_objects({"config/RegKey.license": _SAMPLE_REGKEY})
    reg = next(o for o in objs if o.name == "registration-key")
    entries = json.loads(reg.entries_json)
    assert entries["registration_key"] == "PWVMG-HRGZD-BORJQ-GKQZU-EBUHTXX"


def test_historical_license_backups_become_license_history_objects():
    objs = license_bundle_to_system_objects(
        {
            "config/bigip.license": _SAMPLE_LICENSE,
            "config/bigip.license.20190819": _SAMPLE_EVAL_LICENSE,
        }
    )
    history = [o for o in objs if o.object_type == "sys license-history"]
    assert len(history) == 1
    assert history[0].name == "20190819"
    assert json.loads(history[0].entries_json)["usage"] == "Evaluation"


def test_version_and_platform_files_are_parsed():
    objs = license_bundle_to_system_objects(
        {"config/ucs_version": _SAMPLE_VERSION, "config/.ucs_platform": _SAMPLE_PLATFORM}
    )
    version = next(o for o in objs if o.object_type == "sys software-version")
    platform = next(o for o in objs if o.object_type == "sys platform")
    assert json.loads(version.entries_json)["version"] == "17.5.1.3"
    assert json.loads(platform.entries_json)["platform"] == "C115"


def test_empty_bundle_produces_no_objects():
    assert license_bundle_to_system_objects({}) == []
