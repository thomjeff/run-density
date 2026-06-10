"""Tests for snap-to-route profile resolution (Issue #789)."""

import pytest
from fastapi import HTTPException

from app.routes.api_course import _routing_base_for_profile


def test_default_profile_bases(monkeypatch):
    monkeypatch.delenv("OSRM_ROUTE_URL", raising=False)
    for key in ("FOOT", "BIKE", "CAR"):
        monkeypatch.delenv(f"OSRM_ROUTE_URL_{key}", raising=False)
    assert "routed-foot" in _routing_base_for_profile("foot")
    assert "routed-bike" in _routing_base_for_profile("bike")
    assert "project-osrm" in _routing_base_for_profile("car")
    # Default (blank/None) falls back to car
    assert _routing_base_for_profile("") == _routing_base_for_profile("car")


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("OSRM_ROUTE_URL_FOOT", "http://localhost:5000/route/v1/foot/")
    assert _routing_base_for_profile("foot") == "http://localhost:5000/route/v1/foot"
    # Legacy OSRM_ROUTE_URL still overrides car only
    monkeypatch.delenv("OSRM_ROUTE_URL_CAR", raising=False)
    monkeypatch.setenv("OSRM_ROUTE_URL", "http://legacy/route/v1/driving")
    assert _routing_base_for_profile("car") == "http://legacy/route/v1/driving"
    assert "routed-bike" in _routing_base_for_profile("bike")


def test_unknown_profile_rejected():
    with pytest.raises(HTTPException):
        _routing_base_for_profile("horse")
