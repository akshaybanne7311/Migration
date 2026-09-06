import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.deps import get_session_db
from app.ingest.archive import extract_archive_member
from app.storage import registry_db
from app.storage.repositories import SystemObjectRepository

router = APIRouter(prefix="/api/v1/sessions/{session_id}/certificates", tags=["certificates"])

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _parse_entries(entries_json: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(entries_json)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


@router.get("/{fingerprint}/download")
def download_certificate(
    session_id: str, fingerprint: str, conn: sqlite3.Connection = Depends(get_session_db)
) -> Response:
    """Returns the original, real PEM certificate file exactly as it exists
    inside the archive -- not the parsed fields. Re-opens the session's
    original archive (kept on disk for the session's lifetime) and pulls the
    exact member back out, so what downloads is byte-for-byte what the
    device had, not a reconstruction from parsed metadata.
    """
    objects = SystemObjectRepository.list(conn)
    match = None
    for obj in objects:
        if obj.object_type != "x509 certificate":
            continue
        entries = _parse_entries(obj.entries_json)
        if entries.get("fingerprint_sha256") == fingerprint:
            match = entries
            break
    if match is None:
        raise HTTPException(status_code=404, detail="certificate not found in this session")

    source_paths: List[str] = match.get("source_paths") or []
    if not source_paths:
        raise HTTPException(status_code=404, detail="no source file was recorded for this certificate")

    record = registry_db.get_session(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="session not found")

    pem_bytes = extract_archive_member(Path(record.original_archive_path), source_paths[0])
    if pem_bytes is None:
        raise HTTPException(
            status_code=404,
            detail="the original archive (or this file inside it) is no longer available",
        )

    label = match.get("subject_cn") or fingerprint[:16]
    filename = _SAFE_FILENAME_RE.sub("_", label) + ".crt"
    return Response(
        content=pem_bytes,
        media_type="application/x-pem-file",
        headers={"Content-Disposition": 'attachment; filename="%s"' % filename},
    )
