"""Plan-rooted storage that also writes Execute blobs to Postgres."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from app.core.locations.report_json import parse_optional_id
from app.storage import Storage

_KIND_BY_NAME = {
    "participants.json": "participants",
    "incidents.json": "incidents",
    "state.json": "reopen",
}


def _blob_key(path: str) -> Optional[tuple]:
    parts = Path(str(path)).parts
    if len(parts) < 3 or parts[-2] != "execution":
        return None
    kind = _KIND_BY_NAME.get(parts[-1])
    if not kind:
        return None
    return kind, parts[0]


class PlanStorage(Storage):
    """File store for an imported plan, with optional Postgres blobs."""

    def __init__(self, root: Optional[str], plan_id: str):
        super().__init__(root=root)
        self.plan_id = str(plan_id)

    def exists(self, path: str) -> bool:
        key = _blob_key(path)
        if key:
            from app.core.execute.db import get_blob, using_postgres

            if using_postgres():
                blob = get_blob(self.plan_id, key[0], key[1])
                if blob is not None:
                    return True
        return super().exists(path)

    def read_json(self, path: str) -> Dict[str, Any]:
        key = _blob_key(path)
        if key:
            from app.core.execute.db import get_blob, using_postgres

            if using_postgres():
                raw = get_blob(self.plan_id, key[0], key[1])
                if raw is not None:
                    return raw
        return super().read_json(path)

    def write_json(self, path: str, data: Dict[str, Any]) -> str:
        key = _blob_key(path)
        if key:
            from app.core.execute.db import put_blob, using_postgres

            if using_postgres():
                put_blob(self.plan_id, key[0], key[1], data)
        try:
            return super().write_json(path, data)
        except Exception:
            if key:
                from app.core.execute.db import using_postgres

                if using_postgres():
                    return ""
            raise


def location_catalog_from_rows(
    rows: Optional[Sequence[Any]],
) -> List[Dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    out: List[Dict[str, Any]] = []
    seen: set[Any] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        loc_id = parse_optional_id(row.get("loc_id"))
        label = str(row.get("loc_label") or "").strip()
        if not label:
            continue
        key = loc_id if loc_id is not None else label.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "loc_id": loc_id,
                "loc_label": label,
                "zone": str(row.get("zone") or "").strip(),
            }
        )
    return out
