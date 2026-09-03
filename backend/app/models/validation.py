from enum import Enum
from typing import List, Optional

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


class MigrationSummary(BaseModel):
    """Real counts derived from the same resolved plan the generators read
    from -- never a guess, and always consistent with what Generate will
    actually produce.
    """

    vips_selected: int = 0
    vips_changed: int = 0
    vips_unchanged: int = 0
    pools_affected: int = 0
    nodes_affected: int = 0
    profiles_affected: int = 0
    vlan_bindings_changed: int = 0
    pool_member_edits: int = 0
    objects_created: int = 0
    objects_modified: int = 0
    objects_removed: int = 0
    warnings: int = 0
    errors: int = 0


class ValidationResult(BaseModel):
    checks: List[ValidationCheck] = Field(default_factory=list)
    overall: str = "READY"
    summary: Optional[MigrationSummary] = None
