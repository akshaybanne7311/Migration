from app.generation.as3_generator import generate_as3
from app.generation.emit_order import build_migration_context
from app.migration.change_engine import resolve
from app.models.change_set import ChangeType, CommonChange, MigrationPlan


def test_as3_lossy_annotations_present_for_unmappable_fields(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        # this VIP has a route domain in the fixture, which AS3 can't model
        selected_vips=["/Common/VS-MNP-BL-SIP-5061-IPv6-RD"],
        common_changes=[
            CommonChange(change_type=ChangeType.PERSISTENCE, payload={"new_persistence": "/Common/source_addr"})
        ],
    )
    resolved = resolve(
        plan,
        session_maps["nodes_by_name"],
        session_maps["pools_by_name"],
        session_maps["vips_by_name"],
        session_maps["graph"],
    )
    context = build_migration_context(
        resolved,
        session_maps["nodes_by_name"],
        session_maps["pools_by_name"],
        session_maps["vips_by_name"],
    )
    output = generate_as3(context, session_maps["vips_by_name"])

    assert output["declaration"]["class"] == "ADC"
    notes_fields = {n["field"] for n in output["x-tmos-notes"]}
    assert "route_domain" in notes_fields
    assert "persistence" in notes_fields


def test_as3_declaration_includes_virtual_service(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        common_changes=[
            CommonChange(change_type=ChangeType.MONITOR, payload={"new_monitor": "/Common/WEB-HTTP-Monitor-New"})
        ],
    )
    resolved = resolve(
        plan,
        session_maps["nodes_by_name"],
        session_maps["pools_by_name"],
        session_maps["vips_by_name"],
        session_maps["graph"],
    )
    context = build_migration_context(
        resolved,
        session_maps["nodes_by_name"],
        session_maps["pools_by_name"],
        session_maps["vips_by_name"],
    )
    output = generate_as3(context, session_maps["vips_by_name"])
    tenant = output["declaration"]["Tenant_Migration"]
    assert tenant["class"] == "Tenant"
    assert "VS-WEB-HTTP-80" in tenant
