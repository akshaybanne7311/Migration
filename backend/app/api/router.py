from fastapi import APIRouter

from app.api import migration, nodes, pools, sessions, vips, vlans

api_router = APIRouter()
api_router.include_router(sessions.router)
api_router.include_router(vips.router)
api_router.include_router(pools.router)
api_router.include_router(nodes.router)
api_router.include_router(vlans.router)
api_router.include_router(migration.router)
