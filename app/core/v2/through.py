"""Staged analysis stop-points (#860).

``through`` controls how far ``create_full_analysis_pipeline`` runs:

- ``full`` (default) — today's complete analysis
- ``trajectory`` — Phase 1–2.5 only (trajectory layer persist)
- ``locations`` — trajectory layer + Locations report (no density/flow)
"""

from __future__ import annotations

from typing import FrozenSet

THROUGH_FULL = "full"
THROUGH_TRAJECTORY = "trajectory"
THROUGH_LOCATIONS = "locations"

THROUGH_VALUES: FrozenSet[str] = frozenset(
    {THROUGH_FULL, THROUGH_TRAJECTORY, THROUGH_LOCATIONS}
)


class ThroughError(ValueError):
    """Invalid ``through`` value."""


def normalize_through(value: object | None) -> str:
    if value is None or value == "":
        return THROUGH_FULL
    text = str(value).strip().lower()
    if text not in THROUGH_VALUES:
        raise ThroughError(
            f"Invalid through={value!r}. Expected one of: "
            + ", ".join(sorted(THROUGH_VALUES))
        )
    return text


def run_plan_engines(through: str) -> bool:
    return normalize_through(through) == THROUGH_FULL


def run_locations_report(through: str) -> bool:
    return normalize_through(through) in (THROUGH_FULL, THROUGH_LOCATIONS)
