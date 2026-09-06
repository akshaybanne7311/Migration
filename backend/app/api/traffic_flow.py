import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import get_session_db
from app.simulation.traffic_flow import TrafficFlowResult, simulate_traffic_flow
from app.storage.repositories import NodeRepository, PoolRepository, VipRepository

router = APIRouter(prefix="/api/v1/sessions/{session_id}/traffic-flow", tags=["traffic-flow"])


def _lb_method(pool_source_stanza_json: str) -> str:
    try:
        entries = json.loads(pool_source_stanza_json)
    except json.JSONDecodeError:
        return "round-robin"
    value = entries.get("load-balancing-mode")
    return value if isinstance(value, str) and value else "round-robin"


@router.get("", response_model=TrafficFlowResult)
def get_traffic_flow(
    session_id: str,
    vip: str = Query(...),
    requests: int = Query(default=10, ge=1, le=200),
    conn: sqlite3.Connection = Depends(get_session_db),
) -> TrafficFlowResult:
    vips_by_name = {v.name: v for v in VipRepository.list(conn)}
    target = vips_by_name.get(vip)
    if target is None:
        raise HTTPException(status_code=404, detail="vip not found in this session's parsed config")

    pools_by_name = {p.name: p for p in PoolRepository.list(conn)}
    pool = pools_by_name.get(target.pool_name) if target.pool_name else None
    lb_method = _lb_method(pool.source_stanza_json) if pool else "round-robin"
    nodes_by_name = {n.name: n for n in NodeRepository.list(conn)}

    return simulate_traffic_flow(target, pool, lb_method, nodes_by_name, request_count=requests)
