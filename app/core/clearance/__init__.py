"""Authored clearance / dependency model (Issue #832).

Package-root ``clearance.json``: pair and group (AND) reopen rules.
Clearance time is last runner at the Locations **point**, not Flow zones
and not Stream Passage pin windows.
"""

from app.core.clearance.model import (
    CLEAR_WHEN_LAST_RUNNER,
    ClearanceValidationError,
    empty_clearance_doc,
    subject_key,
    validate_clearance_doc,
)
from app.core.clearance.playbook import (
    attach_clearance_to_locations,
    build_clearance_playbook,
)
from app.core.clearance.storage import (
    load_config_clearance,
    save_config_clearance,
)
from app.core.clearance.subjects import list_package_clearance_subjects

__all__ = [
    "CLEAR_WHEN_LAST_RUNNER",
    "ClearanceValidationError",
    "attach_clearance_to_locations",
    "build_clearance_playbook",
    "empty_clearance_doc",
    "list_package_clearance_subjects",
    "load_config_clearance",
    "save_config_clearance",
    "subject_key",
    "validate_clearance_doc",
]
