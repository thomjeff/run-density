"""SOS attention state and action audit (#928 Milestone 2).

Clearing removes the interrupt. SOS history rows stay.
Do not use Resolved as an SOS state.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from app.core.execute.operator import clean_operator
from app.core.execute.published_plan import (
    PublishedPlanError,
    assert_uuid,
    execute_store_root,
    load_registry,
)


class AttentionError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


NEW = "new"
ACKNOWLEDGED = "acknowledged"
CLEARED = "cleared"
ALLOWED = {NEW, ACKNOWLEDGED, CLEARED}

AUDIT_ACTIONS = {
    "sos_acknowledge",
    "sos_clear",
    "reopen",
    "close",
    "assignment_upsert",
    "assignment_delete",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def _require_imported(plan_id: str, root: Optional[Path] = None) -> str:
    pid = assert_uuid(plan_id)
    registry = load_registry(root)
    if pid not in (registry.get("plans") or {}):
        raise PublishedPlanError(
            f"Published plan {pid} is not imported."
        )
    return pid


def _attention_path(plan_id: str, root: Optional[Path] = None) -> Path:
    return execute_store_root(root) / plan_id / "attention.json"


def _audit_path(plan_id: str, root: Optional[Path] = None) -> Path:
    return execute_store_root(root) / plan_id / "audit.json"


def _empty_row(device_id: str) -> Dict[str, Any]:
    return {
        "device_id": device_id,
        "status": NEW,
        "sos_received_at": "",
        "acknowledged_at": "",
        "acknowledged_by": "",
        "cleared_at": "",
        "cleared_by": "",
    }


def _from_file(
    plan_id: str,
    root: Optional[Path] = None,
) -> Dict[str, Dict[str, Any]]:
    path = _attention_path(plan_id, root)
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("attention") if isinstance(raw, dict) else raw
    out: Dict[str, Dict[str, Any]] = {}
    if not isinstance(rows, list):
        return out
    for item in rows:
        if not isinstance(item, Mapping):
            continue
        did = str(item.get("device_id") or "").strip()
        status = str(item.get("status") or NEW)
        if not did or status not in ALLOWED:
            continue
        row = _empty_row(did)
        row.update(
            {
                "status": status,
                "sos_received_at": str(item.get("sos_received_at") or ""),
                "acknowledged_at": str(item.get("acknowledged_at") or ""),
                "acknowledged_by": str(item.get("acknowledged_by") or ""),
                "cleared_at": str(item.get("cleared_at") or ""),
                "cleared_by": str(item.get("cleared_by") or ""),
            }
        )
        out[did] = row
    return out


def _save_file(
    plan_id: str,
    rows: Mapping[str, Mapping[str, Any]],
    root: Optional[Path] = None,
) -> None:
    path = _attention_path(plan_id, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "attention": [dict(row) for row in rows.values()],
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _from_db(plan_id: str) -> Dict[str, Dict[str, Any]]:
    from app.core.execute.db import connect, init_schema

    init_schema()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT device_id, status, sos_received_at,
                   acknowledged_at, acknowledged_by,
                   cleared_at, cleared_by
            FROM execute_sos_attention
            WHERE plan_id = %s
            """,
            (plan_id,),
        ).fetchall()
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        did = str(row[0] or "").strip()
        if not did:
            continue
        out[did] = {
            "device_id": did,
            "status": str(row[1] or NEW),
            "sos_received_at": _iso(row[2]),
            "acknowledged_at": _iso(row[3]),
            "acknowledged_by": str(row[4] or ""),
            "cleared_at": _iso(row[5]),
            "cleared_by": str(row[6] or ""),
        }
    return out


def _upsert_db(plan_id: str, row: Mapping[str, Any]) -> None:
    from app.core.execute.db import connect, init_schema

    init_schema()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO execute_sos_attention (
                plan_id, device_id, status, sos_received_at,
                acknowledged_at, acknowledged_by,
                cleared_at, cleared_by
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (plan_id, device_id) DO UPDATE SET
                status = EXCLUDED.status,
                sos_received_at = EXCLUDED.sos_received_at,
                acknowledged_at = EXCLUDED.acknowledged_at,
                acknowledged_by = EXCLUDED.acknowledged_by,
                cleared_at = EXCLUDED.cleared_at,
                cleared_by = EXCLUDED.cleared_by
            """,
            (
                plan_id,
                row["device_id"],
                row["status"],
                row.get("sos_received_at") or None,
                row.get("acknowledged_at") or None,
                row.get("acknowledged_by") or "",
                row.get("cleared_at") or None,
                row.get("cleared_by") or "",
            ),
        )
        conn.commit()


def _load(
    plan_id: str,
    root: Optional[Path] = None,
) -> Dict[str, Dict[str, Any]]:
    from app.core.execute.db import using_postgres

    if using_postgres() and root is None:
        return _from_db(plan_id)
    return _from_file(plan_id, root)


def _save_row(
    plan_id: str,
    row: Mapping[str, Any],
    root: Optional[Path] = None,
) -> None:
    from app.core.execute.db import using_postgres

    if using_postgres() and root is None:
        _upsert_db(plan_id, row)
        return
    current = _from_file(plan_id, root)
    current[row["device_id"]] = dict(row)
    _save_file(plan_id, current, root)


def attention_map(
    plan_id: str,
    root: Optional[Path] = None,
) -> Dict[str, Dict[str, Any]]:
    pid = assert_uuid(plan_id)
    return _load(pid, root)


def latch_new_sos(
    plan_id: str,
    device_id: str,
    received_at: Optional[datetime] = None,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    pid = assert_uuid(plan_id)
    did = str(device_id or "").strip()
    if not did:
        raise AttentionError("device_id is required.")
    when = received_at or _now()
    row = _empty_row(did)
    row["status"] = NEW
    row["sos_received_at"] = _iso(when)
    _save_row(pid, row, root)
    return row


def acknowledge_sos(
    plan_id: str,
    device_id: str,
    operator: str,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    pid = _require_imported(plan_id, root)
    did = str(device_id or "").strip()
    actor = clean_operator(operator)
    if not did:
        raise AttentionError("device_id is required.")
    if not actor:
        raise AttentionError(
            "Set a session display name before this action."
        )
    current = _load(pid, root).get(did) or _empty_row(did)
    if current.get("status") == CLEARED:
        raise AttentionError("This SOS is no longer in attention.")
    when = _iso(_now())
    current["status"] = ACKNOWLEDGED
    current["acknowledged_at"] = when
    current["acknowledged_by"] = actor
    _save_row(pid, current, root)
    record_audit(
        pid,
        action="sos_acknowledge",
        actor=actor,
        device_id=did,
        root=root,
    )
    return current


def clear_sos_attention(
    plan_id: str,
    device_id: str,
    operator: str,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    pid = _require_imported(plan_id, root)
    did = str(device_id or "").strip()
    actor = clean_operator(operator)
    if not did:
        raise AttentionError("device_id is required.")
    if not actor:
        raise AttentionError(
            "Set a session display name before this action."
        )
    current = _load(pid, root).get(did) or _empty_row(did)
    when = _iso(_now())
    current["status"] = CLEARED
    current["cleared_at"] = when
    current["cleared_by"] = actor
    _save_row(pid, current, root)
    record_audit(
        pid,
        action="sos_clear",
        actor=actor,
        device_id=did,
        root=root,
    )
    return current


def _audit_from_file(
    plan_id: str,
    root: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    path = _audit_path(plan_id, root)
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("audit") if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        return []
    return [dict(item) for item in rows if isinstance(item, Mapping)]


def _audit_save_file(
    plan_id: str,
    rows: List[Mapping[str, Any]],
    root: Optional[Path] = None,
) -> None:
    path = _audit_path(plan_id, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"audit": [dict(row) for row in rows]}, indent=2)
    path.write_text(payload + "\n", encoding="utf-8")


def record_audit(
    plan_id: str,
    *,
    action: str,
    actor: str,
    device_id: str = "",
    loc_id: Optional[int] = None,
    detail: Optional[Mapping[str, Any]] = None,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    pid = assert_uuid(plan_id)
    if action not in AUDIT_ACTIONS:
        raise AttentionError("Unknown audit action.")
    name = clean_operator(actor)
    if not name:
        raise AttentionError(
            "Set a session display name before this action."
        )
    row = {
        "plan_id": pid,
        "action": action,
        "actor": name,
        "at": _iso(_now()),
        "device_id": str(device_id or ""),
        "loc_id": loc_id,
        "detail": dict(detail or {}),
    }
    from app.core.execute.db import using_postgres

    if using_postgres() and root is None:
        from app.core.execute.db import connect, init_schema

        init_schema()
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO execute_action_audit (
                    plan_id, action, actor, at, device_id, loc_id, detail
                ) VALUES (
                    %s, %s, %s, NOW(), %s, %s, %s::jsonb
                )
                """,
                (
                    pid,
                    action,
                    name,
                    row["device_id"] or None,
                    loc_id,
                    json.dumps(row["detail"]),
                ),
            )
            conn.commit()
        return row
    rows = _audit_from_file(pid, root)
    rows.insert(0, row)
    _audit_save_file(pid, rows[:200], root)
    return row


def list_audit(
    plan_id: str,
    root: Optional[Path] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    pid = assert_uuid(plan_id)
    cap = max(1, min(int(limit or 50), 200))
    from app.core.execute.db import using_postgres

    if using_postgres() and root is None:
        from app.core.execute.db import connect, init_schema

        init_schema()
        with connect() as conn:
            rows = conn.execute(
                """
                SELECT action, actor, at, device_id, loc_id, detail
                FROM execute_action_audit
                WHERE plan_id = %s
                ORDER BY at DESC
                LIMIT %s
                """,
                (pid, cap),
            ).fetchall()
        return [
            {
                "action": str(row[0]),
                "actor": str(row[1] or ""),
                "at": _iso(row[2]),
                "device_id": str(row[3] or ""),
                "loc_id": row[4],
                "detail": dict(row[5]) if isinstance(row[5], dict) else {},
            }
            for row in rows
        ]
    return _audit_from_file(pid, root)[:cap]
