from pathlib import Path

import pytest

from app.ingest.ingest_pipeline import parse_bigip_conf
from app.models.domain import ParsedConfig

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def synthetic_conf_text() -> str:
    return (FIXTURES_DIR / "synthetic_bigip.conf").read_text()


@pytest.fixture(scope="session")
def synthetic_ucs_path() -> Path:
    return FIXTURES_DIR / "synthetic.ucs"


@pytest.fixture(scope="session")
def parsed_config(synthetic_conf_text: str) -> ParsedConfig:
    return parse_bigip_conf(synthetic_conf_text)


@pytest.fixture()
def isolated_data_dir(tmp_path, monkeypatch):
    """Point the app's data dir at a throwaway tmp_path for this test only,
    so tests never see another test's (or the real dev server's) session
    data. No connection cache to clear -- session_db never caches
    connections across requests (see storage/session_db.py docstring).
    """
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "registry_db_path", tmp_path / "registry.db")
    monkeypatch.setattr(settings, "sessions_dir", tmp_path / "sessions")
    monkeypatch.setattr(settings, "uploads_dir", tmp_path / "uploads")
    settings.ensure_dirs()
    yield settings


@pytest.fixture()
def client(isolated_data_dir):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def ready_session_id(client, synthetic_ucs_path: Path) -> str:
    with open(synthetic_ucs_path, "rb") as f:
        resp = client.post(
            "/api/v1/sessions",
            files={"file": ("synthetic.ucs", f, "application/octet-stream")},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ready", body
    return body["id"]


@pytest.fixture()
def session_maps(ready_session_id: str):
    """Bundle of everything the change engine / validator / generators need,
    loaded straight from the session DB the same way the API layer does.
    """
    from app.graph.builder import build_dependency_graph
    from app.storage import session_db
    from app.storage.repositories import (
        MonitorRepository,
        NodeRepository,
        PoolRepository,
        VipRepository,
        VlanRepository,
    )

    conn = session_db.open_session_conn(ready_session_id)
    nodes_by_name = {n.name: n for n in NodeRepository.list(conn)}
    pools_by_name = {p.name: p for p in PoolRepository.list(conn)}
    vips_by_name = {v.name: v for v in VipRepository.list(conn)}
    vlans_by_name = {v.name: v for v in VlanRepository.list(conn)}
    monitors_by_name = {m.name: m for m in MonitorRepository.list(conn)}
    graph = build_dependency_graph(conn)
    return {
        "session_id": ready_session_id,
        "conn": conn,
        "nodes_by_name": nodes_by_name,
        "pools_by_name": pools_by_name,
        "vips_by_name": vips_by_name,
        "vlans_by_name": vlans_by_name,
        "monitors_by_name": monitors_by_name,
        "graph": graph,
    }
