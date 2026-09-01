from pathlib import Path

import pytest


def test_create_list_get_session(client, synthetic_ucs_path: Path):
    with open(synthetic_ucs_path, "rb") as f:
        resp = client.post(
            "/api/v1/sessions",
            files={"file": ("synthetic.ucs", f, "application/octet-stream")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["vip_count"] == 6
    assert body["pool_count"] == 4
    assert body["node_count"] == 8
    assert body["vlan_count"] == 2
    session_id = body["id"]

    listed = client.get("/api/v1/sessions").json()
    assert any(s["id"] == session_id for s in listed)

    detail = client.get("/api/v1/sessions/%s" % session_id)
    assert detail.status_code == 200
    assert detail.json()["id"] == session_id


def test_delete_session_purges_db_file_and_registry_row(client, ready_session_id: str):
    from app.storage import session_db

    db_path = session_db.session_db_path(ready_session_id)
    assert db_path.exists()

    resp = client.delete("/api/v1/sessions/%s" % ready_session_id)
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

    assert not db_path.exists()
    with pytest.raises(session_db.SessionNotFoundError):
        session_db.open_session_conn(ready_session_id)

    listed = client.get("/api/v1/sessions").json()
    assert all(s["id"] != ready_session_id for s in listed)


def test_get_deleted_session_returns_404_not_reopened(client, ready_session_id: str):
    client.delete("/api/v1/sessions/%s" % ready_session_id)

    detail = client.get("/api/v1/sessions/%s" % ready_session_id)
    assert detail.status_code == 404

    vips = client.get("/api/v1/sessions/%s/vips" % ready_session_id)
    assert vips.status_code == 404


def test_unknown_session_id_returns_404(client):
    resp = client.get("/api/v1/sessions/does-not-exist")
    assert resp.status_code == 404
    resp2 = client.get("/api/v1/sessions/does-not-exist/vips")
    assert resp2.status_code == 404


def test_oversized_upload_rejected_with_413(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "max_upload_bytes", 10)
    resp = client.post(
        "/api/v1/sessions",
        files={"file": ("big.ucs", b"x" * 100, "application/octet-stream")},
    )
    assert resp.status_code == 413

    listed = client.get("/api/v1/sessions").json()
    assert listed == []  # rejected upload must not leave a registry row behind


def test_health_endpoint(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
