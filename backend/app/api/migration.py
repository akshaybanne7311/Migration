import sqlite3

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.deps import get_session_db
from app.generation.as3_generator import generate_as3
from app.generation.emit_order import build_migration_context
from app.generation.full_recreate import (
    build_full_recreate_units,
    generate_full_recreate_as3,
    generate_full_recreate_rest,
    generate_full_recreate_tmsh,
)
from app.generation.rest_generator import generate_rest
from app.generation.tmsh_generator import generate_tmsh
from app.graph.builder import build_dependency_graph
from app.migration.change_engine import ChangeEngineError, resolve
from app.migration.csv_import import CsvImportError
from app.migration import csv_import as csv_import_module
from app.migration.node_cascade import NodeCascadeError
from app.migration.plan_repository import create_plan, delete_plan, get_plan, update_plan
from app.models.change_set import MigrationPlan, NodeChange, PoolMemberEdit, VipException
from app.models.validation import Severity, ValidationCheck, ValidationResult
from app.storage.repositories import (
    MonitorRepository,
    NodeRepository,
    PoolRepository,
    VipRepository,
    VlanRepository,
)
from app.validation.context import ValidationInput
from app.validation.validator import run_validation

router = APIRouter(
    prefix="/api/v1/sessions/{session_id}/migration-plans", tags=["migration"]
)


def _load_context_maps(conn: sqlite3.Connection):
    nodes_by_name = {n.name: n for n in NodeRepository.list(conn)}
    pools_by_name = {p.name: p for p in PoolRepository.list(conn)}
    vips_by_name = {v.name: v for v in VipRepository.list(conn)}
    vlans_by_name = {v.name: v for v in VlanRepository.list(conn)}
    return nodes_by_name, pools_by_name, vips_by_name, vlans_by_name


def _resolve_or_error(conn: sqlite3.Connection, plan: MigrationPlan):
    nodes_by_name, pools_by_name, vips_by_name, vlans_by_name = _load_context_maps(conn)
    graph = build_dependency_graph(conn)
    try:
        resolved = resolve(plan, nodes_by_name, pools_by_name, vips_by_name, graph)
    except (ChangeEngineError, NodeCascadeError) as exc:
        return None, str(exc), (nodes_by_name, pools_by_name, vips_by_name, vlans_by_name)
    return resolved, None, (nodes_by_name, pools_by_name, vips_by_name, vlans_by_name)


class CsvImportResult(BaseModel):
    exceptions: list[VipException] = []
    node_changes: list[NodeChange] = []
    pool_member_edits: list[PoolMemberEdit] = []
    row_count: int


CSV_TYPES = ("vip_changes", "vlan_rules", "pool_members", "node_changes")


@router.post("/import-csv", response_model=CsvImportResult)
async def import_csv_rules(
    session_id: str,
    csv_type: str = Form(...),
    selected_vips: str = Form(""),
    file: UploadFile = File(...),
    conn: sqlite3.Connection = Depends(get_session_db),
) -> CsvImportResult:
    if csv_type not in CSV_TYPES:
        raise HTTPException(
            status_code=400, detail="csv_type must be one of %s" % ", ".join(CSV_TYPES)
        )

    raw = await file.read()
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV file must be UTF-8 encoded")

    vip_list = [v for v in (s.strip() for s in selected_vips.split(",")) if v]
    nodes_by_name, pools_by_name, vips_by_name, _vlans_by_name = _load_context_maps(conn)

    try:
        if csv_type == "vip_changes":
            exceptions = csv_import_module.parse_vip_changes_csv(content, vips_by_name)
            return CsvImportResult(exceptions=exceptions, row_count=len(exceptions))
        if csv_type == "vlan_rules":
            exceptions = csv_import_module.parse_vlan_rules_csv(content, vip_list)
            return CsvImportResult(exceptions=exceptions, row_count=len(exceptions))
        if csv_type == "pool_members":
            edits = csv_import_module.parse_pool_member_rules_csv(
                content, vip_list, vips_by_name, pools_by_name
            )
            return CsvImportResult(pool_member_edits=edits, row_count=len(edits))
        node_changes = csv_import_module.parse_node_changes_csv(content)
        return CsvImportResult(node_changes=node_changes, row_count=len(node_changes))
    except CsvImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("")
def create_migration_plan(
    session_id: str, plan: MigrationPlan, conn: sqlite3.Connection = Depends(get_session_db)
):
    plan.session_id = session_id
    plan_id = create_plan(conn, plan)
    return {"id": plan_id, "plan": plan}


@router.get("/{plan_id}")
def get_migration_plan(
    session_id: str, plan_id: str, conn: sqlite3.Connection = Depends(get_session_db)
):
    plan = get_plan(conn, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="migration plan not found")
    return {"id": plan_id, "plan": plan}


@router.put("/{plan_id}")
def put_migration_plan(
    session_id: str,
    plan_id: str,
    plan: MigrationPlan,
    step: int = 1,
    conn: sqlite3.Connection = Depends(get_session_db),
):
    existing = get_plan(conn, plan_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="migration plan not found")
    plan.session_id = session_id
    update_plan(conn, plan_id, plan, step=step)
    return {"id": plan_id, "plan": plan}


@router.delete("/{plan_id}")
def delete_migration_plan(
    session_id: str, plan_id: str, conn: sqlite3.Connection = Depends(get_session_db)
):
    existing = get_plan(conn, plan_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="migration plan not found")
    delete_plan(conn, plan_id)
    return {"deleted": True, "id": plan_id}


@router.post("/{plan_id}/validate", response_model=ValidationResult)
def validate_migration_plan(
    session_id: str, plan_id: str, conn: sqlite3.Connection = Depends(get_session_db)
) -> ValidationResult:
    plan = get_plan(conn, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="migration plan not found")

    resolved, error, maps = _resolve_or_error(conn, plan)
    if resolved is None:
        check = ValidationCheck(
            id="plan_resolution",
            label="Plan resolution",
            severity=Severity.BLOCKED,
            details=error or "unresolvable plan",
            affected=[],
        )
        return ValidationResult(checks=[check], overall="BLOCKED")

    nodes_by_name, pools_by_name, vips_by_name, vlans_by_name = maps
    context = build_migration_context(resolved, nodes_by_name, pools_by_name, vips_by_name)
    vi = ValidationInput(
        resolved=resolved,
        context=context,
        nodes_by_name=nodes_by_name,
        pools_by_name=pools_by_name,
        vips_by_name=vips_by_name,
        vlans_by_name=vlans_by_name,
    )
    return run_validation(vi)


@router.post("/{plan_id}/generate")
def generate_migration_outputs(
    session_id: str, plan_id: str, conn: sqlite3.Connection = Depends(get_session_db)
):
    plan = get_plan(conn, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="migration plan not found")

    resolved, error, maps = _resolve_or_error(conn, plan)
    if resolved is None:
        raise HTTPException(status_code=422, detail=error)

    nodes_by_name, pools_by_name, vips_by_name, vlans_by_name = maps
    context = build_migration_context(resolved, nodes_by_name, pools_by_name, vips_by_name)
    vi = ValidationInput(
        resolved=resolved,
        context=context,
        nodes_by_name=nodes_by_name,
        pools_by_name=pools_by_name,
        vips_by_name=vips_by_name,
        vlans_by_name=vlans_by_name,
    )
    validation = run_validation(vi)
    if validation.overall == "BLOCKED":
        raise HTTPException(
            status_code=422,
            detail={"message": "plan is BLOCKED", "validation": validation.model_dump()},
        )

    if plan.output_mode == "full_recreate":
        monitors_by_name = {m.name: m for m in MonitorRepository.list(conn)}
        units = build_full_recreate_units(
            plan.selected_vips, context, nodes_by_name, pools_by_name, vips_by_name, monitors_by_name
        )
        tmsh = generate_full_recreate_tmsh(units)
        rest_calls = generate_full_recreate_rest(units)
        as3 = generate_full_recreate_as3(units)
    else:
        tmsh = generate_tmsh(context, vips_by_name)
        rest_calls = generate_rest(context, vips_by_name)
        as3 = generate_as3(context, vips_by_name, pools_by_name, nodes_by_name)

    return {
        "tmsh": tmsh,
        "rest": [c.model_dump() for c in rest_calls],
        "as3": as3,
        "validation": validation.model_dump(),
        "output_mode": plan.output_mode,
    }
