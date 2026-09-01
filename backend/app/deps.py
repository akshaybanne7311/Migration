import sqlite3
from typing import Iterator

from fastapi import HTTPException

from app.storage import registry_db, session_db


def get_session_db(session_id: str) -> Iterator[sqlite3.Connection]:
    record = registry_db.get_session(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="session not found")
    if record.status != "ready":
        raise HTTPException(
            status_code=409,
            detail="session is not ready (status=%s)" % record.status,
        )
    try:
        conn = session_db.open_session_conn(session_id)
    except session_db.SessionNotFoundError:
        raise HTTPException(status_code=404, detail="session not found")

    try:
        yield conn
    finally:
        conn.close()
