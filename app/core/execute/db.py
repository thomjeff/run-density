"""Optional PostgreSQL store for Execute (Issue #922)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def database_url() -> str:
    return (os.environ.get("EXECUTE_DATABASE_URL") or "").strip()


def using_postgres() -> bool:
    return bool(database_url())


def connect():
    import psycopg

    return psycopg.connect(database_url())


def init_schema() -> None:
    if not using_postgres():
        return
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect() as conn:
        for part in sql.split(";"):
            stmt = part.strip()
            if stmt:
                conn.execute(stmt)
        conn.commit()


def registry_from_db() -> Dict[str, Any]:
    init_schema()
    with connect() as conn:
        active = conn.execute(
            "SELECT plan_id FROM execute_active WHERE lock = 1"
        ).fetchone()
        rows = conn.execute("""
            SELECT plan_id, revision, calendar_date, weekday_code, name,
                   source_run_id, archived, imported_at
            FROM execute_plans
            """).fetchall()
    plans = {}
    for row in rows:
        plan_id = str(row[0])
        plans[plan_id] = {
            "plan_id": plan_id,
            "revision": int(row[1]),
            "calendar_date": row[2].isoformat() if row[2] else "",
            "weekday_code": row[3] or "",
            "name": row[4] or "",
            "source_run_id": row[5] or "",
            "archived": bool(row[6]),
            "imported_at": row[7].isoformat() if row[7] else "",
        }
    return {
        "active_plan_id": str(active[0]) if active and active[0] else None,
        "plans": plans,
    }


def save_registry_db(registry: Dict[str, Any]) -> None:
    init_schema()
    active = registry.get("active_plan_id")
    with connect() as conn:
        conn.execute(
            "UPDATE execute_active SET plan_id = %s WHERE lock = 1",
            (active,),
        )
        for plan_id, row in (registry.get("plans") or {}).items():
            conn.execute(
                """
                INSERT INTO execute_plans (
                    plan_id, revision, calendar_date, weekday_code, name,
                    source_run_id, archived, manifest, locations, courses
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    %s::jsonb, %s::jsonb, %s::jsonb
                )
                ON CONFLICT (plan_id) DO UPDATE SET
                    revision = EXCLUDED.revision,
                    calendar_date = EXCLUDED.calendar_date,
                    weekday_code = EXCLUDED.weekday_code,
                    name = EXCLUDED.name,
                    source_run_id = EXCLUDED.source_run_id,
                    archived = EXCLUDED.archived,
                    manifest = COALESCE(
                        EXCLUDED.manifest, execute_plans.manifest
                    ),
                    locations = COALESCE(
                        EXCLUDED.locations, execute_plans.locations
                    ),
                    courses = COALESCE(
                        EXCLUDED.courses, execute_plans.courses
                    )
                """,
                (
                    plan_id,
                    int(row.get("revision") or 1),
                    row.get("calendar_date"),
                    row.get("weekday_code") or "",
                    row.get("name") or "",
                    row.get("source_run_id") or "",
                    bool(row.get("archived")),
                    json.dumps(row.get("manifest") or {}),
                    json.dumps(row.get("locations") or {}),
                    json.dumps(row.get("courses") or {}),
                ),
            )
        conn.commit()


def save_plan_package(
    plan_id: str,
    *,
    manifest: Mapping[str, Any],
    locations: Mapping[str, Any],
    courses: Mapping[str, Any],
) -> None:
    if not using_postgres():
        return
    init_schema()
    with connect() as conn:
        conn.execute(
            """
            UPDATE execute_plans
            SET manifest = %s::jsonb,
                locations = %s::jsonb,
                courses = %s::jsonb
            WHERE plan_id = %s
            """,
            (
                json.dumps(dict(manifest)),
                json.dumps(dict(locations)),
                json.dumps(dict(courses)),
                plan_id,
            ),
        )
        conn.commit()


def load_plan_package(plan_id: str) -> Optional[Dict[str, Any]]:
    if not using_postgres():
        return None
    init_schema()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT manifest, locations, courses
            FROM execute_plans
            WHERE plan_id = %s
            """,
            (plan_id,),
        ).fetchone()
    if not row or not row[0]:
        return None
    return {
        "manifest": dict(row[0]) if isinstance(row[0], dict) else {},
        "locations": dict(row[1]) if isinstance(row[1], dict) else {},
        "courses": dict(row[2]) if isinstance(row[2], dict) else {},
    }


def put_blob(plan_id: str, kind: str, day: str, payload: Any) -> None:
    if not using_postgres():
        return
    init_schema()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO execute_blobs (plan_id, kind, day, payload)
            VALUES (%s, %s, %s, %s::jsonb)
            ON CONFLICT (plan_id, kind, day) DO UPDATE
            SET payload = EXCLUDED.payload
            """,
            (plan_id, kind, day or "", json.dumps(payload)),
        )
        conn.commit()


def get_blob(plan_id: str, kind: str, day: str) -> Optional[Dict[str, Any]]:
    if not using_postgres():
        return None
    init_schema()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT payload FROM execute_blobs
            WHERE plan_id = %s AND kind = %s AND day = %s
            """,
            (plan_id, kind, day or ""),
        ).fetchone()
    if not row:
        return None
    payload = row[0]
    return dict(payload) if isinstance(payload, dict) else None
