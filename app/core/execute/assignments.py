"""Day Plan device assignments (Issue #928).

Device id is ingest identity. Resource name, person, phone, and
agency belong to one Day Plan. Saturday and Sunday stay isolated.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from app.core.execute.published_plan import (
    PublishedPlanError,
    assert_uuid,
    execute_store_root,
    load_registry,
)


class AssignmentError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def assignments_path(
    plan_id: str,
    root: Optional[Path] = None,
) -> Path:
    return execute_store_root(root) / plan_id / "assignments.json"


def _clean(value: Any, limit: int = 120) -> str:
    return str(value or "").strip()[:limit]


def normalize_assignment(raw: Mapping[str, Any]) -> Dict[str, str]:
    device_id = _clean(raw.get("device_id"), 128)
    resource_name = _clean(raw.get("resource_name"), 80)
    if not device_id:
        raise AssignmentError("device_id is required.")
    if not resource_name:
        raise AssignmentError("resource_name is required.")
    return {
        "device_id": device_id,
        "resource_name": resource_name,
        "person_name": _clean(raw.get("person_name"), 80),
        "phone": _clean(raw.get("phone"), 40),
        "agency": _clean(raw.get("agency"), 80),
    }


def _require_imported(plan_id: str, root: Optional[Path] = None) -> str:
    pid = assert_uuid(plan_id)
    registry = load_registry(root)
    if pid not in (registry.get("plans") or {}):
        raise PublishedPlanError(
            f"Published plan {pid} is not imported."
        )
    return pid


def _from_file(
    plan_id: str,
    root: Optional[Path] = None,
) -> List[Dict[str, str]]:
    path = assignments_path(plan_id, root)
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("assignments") if isinstance(raw, dict) else raw
    out: List[Dict[str, str]] = []
    if not isinstance(rows, list):
        return out
    for item in rows:
        if not isinstance(item, Mapping):
            continue
        try:
            out.append(normalize_assignment(item))
        except AssignmentError:
            continue
    out.sort(key=lambda row: (row["resource_name"], row["device_id"]))
    return out


def _save_file(
    plan_id: str,
    rows: List[Mapping[str, str]],
    root: Optional[Path] = None,
) -> None:
    path = assignments_path(plan_id, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "assignments": [dict(row) for row in rows],
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _from_db(plan_id: str) -> List[Dict[str, str]]:
    from app.core.execute.db import connect, init_schema

    init_schema()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT device_id, resource_name, person_name, phone, agency
            FROM execute_device_assignments
            WHERE plan_id = %s
            ORDER BY resource_name, device_id
            """,
            (plan_id,),
        ).fetchall()
    return [
        {
            "device_id": str(row[0]),
            "resource_name": str(row[1] or ""),
            "person_name": str(row[2] or ""),
            "phone": str(row[3] or ""),
            "agency": str(row[4] or ""),
        }
        for row in rows
        if str(row[0] or "").strip()
    ]


def _upsert_db(plan_id: str, row: Mapping[str, str]) -> None:
    from app.core.execute.db import connect, init_schema

    init_schema()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO execute_device_assignments (
                plan_id, device_id, resource_name, person_name,
                phone, agency, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, NOW()
            )
            ON CONFLICT (plan_id, device_id) DO UPDATE SET
                resource_name = EXCLUDED.resource_name,
                person_name = EXCLUDED.person_name,
                phone = EXCLUDED.phone,
                agency = EXCLUDED.agency,
                updated_at = NOW()
            """,
            (
                plan_id,
                row["device_id"],
                row["resource_name"],
                row["person_name"],
                row["phone"],
                row["agency"],
            ),
        )
        conn.commit()


def _delete_db(plan_id: str, device_id: str) -> None:
    from app.core.execute.db import connect, init_schema

    init_schema()
    with connect() as conn:
        conn.execute(
            """
            DELETE FROM execute_device_assignments
            WHERE plan_id = %s AND device_id = %s
            """,
            (plan_id, device_id),
        )
        conn.commit()


def list_assignments(
    plan_id: str,
    root: Optional[Path] = None,
) -> List[Dict[str, str]]:
    pid = assert_uuid(plan_id)
    from app.core.execute.db import using_postgres

    if using_postgres() and root is None:
        return _from_db(pid)
    return _from_file(pid, root)


def upsert_assignment(
    plan_id: str,
    payload: Mapping[str, Any],
    root: Optional[Path] = None,
) -> Dict[str, str]:
    pid = _require_imported(plan_id, root)
    row = normalize_assignment(payload)
    from app.core.execute.db import using_postgres

    if using_postgres() and root is None:
        _upsert_db(pid, row)
        return row
    current = {
        item["device_id"]: item
        for item in _from_file(pid, root)
    }
    current[row["device_id"]] = row
    _save_file(pid, list(current.values()), root)
    return row


def delete_assignment(
    plan_id: str,
    device_id: str,
    root: Optional[Path] = None,
) -> None:
    pid = _require_imported(plan_id, root)
    did = _clean(device_id, 128)
    if not did:
        raise AssignmentError("device_id is required.")
    from app.core.execute.db import using_postgres

    if using_postgres() and root is None:
        _delete_db(pid, did)
        return
    kept = [
        item
        for item in _from_file(pid, root)
        if item["device_id"] != did
    ]
    _save_file(pid, kept, root)


def assignment_roster(
    plan_id: str,
    root: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Assigned rows plus devices heard on this Day Plan."""
    pid = _require_imported(plan_id, root)
    assigned = list_assignments(pid, root)
    by_id = {row["device_id"]: dict(row) for row in assigned}
    seen: Dict[str, Dict[str, Any]] = {}
    from app.core.execute.db import using_postgres

    if using_postgres() and root is None:
        from app.core.execute.gps import latest_fixes

        try:
            for fix in latest_fixes(pid):
                did = str(fix.get("device_id") or "").strip()
                if not did:
                    continue
                row = dict(by_id.get(did) or {"device_id": did})
                row["seen"] = True
                seen[did] = row
        except Exception:
            pass
    out: List[Dict[str, Any]] = []
    for row in assigned:
        extra = seen.pop(row["device_id"], {})
        item = dict(row)
        item["seen"] = bool(extra.get("seen"))
        item["assigned"] = True
        out.append(item)
    for row in seen.values():
        row["assigned"] = bool(row.get("resource_name"))
        row.setdefault("seen", True)
        out.append(row)
    out.sort(
        key=lambda row: (
            str(row.get("resource_name") or ""),
            str(row.get("device_id") or ""),
        )
    )
    return out
