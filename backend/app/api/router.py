from fastapi import APIRouter

from app.api import (
    certificates,
    command_history,
    config_revisions,
    dependency_graph,
    health_check,
    migration,
    monitors,
    nodes,
    pools,
    sessions,
    system_objects,
    traffic_flow,
    vips,
    vlans,
)

api_router = APIRouter()
api_router.include_router(sessions.router)
api_router.include_router(vips.router)
api_router.include_router(pools.router)
api_router.include_router(nodes.router)
api_router.include_router(vlans.router)
api_router.include_router(monitors.router)
api_router.include_router(system_objects.router)
api_router.include_router(command_history.router)
api_router.include_router(config_revisions.router)
api_router.include_router(certificates.router)
api_router.include_router(dependency_graph.router)
api_router.include_router(traffic_flow.router)
api_router.include_router(health_check.router)
api_router.include_router(migration.router)
