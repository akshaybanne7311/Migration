import sqlite3
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.deps import get_session_db
from app.models.domain import Vlan
from app.storage.repositories import VlanRepository

router = APIRouter(prefix="/api/v1/sessions/{session_id}/vlans", tags=["vlans"])


class VlanListOut(BaseModel):
    items: List[Vlan]
    total: int


@router.get("", response_model=VlanListOut)
def list_vlans(session_id: str, conn: sqlite3.Connection = Depends(get_session_db)) -> VlanListOut:
    items = VlanRepository.list(conn)
    return VlanListOut(items=items, total=len(items))
