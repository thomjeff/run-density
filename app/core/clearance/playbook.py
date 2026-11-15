"""
Static clearance playbook from authored rules + Locations last_runner (Issue #832).
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence


def _parse_hhmmss(raw: Any) -> Optional[int]:
    text = str(raw or "").strip()
    if not text or text.upper() == "NA":
        return None
    parts = text.split(":")
    if len(parts) < 2:
        return None
    try:
        hh = int(parts[0])
        mm = int(parts[1])
        ss = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        return None
    return hh * 3600 + mm * 60 + ss


def _fmt_hhmmss(seconds: Optional[int]) -> Optional[str]:
    if seconds is None:
        return None
    if seconds < 0:
        seconds = 0
    hh = seconds // 3600
    mm = (seconds % 3600) // 60
    ss = seconds % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}"


def _row_subject_ids(row: Mapping[str, Any]) -> List[str]:
    ids: List[str] = []
    for key in ("loc_id", "primary_loc_id", "id"):
        raw = row.get(key)
        if raw is None or str(raw).strip() == "":
            continue
        text = str(raw).strip()
        if text.isdigit():
            text = str(int(text))
        if text not in ids:
            ids.append(text)
    for raw in row.get("loc_ids") or []:
        if raw is None or str(raw).strip() == "":
            continue
        text = str(raw).strip()
        if text.isdigit():
            text = str(int(text))
        if text not in ids:
            ids.append(text)
    return ids


def _clear_times_by_subject(
    location_rows: Sequence[Mapping[str, Any]],
    assets: Sequence[Mapping[str, Any]],
) -> Dict[str, Optional[int]]:
    times: Dict[str, Optional[int]] = {}
    for row in location_rows:
        secs = _parse_hhmmss(row.get("last_runner"))
        for sid in _row_subject_ids(row):
            prev = times.get(sid)
            if prev is None or (secs is not None and secs > prev):
                times[sid] = secs
    for asset in assets:
        asset_id = str(asset.get("asset_id") or "").strip()
        if not asset_id:
            continue
        loc_id = str(asset.get("loc_id") or "").strip()
        if loc_id and loc_id in times:
            times[asset_id] = times[loc_id]
        else:
            times.setdefault(asset_id, None)
    return times


def build_static_playbook(
    clearance_doc: Mapping[str, Any],
    location_rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Derive reopen-not-before times and blocker explanations.

    ``reopen_not_before`` for a blocked subject is
    ``max(last_runner(u) for u in until)`` (AND).
    """
    assets = list(clearance_doc.get("assets") or [])
    rules = list(clearance_doc.get("rules") or [])
    clear_times = _clear_times_by_subject(location_rows, assets)

    steps: List[Dict[str, Any]] = []
    for rule in rules:
        blocked = str(rule.get("blocked") or "")
        until = [str(u) for u in (rule.get("until") or [])]
        blockers: List[Dict[str, Any]] = []
        max_secs: Optional[int] = None
        missing = False
        for u in until:
            secs = clear_times.get(u)
            blockers.append(
                {
                    "subject": u,
                    "last_runner": _fmt_hhmmss(secs),
                    "known": secs is not None,
                }
            )
            if secs is None:
                missing = True
            elif max_secs is None or secs > max_secs:
                max_secs = secs
        steps.append(
            {
                "rule_id": rule.get("id"),
                "blocked": blocked,
                "until": until,
                "clear_when": rule.get("clear_when") or "last_runner",
                "blockers": blockers,
                "reopen_not_before": None if missing else _fmt_hhmmss(max_secs),
                "ready": not missing and max_secs is not None,
                "explanation": (
                    f"{blocked} waits until all of [{', '.join(until)}] clear "
                    f"(last runner at each point)."
                    + (
                        f" Earliest reopen: {_fmt_hhmmss(max_secs)}."
                        if not missing and max_secs is not None
                        else " Missing last_runner for one or more blockers."
                    )
                ),
            }
        )

    steps.sort(
        key=lambda s: (
            _parse_hhmmss(s.get("reopen_not_before")) is None,
            _parse_hhmmss(s.get("reopen_not_before")) or 0,
            str(s.get("blocked") or ""),
        )
    )
    return {
        "ok": True,
        "clear_when": "last_runner",
        "rule_count": len(steps),
        "steps": steps,
    }
