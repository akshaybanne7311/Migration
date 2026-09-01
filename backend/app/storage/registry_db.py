"""Registry of sessions -- separate from each session's own SQLite DB.

Kept intentionally tiny: this is the source of truth for "does session X
exist," which is what makes stale-session protection possible (a request
for a deleted/unknown session id 404s from here before any per-session
DB file is ever touched).
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel

from app.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_filename TEXT NOT NULL,
    original_archive_path TEXT NOT NULL,
    session_db_path TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    created_at TEXT NOT NULL
);
"""


class SessionRecord(BaseModel):
    id: str
    name: str
    source_filename: str
    original_archive_path: str
    session_db_path: str
    status: str
    error_message: Optional[str] = None
    created_at: str


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.registry_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
    return conn


def create_session(
    session_id: str,
    name: str,
    source_filename: str,
    original_archive_path: Path,
    session_db_path: Path,
) -> SessionRecord:
    created_at = datetime.now(timezone.utc).isoformat()
    record = SessionRecord(
        id=session_id,
        name=name,
        source_filename=source_filename,
        original_archive_path=str(original_archive_path),
        session_db_path=str(session_db_path),
        status="parsing",
        created_at=created_at,
    )
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions "
            "(id, name, source_filename, original_archive_path, session_db_path, "
            " status, error_message, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.id,
                record.name,
                record.source_filename,
                record.original_archive_path,
                record.session_db_path,
                record.status,
                record.error_message,
                record.created_at,
            ),
        )
    return record


def update_status(session_id: str, status: str, error_message: Optional[str] = None) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET status = ?, error_message = ? WHERE id = ?",
            (status, error_message, session_id),
        )


def get_session(session_id: str) -> Optional[SessionRecord]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return SessionRecord(**dict(row)) if row else None


def list_sessions() -> List[SessionRecord]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
    return [SessionRecord(**dict(r)) for r in rows]


def delete_session(session_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
