from fastapi import APIRouter

from app.api import command_history, health_check, migration, monitors, nodes, pools, sessions, system_objects, vips, vlans

api_router = APIRouter()
api_router.include_router(sessions.router)
api_router.include_router(vips.router)
api_router.include_router(pools.router)
api_router.include_router(nodes.router)
api_router.include_router(vlans.router)
api_router.include_router(monitors.router)
api_router.include_router(system_objects.router)
api_router.include_router(command_history.router)
api_router.include_router(health_check.router)
api_router.include_router(migration.router)
