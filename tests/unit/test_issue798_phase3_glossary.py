"""
Issue #798 Phase 3: domain glossary present and light naming enforcement.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GLOSSARY = REPO_ROOT / "docs" / "architecture" / "domain-glossary.md"


REQUIRED_HEADINGS = (
    "## Product vs repository",
    "## Core nouns",
    "## Field alias map",
    "## Guidance for agents",
)

REQUIRED_PHRASES = (
    "Runflow",
    "run-density",
    "seg_id",
    "leg_id",
    "loc_id",
    "location_key",
    "event_duration_minutes",
    "step_km",
    "app.core.v2.start_time",
    "300–1200",
)


def test_domain_glossary_exists_with_required_sections():
    text = GLOSSARY.read_text(encoding="utf-8")
    assert "Issue #798 Phase 3" in text
    for heading in REQUIRED_HEADINGS:
        assert heading in text, f"Missing glossary section: {heading}"
    for phrase in REQUIRED_PHRASES:
        assert phrase in text, f"Missing glossary phrase: {phrase}"


def test_fastapi_title_is_runflow():
    from app.main import app

    assert app.title == "Runflow"


def test_core_v2_avoids_new_bare_event_duration_api_fields():
    """
    Cheap guard: analysis.json / API validation should keep the unit-suffixed wire name.
    Internal dict keys like event_durations (plural) are allowed.
    """
    from app.api.models.v2 import V2EventRequest

    fields = V2EventRequest.model_fields
    assert "event_duration_minutes" in fields
    assert "event_duration" not in fields
