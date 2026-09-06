import sqlite3
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.deps import get_session_db
from app.models.domain import Monitor
from app.storage.repositories import MonitorRepository

router = APIRouter(prefix="/api/v1/sessions/{session_id}/monitors", tags=["monitors"])


class MonitorListOut(BaseModel):
    items: List[Monitor]
    total: int


@router.get("", response_model=MonitorListOut)
def list_monitors(session_id: str, conn: sqlite3.Connection = Depends(get_session_db)) -> MonitorListOut:
    items = MonitorRepository.list(conn)
    return MonitorListOut(items=items, total=len(items))
