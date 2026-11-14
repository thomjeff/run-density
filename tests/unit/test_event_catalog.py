"""Distances and events catalog (Issue #955)."""

import csv
import re
from pathlib import Path

import pandas as pd
import pytest

from app.core.config_package.saved_courses import (
    build_package_race_exports,
    save_org_course,
    set_package_course_assignments,
)
from app.core.config_package.segment_recipes import save_package_segment_manifest
from app.core.config_package.storage import (
    create_config_package,
    load_config_manifest,
    normalize_package_events,
    resolve_config_package_path,
    save_config_manifest,
)
from app.utils import constants, execute_constants
from tests.unit.test_saved_courses import _patch_roots, _seed_org_legs

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_execute_constants_mirror_catalog():
    assert execute_constants.COURSE_EVENT_IDS == constants.COURSE_EVENT_IDS
    assert execute_constants.EVENT_LABELS == constants.EVENT_LABELS


def test_every_event_distance_is_a_course_distance():
    for event in constants.RACE_EVENTS:
        assert re.fullmatch(r"[a-z0-9_]+", event["id"])
        assert event["distance"] in constants.COURSE_DISTANCE_IDS
    # Course exports use the distance id as their event column.
    for distance in constants.COURSE_DISTANCE_IDS:
        assert distance in constants.COURSE_EVENT_IDS


def test_5k_is_active_and_elite_open_are_legacy():
    assert "5k" in constants.ACTIVE_EVENT_IDS
    assert "elite" not in constants.ACTIVE_EVENT_IDS
    assert "open" not in constants.ACTIVE_EVENT_IDS
    assert {"elite", "open", "5k"} <= set(constants.COURSE_EVENT_IDS)
    assert constants.EVENT_DISTANCES["elite"] == "5k"
    assert constants.event_label("5k") == "5K"
    assert constants.event_label("full", long=True) == "Full Marathon"
    assert constants.event_label("ultra") == "ULTRA"


def test_normalize_package_events_legacy_rules():
    assert normalize_package_events(["elite", "open"]) == ["elite", "open"]
    assert normalize_package_events(["5k"], allow_legacy=False) == ["5k"]
    with pytest.raises(ValueError, match="legacy"):
        normalize_package_events(["5k", "elite"], allow_legacy=False)


def test_create_package_rejects_legacy_events(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root", lambda: tmp_path
    )
    with pytest.raises(ValueError, match="legacy"):
        create_config_package("Old", "", event_day="sat", package_events=["elite"])


def test_save_org_course_validates_distance_not_event(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="Unsupported distance"):
        save_org_course(name="X", distance="elite", recipe=["01"])
    with pytest.raises(ValueError, match="at least one leg"):
        save_org_course(name="X", distance="5k", recipe=[])


def _seed_package(config_id, events):
    save_package_segment_manifest(
        config_id,
        {
            "version": 1,
            "leg_source": "org",
            "legs": [],
            "recipes": {e: [] for e in events},
            "flow_overrides": [],
        },
    )


def _segment_flags(package_path, event):
    with open(package_path / "segments.csv", newline="", encoding="utf-8") as fh:
        return {row[event] for row in csv.DictReader(fh)}


def test_5k_course_and_package_race_exports(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _seed_org_legs(tmp_path, leg_ids=("47", "48"))
    save_org_course(name="5K Downtown", distance="5k", recipe=["47", "48"])
    course_id = "01"
    assert (tmp_path / "org" / "courses" / course_id / "5k.gpx").is_file()
    save_org_course(name="10K", distance="10k", recipe=["47"], course_id="10k-a")

    config_id = create_config_package(
        "FM2027 (Sat)", "", event_day="sat", package_events=["5k"]
    )["config_id"]
    _seed_package(config_id, ["5k"])
    with pytest.raises(ValueError, match="needs a 5k course"):
        set_package_course_assignments(config_id, {"5k": "10k-a"})
    set_package_course_assignments(config_id, {"5k": course_id})

    build_package_race_exports(config_id)
    package_path = resolve_config_package_path(config_id)
    assert (package_path / "5k.gpx").is_file()
    assert _segment_flags(package_path, "5k") == {"y"}
    assert _segment_flags(package_path, "full") == {"n"}


def test_legacy_package_assigns_one_5k_course_to_elite_and_open(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _seed_org_legs(tmp_path, leg_ids=("47", "48"))
    save_org_course(name="5K", distance="5k", recipe=["47", "48"], course_id="5k-a")
    config_id = create_config_package(
        "FM2026 (Sat)", "", event_day="sat", package_events=["5k"]
    )["config_id"]
    package_path = resolve_config_package_path(config_id)
    manifest = load_config_manifest(config_id)
    manifest["package_events"] = ["elite", "open"]
    save_config_manifest(package_path, manifest)
    _seed_package(config_id, ["elite", "open"])

    set_package_course_assignments(config_id, {"elite": "5k-a", "open": "5k-a"})
    build_package_race_exports(config_id)
    assert _segment_flags(package_path, "elite") == {"y"}
    assert _segment_flags(package_path, "open") == {"y"}
    assert (package_path / "elite.gpx").is_file()
    assert (package_path / "open.gpx").is_file()


def test_pipeline_helpers_handle_5k():
    from app.core.density.compute import get_event_intervals
    from app.core.flow.flow import _get_event_distance_range, _get_segment_events

    row = pd.Series(
        {"full": "n", "5k": "y", "10K": "y", "5k_from_km": 1.0, "5k_to_km": 2.5}
    )
    assert _get_segment_events(row) == ["10k", "5k"]
    assert _get_event_distance_range(row, "5k") == (1.0, 2.5)
    assert get_event_intervals("5k", {"5k_from_km": 1.0, "5k_to_km": 2.5}) == (
        1.0,
        2.5,
    )


_HARD_CODED_EVENT_LIST = re.compile(
    r"""["']full["']\s*,\s*["']half["']\s*,\s*["']10k["']\s*,\s*["']elite["']""",
    re.IGNORECASE,
)


def test_no_hard_coded_event_lists_outside_catalog():
    allowed = {
        REPO_ROOT / "app" / "utils" / "constants.py",
        REPO_ROOT / "app" / "utils" / "execute_constants.py",
    }
    offenders = []
    for base, pattern in (
        ("app", "*.py"),
        ("frontend", "*.js"),
        ("frontend", "*.html"),
    ):
        for path in (REPO_ROOT / base).rglob(pattern):
            if path in allowed:
                continue
            if _HARD_CODED_EVENT_LIST.search(path.read_text(encoding="utf-8")):
                offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []
