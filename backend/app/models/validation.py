from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class Severity(str, Enum):
    PASS = "pass"
    WARN = "warn"
    BLOCKED = "blocked"


class ValidationCheck(BaseModel):
    id: str
    label: str
    severity: Severity
    details: str = ""
    affected: List[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    checks: List[ValidationCheck] = Field(default_factory=list)
    overall: str = "READY"
