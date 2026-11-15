"""
Clearance / dependency rules for reopen playbooks (Issue #832).

Package-root ``clearance_rules.json``. A ``blocked`` subject waits on all
``until`` subjects (AND). Clearance time uses Locations ``last_runner``.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set

from app.core.config_package.storage import (
    load_config_course,
    resolve_config_package_path,
    validate_config_id,
)

logger = logging.getLogger(__name__)

CLEARANCE_RULES_NAME = "clearance_rules.json"
CLEARANCE_DOC_VERSION = 1
CLEAR_WHEN_LAST_RUNNER = "last_runner"
_SUBJECT_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-:]{0,63}$")


def clearance_rules_path(config_id: str) -> Path:
    return resolve_config_package_path(config_id) / CLEARANCE_RULES_NAME


def empty_clearance_doc() -> Dict[str, Any]:
    return {
        "version": CLEARANCE_DOC_VERSION,
        "assets": [],
        "rules": [],
        "updated": None,
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _subject_id(raw: Any, field: str) -> str:
    text = str(raw or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    if text.isdigit():
        return str(int(text))
    if not _SUBJECT_RE.match(text):
        raise ValueError(f"Invalid {field}: {raw!r}")
    return text


def _normalize_asset(raw: Any, index: int) -> Dict[str, str]:
    if not isinstance(raw, Mapping):
        raise ValueError(f"assets[{index}] must be an object")
    asset_id = _subject_id(
        raw.get("asset_id") or raw.get("id"), f"assets[{index}].asset_id"
    )
    label = str(raw.get("label") or asset_id).strip() or asset_id
    out: Dict[str, str] = {"asset_id": asset_id, "label": label}
    loc_raw = raw.get("loc_id")
    if loc_raw is not None and str(loc_raw).strip() != "":
        out["loc_id"] = _subject_id(loc_raw, f"assets[{index}].loc_id")
    return out


def _normalize_rule(raw: Any, index: int) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError(f"rules[{index}] must be an object")
    rule_id = str(raw.get("id") or f"rule-{index + 1}").strip() or f"rule-{index + 1}"
    blocked = _subject_id(raw.get("blocked"), f"rules[{index}].blocked")
    until_raw = raw.get("until")
    if until_raw is None and raw.get("until_one") is not None:
        until_raw = [raw.get("until_one")]
    if not isinstance(until_raw, list) or not until_raw:
        raise ValueError(f"rules[{index}].until must be a non-empty list")
    until: List[str] = []
    for j, item in enumerate(until_raw):
        sid = _subject_id(item, f"rules[{index}].until[{j}]")
        if sid == blocked:
            raise ValueError(f"rules[{index}]: blocked cannot wait on itself")
        if sid not in until:
            until.append(sid)
    clear_when = str(raw.get("clear_when") or CLEAR_WHEN_LAST_RUNNER).strip().lower()
    if clear_when != CLEAR_WHEN_LAST_RUNNER:
        raise ValueError(
            f"rules[{index}].clear_when must be '{CLEAR_WHEN_LAST_RUNNER}' in v1"
        )
    return {
        "id": rule_id,
        "blocked": blocked,
        "until": until,
        "clear_when": CLEAR_WHEN_LAST_RUNNER,
    }


def known_subjects_from_course(course: Mapping[str, Any]) -> Set[str]:
    subjects: Set[str] = set()
    for loc in course.get("locations") or []:
        if not isinstance(loc, Mapping):
            continue
        for key in ("id", "loc_id"):
            raw = loc.get(key)
            if raw is None or str(raw).strip() == "":
                continue
            try:
                subjects.add(_subject_id(raw, "loc_id"))
            except ValueError:
                continue
    return subjects


def detect_cycles(rules: Sequence[Mapping[str, Any]]) -> Optional[List[str]]:
    """Return a cycle path if the blocked→until graph has a cycle, else None."""
    graph: Dict[str, List[str]] = {}
    for rule in rules:
        blocked = str(rule.get("blocked") or "")
        until = [str(u) for u in (rule.get("until") or [])]
        graph.setdefault(blocked, [])
        for u in until:
            graph[blocked].append(u)
            graph.setdefault(u, [])

    visiting: Set[str] = set()
    visited: Set[str] = set()
    stack: List[str] = []

    def dfs(node: str) -> Optional[List[str]]:
        visiting.add(node)
        stack.append(node)
        for nxt in graph.get(node) or []:
            if nxt in visiting:
                if nxt in stack:
                    i = stack.index(nxt)
                    return stack[i:] + [nxt]
                return [node, nxt, node]
            if nxt not in visited:
                found = dfs(nxt)
                if found:
                    return found
        visiting.remove(node)
        stack.pop()
        visited.add(node)
        return None

    for node in sorted(graph.keys()):
        if node not in visited:
            found = dfs(node)
            if found:
                return found
    return None


def validate_clearance_doc(
    data: Mapping[str, Any],
    *,
    known_loc_ids: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    if not isinstance(data, Mapping):
        raise ValueError("clearance document must be an object")
    assets_raw = data.get("assets") or []
    rules_raw = data.get("rules") or []
    if not isinstance(assets_raw, list):
        raise ValueError("assets must be a list")
    if not isinstance(rules_raw, list):
        raise ValueError("rules must be a list")

    assets: List[Dict[str, str]] = []
    asset_ids: Set[str] = set()
    for i, item in enumerate(assets_raw):
        asset = _normalize_asset(item, i)
        if asset["asset_id"] in asset_ids:
            raise ValueError(f"Duplicate asset_id: {asset['asset_id']}")
        asset_ids.add(asset["asset_id"])
        assets.append(asset)

    rules: List[Dict[str, Any]] = []
    rule_ids: Set[str] = set()
    for i, item in enumerate(rules_raw):
        rule = _normalize_rule(item, i)
        if rule["id"] in rule_ids:
            raise ValueError(f"Duplicate rule id: {rule['id']}")
        rule_ids.add(rule["id"])
        rules.append(rule)

    if known_loc_ids is not None:
        known = set(known_loc_ids) | asset_ids
        for i, rule in enumerate(rules):
            for sid in [rule["blocked"], *rule["until"]]:
                if sid not in known:
                    raise ValueError(f"rules[{i}] references unknown subject '{sid}'")

    cycle = detect_cycles(rules)
    if cycle:
        raise ValueError("Clearance rules contain a cycle: " + " → ".join(cycle))

    return {
        "version": int(data.get("version") or CLEARANCE_DOC_VERSION),
        "assets": assets,
        "rules": rules,
        "updated": data.get("updated"),
    }


def load_config_clearance_rules(config_id: str) -> Dict[str, Any]:
    cid = validate_config_id(config_id)
    path = clearance_rules_path(cid)
    if not path.is_file():
        return empty_clearance_doc()
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    course = load_config_course(cid)
    known = known_subjects_from_course(course)
    return validate_clearance_doc(
        data if isinstance(data, dict) else {}, known_loc_ids=known
    )


def save_config_clearance_rules(config_id: str, data: Mapping[str, Any]) -> Path:
    cid = validate_config_id(config_id)
    package_path = resolve_config_package_path(cid)
    course = load_config_course(cid)
    known = known_subjects_from_course(course)
    doc = validate_clearance_doc(data, known_loc_ids=known)
    doc["updated"] = _now_iso()
    path = package_path / CLEARANCE_RULES_NAME
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    logger.info("Saved clearance rules for %s (%s rules)", cid, len(doc["rules"]))
    return path
