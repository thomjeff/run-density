"""Issue #798 Phase 9: cohesive extraction of bin hotspot coarsening helpers."""

from __future__ import annotations

from app.core.bin.hotspots import coarsen_plan, is_hotspot
from app.density_report import coarsen_plan as façade_coarsen
from app.density_report import is_hotspot as façade_hotspot


def test_hotspot_from_template_ids():
    assert is_hotspot("F1") is True
    assert is_hotspot("ZZ_NOT_A_HOTSPOT") is False
    assert is_hotspot("ZZ_NOT_A_HOTSPOT", peak_los="E") is True


def test_coarsen_plan_preserves_hotspots():
    assert coarsen_plan("F1", 0.1, 60) == (0.1, 60)
    bin_km, dt = coarsen_plan("ZZ", 0.1, 60)
    assert bin_km >= 0.2
    assert dt >= 120


def test_density_report_reexports_same_callables():
    assert façade_hotspot is is_hotspot
    assert façade_coarsen is coarsen_plan
