"""Stable authoring keys for config-package locations (Issue #780)."""

from __future__ import annotations

import re
import secrets
from typing import Any, Dict, Optional, Set

# Crockford base32 (no 0/O, 1/I/L) — short keys for authoring UI.
_LOCATION_KEY_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
LOCATION_KEY_LENGTH = 5
LOCATION_KEY_RE = re.compile(rf"^[{_LOCATION_KEY_ALPHABET}]{{{LOCATION_KEY_LENGTH}}}$")


def is_valid_location_key(value: Any) -> bool:
    if value is None:
        return False
    return bool(LOCATION_KEY_RE.match(str(value).strip()))


def generate_location_key(used: Optional[Set[str]] = None) -> str:
    """Allocate a unique short location_key (5-char Crockford base32)."""
    taken = {str(k).strip() for k in (used or set()) if k}
    for _ in range(256):
        key = "".join(
            secrets.choice(_LOCATION_KEY_ALPHABET) for _ in range(LOCATION_KEY_LENGTH)
        )
        if key not in taken:
            return key
    raise RuntimeError("Could not allocate location_key")


def ensure_location_key(
    loc: Dict[str, Any],
    used: Optional[Set[str]] = None,
) -> str:
    """
    Ensure ``loc`` has a valid ``location_key``; return the key.

    Issue #810: a valid existing key is always preserved, even if already present
    in ``used``. Paired reverse legs intentionally share one key for the same
    physical Location. Newly allocated keys are added to ``used`` when provided.
    """
    existing = str(loc.get("location_key") or "").strip()
    taken = used if used is not None else set()
    if is_valid_location_key(existing):
        loc["location_key"] = existing
        if used is not None:
            used.add(existing)
        return existing
    key = generate_location_key(taken)
    loc["location_key"] = key
    if used is not None:
        used.add(key)
    return key
