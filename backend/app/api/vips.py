import sqlite3
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.deps import get_session_db
from app.graph.builder import build_dependency_graph
from app.models.domain import Vip
from app.models.graph import SelectionCounts
from app.storage.repositories import VipRepository

router = APIRouter(prefix="/api/v1/sessions/{session_id}/vips", tags=["vips"])


class VipListOut(BaseModel):
    items: List[Vip]
    total: int


@router.get("", response_model=VipListOut)
def list_vips(
    session_id: str,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    conn: sqlite3.Connection = Depends(get_session_db),
) -> VipListOut:
    items = VipRepository.list(conn, search=search, limit=limit, offset=offset)
    total = VipRepository.count(conn, search=search)
    return VipListOut(items=items, total=total)


@router.get("/detail", response_model=Vip)
def get_vip_detail(
    session_id: str, name: str, conn: sqlite3.Connection = Depends(get_session_db)
) -> Vip:
    vip = VipRepository.get(conn, name)
    if vip is None:
        raise HTTPException(status_code=404, detail="vip not found")
    return vip


class SelectionRequest(BaseModel):
    vip_names: List[str]


@router.post("/kpis", response_model=SelectionCounts)
def selection_kpis(
    session_id: str,
    body: SelectionRequest,
    conn: sqlite3.Connection = Depends(get_session_db),
) -> SelectionCounts:
    graph = build_dependency_graph(conn)
    return graph.counts_for_selection(body.vip_names)
