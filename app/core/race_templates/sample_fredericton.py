"""
Sample Fredericton Marathon-shaped defaults (Issue #798 Phase 8).

UI suggestions and legacy map/hotspot helpers may use this template.
v2 analysis always prefers package / request payloads over these values.
"""

from __future__ import annotations

SAMPLE_FREDERICTON = {
    "id": "sample_fredericton",
    "label": "Sample Fredericton Marathon (illustrative)",
    # UI-only suggestions when opening run-analysis (not applied server-side unless chosen).
    "suggested_event_schedule": {
        "full": {"start_time": 420, "event_duration_minutes": 390},
        "half": {"start_time": 440, "event_duration_minutes": 180},
        "10k": {"start_time": 460, "event_duration_minutes": 120},
        "elite": {"start_time": 480, "event_duration_minutes": 45},
        "open": {"start_time": 510, "event_duration_minutes": 75},
    },
    # Segments preserved preferentially during bin coarsening (sample course IDs).
    "hotspot_segments": {"F1", "H1", "J1", "J4", "J5", "K1", "L1"},
    "map_center": {"lat": 45.9620, "lon": -66.6500},
    # Deprecated v1 API durations (capitalized keys for legacy payloads).
    "v1_event_duration_minutes": {
        "elite": 45,
        "open": 75,
        "10k": 120,
        "half": 180,
        "full": 390,
        "Elite": 45,
        "Open": 75,
        "10K": 120,
        "Half": 180,
        "Full": 390,
    },
}
