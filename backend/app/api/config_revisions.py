import sqlite3
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.deps import get_session_db
from app.models.domain import ConfigRevision
from app.storage.repositories import ConfigRevisionRepository

router = APIRouter(prefix="/api/v1/sessions/{session_id}/config-revisions", tags=["config-revisions"])


class ConfigRevisionListOut(BaseModel):
    items: List[ConfigRevision]
    total: int
    total_all: int
    config_files: List[str]


@router.get("", response_model=ConfigRevisionListOut)
def list_config_revisions(
    session_id: str,
    config_file: Optional[str] = Query(default=None),
    conn: sqlite3.Connection = Depends(get_session_db),
) -> ConfigRevisionListOut:
    items = ConfigRevisionRepository.list(conn, config_file=config_file)
    total_all = ConfigRevisionRepository.count(conn)
    config_files = ConfigRevisionRepository.config_files(conn)
    return ConfigRevisionListOut(items=items, total=len(items), total_all=total_all, config_files=config_files)
