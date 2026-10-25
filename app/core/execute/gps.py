"""Execute GPS ingest and Operations overlay (Issue #925)."""

from __future__ import annotations

import hmac
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import parse_qs

from app.core.execute.db import connect, using_postgres
from app.core.execute.published_plan import active_plan_id
from app.utils.env import env_str

STALE_AFTER_SECONDS = 180
SOS_ALARMS = frozenset({"sos", "sos_alarm", "alarm"})


class GpsError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def ingest_token() -> str:
    return env_str("EXECUTE_GPS_TOKEN", "").strip()


def require_ingest_token(provided: str) -> None:
    expected = ingest_token()
    if not expected:
        raise GpsError("GPS ingest is not configured.", 503)
    given = str(provided or "").strip()
    if not given or not hmac.compare_digest(given, expected):
        raise GpsError("Unauthorized.", 401)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(raw: Any) -> Optional[datetime]:
    if raw in (None, ""):
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        unix = float(text)
        if unix > 1e12:
            unix = unix / 1000.0
        return datetime.fromtimestamp(unix, tz=timezone.utc)
    except ValueError:
        pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_float(raw: Any) -> Optional[float]:
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def is_sos(alarm: str) -> bool:
    token = str(alarm or "").strip().lower()
    return token in SOS_ALARMS or token.startswith("sos")


def _first(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def merge_client_payload(
    params: Mapping[str, Any],
    body: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Merge query params with classic OsmAnd or Traccar Client v9 JSON."""
    out: Dict[str, Any] = dict(params)
    leftover: Dict[str, Any] = {}
    if body and isinstance(body, Mapping):
        loc = body.get("location")
        if not isinstance(loc, Mapping):
            loc = {}
        coords = loc.get("coords")
        if not isinstance(coords, Mapping):
            coords = {}
        extras = loc.get("extras")
        if not isinstance(extras, Mapping):
            extras = {}
        battery = loc.get("battery")
        if not isinstance(battery, Mapping):
            battery = {}
        raw_qs = str(loc.get("_") or "").lstrip("&")
        if raw_qs:
            parsed = parse_qs(raw_qs, keep_blank_values=False)
            leftover = {}
            for key, values in parsed.items():
                if values:
                    leftover[key] = values[0]
        batt = battery.get("level")
        if isinstance(batt, (int, float)) and float(batt) <= 1.0:
            batt = float(batt) * 100.0
        event = str(loc.get("event") or extras.get("event") or "")
        alarm = extras.get("alarm")
        if event.lower() == "sos" and not alarm:
            alarm = "sos"
        out["id"] = _first(
            out.get("id"),
            out.get("deviceid"),
            leftover.get("id"),
            leftover.get("deviceid"),
            body.get("device_id"),
        )
        out["lat"] = _first(
            out.get("lat"),
            leftover.get("lat"),
            coords.get("latitude"),
        )
        out["lon"] = _first(
            out.get("lon"), leftover.get("lon"), coords.get("longitude")
        )
        out["timestamp"] = _first(
            out.get("timestamp"),
            leftover.get("timestamp"),
            loc.get("timestamp"),
        )
        out["speed"] = _first(out.get("speed"), coords.get("speed"))
        out["bearing"] = _first(
            out.get("bearing"),
            out.get("heading"),
            leftover.get("bearing"),
            leftover.get("heading"),
            coords.get("heading"),
        )
        out["accuracy"] = _first(
            out.get("accuracy"),
            leftover.get("accuracy"),
            coords.get("accuracy"),
        )
        out["batt"] = _first(out.get("batt"), leftover.get("batt"), batt)
        out["alarm"] = _first(out.get("alarm"), leftover.get("alarm"), alarm)
    if not out.get("id"):
        out["id"] = out.get("deviceid")
    if not out.get("bearing"):
        out["bearing"] = out.get("heading")
    return out


def parse_osmand(params: Mapping[str, Any]) -> Dict[str, Any]:
    merged = merge_client_payload(params)
    device_id = str(merged.get("id") or "").strip()
    lat = _parse_float(merged.get("lat"))
    lon = _parse_float(merged.get("lon"))
    if not device_id:
        raise GpsError("id is required.")
    if lat is None or lon is None:
        raise GpsError("lat and lon are required.")
    if not -90.0 <= lat <= 90.0:
        raise GpsError("lat is out of range.")
    if not -180.0 <= lon <= 180.0:
        raise GpsError("lon is out of range.")
    alarm = str(merged.get("alarm") or "").strip()
    return {
        "device_id": device_id,
        "lat": lat,
        "lon": lon,
        "fix_time": _parse_time(merged.get("timestamp")),
        "speed": _parse_float(merged.get("speed")),
        "heading": _parse_float(merged.get("bearing")),
        "accuracy": _parse_float(merged.get("accuracy")),
        "battery": _parse_float(merged.get("batt")),
        "alarm": alarm,
    }


def insert_fix(
    plan_id: str,
    fix: Mapping[str, Any],
    received_at: datetime,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO execute_gps_fixes (
                plan_id, device_id, lat, lon, fix_time, received_at,
                speed, heading, accuracy, battery, alarm
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                plan_id,
                fix["device_id"],
                fix["lat"],
                fix["lon"],
                fix.get("fix_time"),
                received_at,
                fix.get("speed"),
                fix.get("heading"),
                fix.get("accuracy"),
                fix.get("battery"),
                str(fix.get("alarm") or ""),
            ),
        )
        conn.commit()


def insert_sos(
    plan_id: str,
    fix: Mapping[str, Any],
    received_at: datetime,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO execute_gps_sos (
                plan_id, device_id, lat, lon, fix_time, received_at, alarm
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                plan_id,
                fix["device_id"],
                fix["lat"],
                fix["lon"],
                fix.get("fix_time"),
                received_at,
                str(fix.get("alarm") or "sos"),
            ),
        )
        conn.commit()
    try:
        from app.core.execute.attention import latch_new_sos

        latch_new_sos(plan_id, fix["device_id"], received_at)
    except Exception:
        pass


def latest_fixes(plan_id: str) -> List[Dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT ON (device_id)
                device_id, lat, lon, fix_time, received_at, alarm,
                speed, heading
            FROM execute_gps_fixes
            WHERE plan_id = %s
            ORDER BY device_id, received_at DESC
            """,
            (plan_id,),
        ).fetchall()
    out = []
    for row in rows:
        out.append(
            {
                "device_id": row[0],
                "lat": float(row[1]),
                "lon": float(row[2]),
                "fix_time": row[3],
                "received_at": row[4],
                "alarm": row[5] or "",
                "speed": float(row[6]) if row[6] is not None else None,
                "heading": float(row[7]) if row[7] is not None else None,
            }
        )
    return out


def list_sos(plan_id: str) -> List[Dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT device_id, lat, lon, fix_time, received_at, alarm
            FROM execute_gps_sos
            WHERE plan_id = %s
            ORDER BY received_at DESC
            """,
            (plan_id,),
        ).fetchall()
    out = []
    for row in rows:
        out.append(
            {
                "device_id": row[0],
                "lat": float(row[1]),
                "lon": float(row[2]),
                "fix_time": row[3],
                "received_at": row[4],
                "alarm": row[5] or "sos",
            }
        )
    return out


def _resource_view(
    row: Mapping[str, Any],
    assigned: Mapping[str, Mapping[str, Any]],
    *,
    stale: Optional[bool],
) -> Dict[str, Any]:
    device_id = str(row.get("device_id") or "")
    card = assigned.get(device_id) or {}
    resource_name = str(card.get("resource_name") or "").strip()
    view: Dict[str, Any] = {
        "device_id": device_id,
        "lat": row["lat"],
        "lon": row["lon"],
        "fix_time": _iso(row.get("fix_time")),
        "received_at": _iso(row.get("received_at")),
        "unknown": False,
        "resource_name": resource_name,
        "unnamed": not resource_name,
        "person_name": str(card.get("person_name") or ""),
        "phone": str(card.get("phone") or ""),
        "agency": str(card.get("agency") or ""),
        "speed": row.get("speed"),
        "heading": row.get("heading"),
        "display_name": resource_name or device_id or "unnamed",
    }
    if stale is not None:
        view["stale"] = stale
        view["status_label"] = "last seen" if stale else "live"
    return view


def _iso(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _stale(received_at: Any, now: datetime) -> bool:
    if not isinstance(received_at, datetime):
        return True
    when = received_at
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    age = now - when
    return age > timedelta(seconds=STALE_AFTER_SECONDS)


def ingest_osmand(
    params: Mapping[str, Any],
    *,
    token: str,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    require_ingest_token(token)
    if not using_postgres():
        raise GpsError("GPS requires Execute PostgreSQL.", 503)
    plan_id = active_plan_id()
    if not plan_id:
        raise GpsError("Activate a plan on Execute → Plans.", 400)
    fix = parse_osmand(params)
    received = now or _now()
    insert_fix(plan_id, fix, received)
    if is_sos(str(fix.get("alarm") or "")):
        insert_sos(plan_id, fix, received)
    return {
        "ok": True,
        "plan_id": plan_id,
        "device_id": fix["device_id"],
        "sos": is_sos(str(fix.get("alarm") or "")),
    }


def overlay(*, now: Optional[datetime] = None) -> Dict[str, Any]:
    plan_id = active_plan_id()
    if not plan_id or not using_postgres():
        return {
            "ok": True,
            "empty": True,
            "plan_id": plan_id,
            "positions": [],
            "sos": [],
        }
    clock = now or _now()
    assigned = {}
    try:
        from app.core.execute.assignments import list_assignments

        for item in list_assignments(plan_id):
            assigned[item["device_id"]] = item
    except Exception:
        assigned = {}
    positions = []
    for row in latest_fixes(plan_id):
        stale = _stale(row.get("received_at"), clock)
        positions.append(
            _resource_view(row, assigned, stale=stale)
        )
    attention = {}
    try:
        from app.core.execute.attention import attention_map

        attention = attention_map(plan_id)
    except Exception:
        attention = {}
    sos_rows = []
    seen_sos = set()
    for row in list_sos(plan_id):
        device_id = str(row.get("device_id") or "")
        if not device_id or device_id in seen_sos:
            continue
        seen_sos.add(device_id)
        state = attention.get(device_id) or {}
        status = str(state.get("status") or "new")
        if status == "cleared":
            continue
        if status not in ("new", "acknowledged"):
            status = "new"
        view = _resource_view(row, assigned, stale=None)
        view["alarm"] = row.get("alarm") or "sos"
        view["attention"] = status
        view["acknowledged_by"] = state.get("acknowledged_by") or ""
        view["acknowledged_at"] = state.get("acknowledged_at") or ""
        sos_rows.append(view)
    sos_ids = {str(row.get("device_id") or "") for row in sos_rows}
    sos_status = {
        str(row.get("device_id") or ""): row.get("attention")
        for row in sos_rows
    }
    for item in positions:
        if item["device_id"] in sos_ids:
            item["sos"] = True
            item["attention"] = sos_status.get(item["device_id"]) or "new"
        else:
            item["sos"] = False
    return {
        "ok": True,
        "empty": False,
        "plan_id": plan_id,
        "stale_after_seconds": STALE_AFTER_SECONDS,
        "positions": positions,
        "sos": sos_rows,
    }
