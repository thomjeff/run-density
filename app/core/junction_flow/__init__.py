"""Junction Flow analysis (Issue #818)."""

from app.core.junction_flow.compute import (
    MERGE_PARTNER_EVENTS,
    NODE_DWELL_SEC,
    InteractionResult,
    analyze_interaction,
    analyze_junction,
    analyze_junctions_doc,
    interaction_to_dict,
    prepare_runners_by_event,
    result_to_ui_payload,
)
from app.core.junction_flow.descriptions import (
    format_interaction_description,
    role_headline_labels,
)

__all__ = [
    "MERGE_PARTNER_EVENTS",
    "NODE_DWELL_SEC",
    "InteractionResult",
    "analyze_interaction",
    "analyze_junction",
    "analyze_junctions_doc",
    "format_interaction_description",
    "interaction_to_dict",
    "prepare_runners_by_event",
    "result_to_ui_payload",
    "role_headline_labels",
]
