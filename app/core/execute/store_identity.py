"""Normalize leftover store identity to plan_id."""

from __future__ import annotations

from typing import Any, Dict, Mapping


def with_plan_id(store: Mapping[str, Any], plan_id: str) -> Dict[str, Any]:
    """Write plan_id. Read leftover run_id. Do not keep run_id."""
    payload = dict(store)
    leftover = payload.pop("run_id", None)
    current = payload.get("plan_id") or leftover or plan_id
    payload["plan_id"] = str(current or "")
    return payload
