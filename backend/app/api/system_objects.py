import sqlite3
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.deps import get_session_db
from app.models.domain import SystemObject
from app.storage.repositories import SystemObjectRepository

router = APIRouter(prefix="/api/v1/sessions/{session_id}/system-objects", tags=["system-objects"])


class SystemObjectListOut(BaseModel):
    items: List[SystemObject]
    total: int


@router.get("", response_model=SystemObjectListOut)
def list_system_objects(
    session_id: str, conn: sqlite3.Connection = Depends(get_session_db)
) -> SystemObjectListOut:
    items = SystemObjectRepository.list(conn)
    return SystemObjectListOut(items=items, total=len(items))
