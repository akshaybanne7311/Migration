import sqlite3
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.deps import get_session_db
from app.models.domain import CommandHistoryEntry
from app.storage.repositories import CommandHistoryRepository

router = APIRouter(prefix="/api/v1/sessions/{session_id}/command-history", tags=["command-history"])


class CommandHistoryListOut(BaseModel):
    items: List[CommandHistoryEntry]
    total: int
    total_all: int


@router.get("", response_model=CommandHistoryListOut)
def list_command_history(
    session_id: str,
    mutating_only: bool = Query(default=False),
    user: Optional[str] = Query(default=None),
    conn: sqlite3.Connection = Depends(get_session_db),
) -> CommandHistoryListOut:
    items = CommandHistoryRepository.list(conn, mutating_only=mutating_only, user=user)
    total_all = CommandHistoryRepository.count(conn)
    return CommandHistoryListOut(items=items, total=len(items), total_all=total_all)
