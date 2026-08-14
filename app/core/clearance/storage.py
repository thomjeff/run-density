"""Load and save package-root clearance.json (Issue #832)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.clearance.model import empty_clearance_doc, validate_clearance_doc
from app.core.clearance.subjects import list_package_location_ids
from app.core.config_package.storage import (
    resolve_config_package_path,
    validate_config_id,
)

CLEARANCE_NAME = "clearance.json"


def clearance_path(config_id: str) -> Path:
    return resolve_config_package_path(config_id) / CLEARANCE_NAME


def load_config_clearance(config_id: str) -> Dict[str, Any]:
    """Load clearance.json or return an empty document if missing."""
    cid = validate_config_id(config_id)
    path = clearance_path(cid)
    if not path.is_file():
        return empty_clearance_doc()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    known = list_package_location_ids(cid)
    return validate_clearance_doc(data, known_location_ids=known)


def save_config_clearance(config_id: str, data: Dict[str, Any]) -> Path:
    """Validate and write clearance.json for a config package."""
    cid = validate_config_id(config_id)
    package_path = resolve_config_package_path(cid)
    known = list_package_location_ids(cid)
    doc = validate_clearance_doc(data, known_location_ids=known)
    doc["updated"] = datetime.now(timezone.utc).isoformat()
    path = package_path / CLEARANCE_NAME
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path


def try_load_config_clearance(config_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Return a validated document, or None if the package/file is missing."""
    if not config_id:
        return None
    try:
        cid = validate_config_id(config_id)
        path = resolve_config_package_path(cid) / CLEARANCE_NAME
    except (FileNotFoundError, ValueError):
        return None
    if not path.is_file():
        return None
    return load_config_clearance(cid)
