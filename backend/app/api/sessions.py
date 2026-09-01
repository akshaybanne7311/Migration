import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import settings
from app.ingest.archive import ArchiveError, extract_config_text
from app.ingest.ingest_pipeline import parse_bigip_conf
from app.storage import registry_db, session_db

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


class SessionOut(BaseModel):
    id: str
    name: str
    source_filename: str
    status: str
    error_message: Optional[str] = None
    created_at: str
    vip_count: int = 0
    pool_count: int = 0
    node_count: int = 0
    vlan_count: int = 0


def _to_out(record: registry_db.SessionRecord) -> SessionOut:
    counts = {"vip_count": 0, "pool_count": 0, "node_count": 0, "vlan_count": 0}
    if record.status == "ready":
        try:
            conn = session_db.open_session_conn(record.id)
            try:
                counts["vip_count"] = conn.execute("SELECT COUNT(*) c FROM vips").fetchone()["c"]
                counts["pool_count"] = conn.execute("SELECT COUNT(*) c FROM pools").fetchone()["c"]
                counts["node_count"] = conn.execute("SELECT COUNT(*) c FROM nodes").fetchone()["c"]
                counts["vlan_count"] = conn.execute("SELECT COUNT(*) c FROM vlans").fetchone()["c"]
            finally:
                conn.close()
        except session_db.SessionNotFoundError:
            pass
    return SessionOut(
        id=record.id,
        name=record.name,
        source_filename=record.source_filename,
        status=record.status,
        error_message=record.error_message,
        created_at=record.created_at,
        **counts,
    )


@router.post("", response_model=SessionOut)
async def upload_session(file: UploadFile = File(...)) -> SessionOut:
    session_id = str(uuid.uuid4())
    upload_dir = settings.uploads_dir / session_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    archive_path = upload_dir / (file.filename or "upload.ucs")
    contents = await file.read()
    if len(contents) > settings.max_upload_bytes:
        upload_dir.rmdir()
        raise HTTPException(
            status_code=413,
            detail="file exceeds the %d MB upload limit"
            % (settings.max_upload_bytes // (1024 * 1024)),
        )
    archive_path.write_bytes(contents)

    session_name = Path(file.filename or "session").stem
    db_path = session_db.session_db_path(session_id)
    registry_db.create_session(
        session_id=session_id,
        name=session_name,
        source_filename=file.filename or "upload.ucs",
        original_archive_path=archive_path,
        session_db_path=db_path,
    )

    try:
        text = extract_config_text(archive_path)
        config = parse_bigip_conf(text)
        conn = session_db.create_session_db(session_id)
        try:
            session_db.write_parsed_config(conn, config)
        finally:
            conn.close()
        registry_db.update_status(session_id, "ready")
    except ArchiveError as exc:
        registry_db.update_status(session_id, "failed", str(exc))
    except Exception as exc:  # noqa: BLE001 - surfaced to the user as session status
        registry_db.update_status(session_id, "failed", str(exc))

    record = registry_db.get_session(session_id)
    return _to_out(record)


@router.get("", response_model=List[SessionOut])
def list_sessions() -> List[SessionOut]:
    return [_to_out(r) for r in registry_db.list_sessions()]


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: str) -> SessionOut:
    record = registry_db.get_session(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="session not found")
    return _to_out(record)


@router.delete("/{session_id}")
def delete_session(session_id: str):
    record = registry_db.get_session(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="session not found")

    session_db.delete_session_files(session_id)

    archive_path = Path(record.original_archive_path)
    if archive_path.exists():
        archive_path.unlink()
    if archive_path.parent.exists() and not any(archive_path.parent.iterdir()):
        archive_path.parent.rmdir()

    registry_db.delete_session(session_id)
    return {"deleted": True, "id": session_id}
