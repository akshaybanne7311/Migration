import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("f5ci")

app = FastAPI(title="Config Intelligence API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort safety net: FastAPI's default behavior on an uncaught
    exception is a bare 500 with no body (or a traceback if run with
    --reload's debug page), which is both an unhelpful dead end for
    whoever is driving the wizard and, in production, a way to leak
    internals. Log the real exception server-side, hand the client a
    stable JSON envelope."""
    logger.exception("unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "internal server error", "path": request.url.path},
    )


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "version": app.version}
