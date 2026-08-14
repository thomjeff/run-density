"""Clearance.json schema, normalization, and cycle rejection (Issue #832)."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

CLEARANCE_DOC_VERSION = 1
CLEAR_WHEN_LAST_RUNNER = "last_runner"
SUBJECT_KINDS = frozenset({"location"})
RULE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


class ClearanceValidationError(ValueError):
    """Invalid clearance document (including dependency cycles)."""


def empty_clearance_doc() -> Dict[str, Any]:
    return {
        "version": CLEARANCE_DOC_VERSION,
        "clear_when": CLEAR_WHEN_LAST_RUNNER,
        "assets": [],
        "rules": [],
        "updated": None,
    }


def subject_key(subject: Dict[str, str]) -> str:
    return f"{subject['kind']}:{subject['id']}"


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_subject(raw: Any, *, field: str) -> Dict[str, str]:
    """Normalize a blocked/until subject to ``{kind, id}``."""
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            raise ClearanceValidationError(f"{field} must not be empty")
        lower = text.lower()
        if lower.startswith("asset:"):
            raise ClearanceValidationError(
                f"{field}: off-course assets are not used; pin the point as a location"
            )
        if lower.startswith("loc:") or lower.startswith("location:"):
            return _finish_subject("location", text.split(":", 1)[1], field)
        return _finish_subject("location", text, field)

    if isinstance(raw, dict):
        kind = _as_text(raw.get("kind")).lower()
        sid = raw.get("id")
        if sid is None:
            sid = raw.get("loc_id") or raw.get("asset_id")
        if kind == "asset":
            raise ClearanceValidationError(
                f"{field}: off-course assets are not used; pin the point as a location"
            )
        if not kind:
            kind = "location"
        return _finish_subject(kind, sid, field)

    raise ClearanceValidationError(f"{field} must be a string or object")


def _finish_subject(kind: str, raw_id: Any, field: str) -> Dict[str, str]:
    kind = (kind or "").strip().lower()
    if kind not in SUBJECT_KINDS:
        raise ClearanceValidationError(
            f"{field} kind must be location, got {kind!r}"
        )
    sid = _as_text(raw_id)
    if not sid:
        raise ClearanceValidationError(f"{field} id is required")
    if sid.isdigit():
        sid = str(int(sid))
    return {"kind": "location", "id": sid}


def _normalize_rule(raw: Any, index: int) -> Dict[str, Any]:
    field = f"rules[{index}]"
    if not isinstance(raw, dict):
        raise ClearanceValidationError(f"{field} must be an object")
    rule_id = _as_text(raw.get("id") or raw.get("rule_id"))
    if not rule_id:
        raise ClearanceValidationError(f"{field}.id is required")
    if not RULE_ID_RE.match(rule_id):
        raise ClearanceValidationError(
            f"{field}.id {rule_id!r} must be 1–40 letters, digits, _ or -"
        )
    clear_when = _as_text(raw.get("clear_when") or CLEAR_WHEN_LAST_RUNNER).lower()
    if clear_when != CLEAR_WHEN_LAST_RUNNER:
        raise ClearanceValidationError(
            f"{field}.clear_when must be {CLEAR_WHEN_LAST_RUNNER!r} in v1"
        )
    blocked = normalize_subject(raw.get("blocked"), field=f"{field}.blocked")
    until_raw = raw.get("until")
    if until_raw is None:
        single = raw.get("until_id") or raw.get("until_one")
        until_raw = [single] if single is not None else []
    if isinstance(until_raw, (str, dict)):
        until_raw = [until_raw]
    if not isinstance(until_raw, list) or not until_raw:
        raise ClearanceValidationError(
            f"{field}.until must be a non-empty list (pair or AND group)"
        )
    until: List[Dict[str, str]] = []
    seen: Set[str] = set()
    for j, item in enumerate(until_raw):
        subj = normalize_subject(item, field=f"{field}.until[{j}]")
        key = subject_key(subj)
        if key in seen:
            raise ClearanceValidationError(f"{field}.until has duplicate {key}")
        if key == subject_key(blocked):
            raise ClearanceValidationError(
                f"{field}: blocked subject cannot wait on itself"
            )
        seen.add(key)
        until.append(subj)
    note = _as_text(raw.get("note"))
    rule: Dict[str, Any] = {
        "id": rule_id,
        "blocked": blocked,
        "until": until,
        "clear_when": CLEAR_WHEN_LAST_RUNNER,
    }
    if note:
        rule["note"] = note
    return rule


def _find_cycle(edges: Dict[str, Set[str]]) -> Optional[List[str]]:
    """Return one cycle as node keys, or None. Edge u→v means u depends on v."""
    visiting: Set[str] = set()
    visited: Set[str] = set()
    stack: List[str] = []

    def dfs(node: str) -> Optional[List[str]]:
        visiting.add(node)
        stack.append(node)
        for nxt in sorted(edges.get(node, ())):
            if nxt in visiting:
                start = stack.index(nxt)
                return stack[start:] + [nxt]
            if nxt not in visited:
                found = dfs(nxt)
                if found:
                    return found
        stack.pop()
        visiting.remove(node)
        visited.add(node)
        return None

    for node in sorted(edges):
        if node not in visited:
            found = dfs(node)
            if found:
                return found
    return None


def detect_clearance_cycle(rules: Sequence[MappingLike]) -> Optional[List[str]]:
    edges: Dict[str, Set[str]] = {}
    for rule in rules:
        blocked = subject_key(rule["blocked"])  # type: ignore[index]
        edges.setdefault(blocked, set())
        for until in rule["until"]:  # type: ignore[index]
            dep = subject_key(until)
            edges[blocked].add(dep)
            edges.setdefault(dep, set())
    return _find_cycle(edges)


MappingLike = Dict[str, Any]


def validate_clearance_doc(
    data: Any,
    *,
    known_location_ids: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Normalize and validate a clearance document. Rejects cycles."""
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ClearanceValidationError("clearance document must be a JSON object")

    version = data.get("version", CLEARANCE_DOC_VERSION)
    try:
        version_i = int(version)
    except (TypeError, ValueError) as exc:
        raise ClearanceValidationError("version must be an integer") from exc
    if version_i != CLEARANCE_DOC_VERSION:
        raise ClearanceValidationError(
            f"Unsupported clearance version {version_i}; expected {CLEARANCE_DOC_VERSION}"
        )

    clear_when = _as_text(data.get("clear_when") or CLEAR_WHEN_LAST_RUNNER).lower()
    if clear_when != CLEAR_WHEN_LAST_RUNNER:
        raise ClearanceValidationError(
            f"clear_when must be {CLEAR_WHEN_LAST_RUNNER!r} in v1"
        )

    raw_assets = data.get("assets") or []
    if not isinstance(raw_assets, list):
        raise ClearanceValidationError("assets must be a list")
    if raw_assets:
        raise ClearanceValidationError(
            "Off-course assets are not used; pin traffic/extract (or any hold) "
            "as a location with a loc_id"
        )

    raw_rules = data.get("rules") or []
    if not isinstance(raw_rules, list):
        raise ClearanceValidationError("rules must be a list")
    rules: List[Dict[str, Any]] = []
    rule_ids: Set[str] = set()
    blocked_keys: Set[str] = set()
    known_locs = {
        str(int(x)) if str(x).strip().isdigit() else str(x).strip()
        for x in (known_location_ids or [])
        if str(x).strip()
    }
    for i, item in enumerate(raw_rules):
        rule = _normalize_rule(item, i)
        if rule["id"] in rule_ids:
            raise ClearanceValidationError(f"Duplicate rule id {rule['id']!r}")
        rule_ids.add(rule["id"])
        bkey = subject_key(rule["blocked"])
        if bkey in blocked_keys:
            raise ClearanceValidationError(
                f"Multiple rules block {bkey}; use one AND group instead"
            )
        blocked_keys.add(bkey)
        _assert_subject_known(rule["blocked"], known_locs, f"rules[{i}].blocked")
        for j, until in enumerate(rule["until"]):
            _assert_subject_known(until, known_locs, f"rules[{i}].until[{j}]")
        rules.append(rule)

    cycle = detect_clearance_cycle(rules)
    if cycle:
        raise ClearanceValidationError(
            "Clearance rules contain a cycle: " + " → ".join(cycle)
        )

    return {
        "version": CLEARANCE_DOC_VERSION,
        "clear_when": CLEAR_WHEN_LAST_RUNNER,
        "assets": [],
        "rules": rules,
        "updated": data.get("updated"),
    }


def _assert_subject_known(
    subject: Dict[str, str],
    known_locs: Set[str],
    field: str,
) -> None:
    if (
        subject["kind"] == "location"
        and known_locs
        and subject["id"] not in known_locs
    ):
        raise ClearanceValidationError(
            f"{field} references unknown loc_id {subject['id']!r}"
        )
