import sqlite3
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.analysis.health_check import run_health_check
from app.deps import get_session_db
from app.models.validation import Severity, ValidationCheck

router = APIRouter(prefix="/api/v1/sessions/{session_id}/health-check", tags=["health-check"])


class HealthCheckResult(BaseModel):
    checks: List[ValidationCheck]
    overall: str


@router.get("", response_model=HealthCheckResult)
def get_health_check(session_id: str, conn: sqlite3.Connection = Depends(get_session_db)) -> HealthCheckResult:
    checks = run_health_check(conn)
    if any(c.severity == Severity.BLOCKED for c in checks):
        overall = "NEEDS_ATTENTION"
    elif any(c.severity == Severity.WARN for c in checks):
        overall = "MINOR_FINDINGS"
    else:
        overall = "CLEAN"
    return HealthCheckResult(checks=checks, overall=overall)
