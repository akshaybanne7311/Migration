import sqlite3
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.deps import get_session_db
from app.models.domain import Pool
from app.storage.repositories import PoolRepository

router = APIRouter(prefix="/api/v1/sessions/{session_id}/pools", tags=["pools"])


class PoolListOut(BaseModel):
    items: List[Pool]
    total: int


@router.get("", response_model=PoolListOut)
def list_pools(session_id: str, conn: sqlite3.Connection = Depends(get_session_db)) -> PoolListOut:
    items = PoolRepository.list(conn)
    return PoolListOut(items=items, total=len(items))


@router.get("/detail", response_model=Pool)
def get_pool_detail(
    session_id: str, name: str, conn: sqlite3.Connection = Depends(get_session_db)
) -> Pool:
    pool = PoolRepository.get(conn, name)
    if pool is None:
        raise HTTPException(status_code=404, detail="pool not found")
    return pool
