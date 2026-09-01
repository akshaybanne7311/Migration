import sqlite3
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.deps import get_session_db
from app.graph.builder import build_dependency_graph
from app.models.domain import Node
from app.storage.repositories import NodeRepository

router = APIRouter(prefix="/api/v1/sessions/{session_id}/nodes", tags=["nodes"])


class NodeOut(Node):
    pool_count: int = 0
    vip_count: int = 0


class NodeListOut(BaseModel):
    items: List[NodeOut]
    total: int


@router.get("", response_model=NodeListOut)
def list_nodes(session_id: str, conn: sqlite3.Connection = Depends(get_session_db)) -> NodeListOut:
    graph = build_dependency_graph(conn)
    items = []
    for node in NodeRepository.list(conn):
        pools = graph.pools_using_node(node.name)
        vips = graph.vips_using_node(node.name)
        items.append(NodeOut(**node.model_dump(), pool_count=len(pools), vip_count=len(vips)))
    return NodeListOut(items=items, total=len(items))


@router.get("/detail", response_model=NodeOut)
def get_node_detail(
    session_id: str, name: str, conn: sqlite3.Connection = Depends(get_session_db)
) -> NodeOut:
    node = NodeRepository.get(conn, name)
    if node is None:
        raise HTTPException(status_code=404, detail="node not found")
    graph = build_dependency_graph(conn)
    pools = graph.pools_using_node(node.name)
    vips = graph.vips_using_node(node.name)
    return NodeOut(**node.model_dump(), pool_count=len(pools), vip_count=len(vips))
