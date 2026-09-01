import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.models.change_set import MigrationPlan


def create_plan(conn: sqlite3.Connection, plan: MigrationPlan) -> str:
    plan_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute(
            "INSERT INTO migration_plans (id, step, plan_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (plan_id, 1, plan.model_dump_json(), now, now),
        )
    return plan_id


def update_plan(conn: sqlite3.Connection, plan_id: str, plan: MigrationPlan, step: int = 1) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute(
            "UPDATE migration_plans SET plan_json = ?, step = ?, updated_at = ? WHERE id = ?",
            (plan.model_dump_json(), step, now, plan_id),
        )


def get_plan(conn: sqlite3.Connection, plan_id: str) -> Optional[MigrationPlan]:
    row = conn.execute(
        "SELECT plan_json FROM migration_plans WHERE id = ?", (plan_id,)
    ).fetchone()
    if row is None:
        return None
    return MigrationPlan.model_validate_json(row["plan_json"])


def delete_plan(conn: sqlite3.Connection, plan_id: str) -> None:
    with conn:
        conn.execute("DELETE FROM migration_plans WHERE id = ?", (plan_id,))
