"""Location helpers. Imports stay lazy so Execute can ship report_json only."""

from typing import Any

__all__ = [
    "DEFAULT_PACKAGE_RESOURCES",
    "ensure_manifest_resources",
    "locations_csv_columns",
    "normalize_location_record",
    "normalize_resource_registry",
    "suggest_location_events",
]


def __getattr__(name: str) -> Any:
    if name in {
        "DEFAULT_PACKAGE_RESOURCES",
        "ensure_manifest_resources",
        "locations_csv_columns",
        "normalize_location_record",
        "normalize_resource_registry",
    }:
        from app.core.locations import schema

        return getattr(schema, name)
    if name == "suggest_location_events":
        from app.core.locations.suggest_events import (
            suggest_location_events,
        )

        return suggest_location_events
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
