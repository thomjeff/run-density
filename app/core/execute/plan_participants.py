"""Participant roster tied to one imported Day Plan (Issue #947)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.execute import participants as hs_participants
from app.core.execute.plan_storage import PlanStorage
from app.core.execute.published_plan import load_imported_plan
from app.core.execute.store_identity import with_plan_id


def decode_roster(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8.") from exc


def parse_roster(text: str) -> List[Dict[str, Any]]:
    """Validate a roster before anything is written."""
    rows = hs_participants.parse_roster_csv(text)
    hs_participants.assert_unique_start_bibs(rows)
    if not hs_participants.lookup_rows(rows):
        raise ValueError("Participant list has no participants.")
    return rows


def _plan_storage(
    plan_id: str,
    root: Optional[Path] = None,
) -> Tuple[str, PlanStorage]:
    loaded = load_imported_plan(plan_id, root)
    day = str(loaded["manifest"].get("weekday_code") or "").strip()
    return day, PlanStorage(root=str(loaded["directory"]), plan_id=plan_id)


def participant_count(plan_id: str, root: Optional[Path] = None) -> int:
    day, storage = _plan_storage(plan_id, root)
    store = hs_participants.load_store(storage, run_id=plan_id, day=day)
    return len(hs_participants.lookup_rows(store.get("rows") or []))


def import_plan_participants(
    plan_id: str,
    text: str,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    parse_roster(text)
    day, storage = _plan_storage(plan_id, root)
    store, stats = hs_participants.import_csv_text(
        storage, run_id=plan_id, day=day, text=text
    )
    hs_participants.persist_store(storage, day, with_plan_id(store, plan_id))
    return {"plan_id": plan_id, "day": day, "stats": stats}
