"""
Sample / package race templates (Issue #798 Phase 8).

Algorithm defaults stay in ``app.utils.constants``. Race-specific schedules,
hotspot segment IDs, and map centers live here so they are not universal law.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Set

from app.core.race_templates.sample_fredericton import SAMPLE_FREDERICTON

# Registry of named templates (extend when adding races).
RACE_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "sample_fredericton": SAMPLE_FREDERICTON,
}

DEFAULT_RACE_TEMPLATE_ID = "sample_fredericton"


def get_race_template(template_id: str | None = None) -> Dict[str, Any]:
    """Return a race template dict (defaults to sample_fredericton)."""
    from app.utils.env import env_str

    tid = (template_id or env_str("RACE_TEMPLATE", DEFAULT_RACE_TEMPLATE_ID)).strip()
    if tid not in RACE_TEMPLATES:
        raise KeyError(
            f"Unknown race template '{tid}'. Known: {sorted(RACE_TEMPLATES)}"
        )
    return RACE_TEMPLATES[tid]


def get_suggested_event_schedule() -> Mapping[str, Dict[str, int]]:
    return get_race_template()["suggested_event_schedule"]


def get_hotspot_segments() -> Set[str]:
    return set(get_race_template()["hotspot_segments"])


def get_map_center() -> tuple[float, float]:
    center = get_race_template()["map_center"]
    return float(center["lat"]), float(center["lon"])


def get_v1_event_duration_minutes() -> Mapping[str, int]:
    """V1-only adapter durations (do not use for v2 analysis.json paths)."""
    return get_race_template()["v1_event_duration_minutes"]
