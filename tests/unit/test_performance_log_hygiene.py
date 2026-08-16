"""Issue #870: named costs and ≥1s phases at INFO; no banner noise."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from app.core.v2.performance import PerformanceMonitor, log_elapsed, phase_display_name


def test_phase_display_names():
    assert phase_display_name("phase_3_2_density_compute") == "Density compute"
    assert phase_display_name("phase_5_1_bin_generation_sun") == "Bins sun"
    assert phase_display_name("phase_10_reports") == "Reports"


def test_subsecond_setup_is_debug(caplog):
    mon = PerformanceMonitor(run_id="t")
    metrics = mon.start_phase(
        "phase_3_1_density_setup",
        phase_number="Phase 3.1",
        phase_description="Density Setup",
    )
    metrics.start_time = time.monotonic() - 0.01
    with caplog.at_level(logging.DEBUG, logger="app.core.v2.performance"):
        mon.complete_phase(
            metrics,
            phase_number="Phase 3.1",
            phase_description="Density Setup",
        )
    info_msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert not any("Density Setup" in m or "density setup" in m.lower() for m in info_msgs)
    assert not any("═" in r.getMessage() for r in caplog.records)


def test_named_cost_is_info_even_if_fast(caplog):
    mon = PerformanceMonitor(run_id="t")
    metrics = mon.start_phase(
        "phase_10_reports",
        phase_number="Phase 10",
        phase_description="Report Generation",
    )
    metrics.start_time = time.monotonic() - 0.05
    with caplog.at_level(logging.INFO, logger="app.core.v2.performance"):
        mon.complete_phase(
            metrics,
            phase_number="Phase 10",
            phase_description="Report Generation",
            summary_stats={"reports": 3},
        )
    text = caplog.text
    assert "Reports:" in text
    assert "Phase 10" not in text
    assert "═" not in text


def test_log_summary_omits_subsecond(caplog):
    mon = PerformanceMonitor(run_id="t")
    fast = mon.start_phase("phase_1_pre_analysis", phase_description="Pre-Analysis")
    fast.start_time = time.monotonic() - 0.02
    mon.complete_phase(fast, phase_description="Pre-Analysis")
    slow = mon.start_phase("phase_3_2_density_compute", phase_description="Density")
    slow.start_time = time.monotonic() - 2.5
    mon.complete_phase(slow, phase_description="Density")
    with caplog.at_level(logging.INFO, logger="app.core.v2.performance"):
        mon.log_summary()
    text = caplog.text
    assert "Timing: total" in text
    assert "Density compute" in text
    assert "Pre-Analysis" not in text
    assert "📊" not in text


def test_log_elapsed_threshold(caplog):
    with caplog.at_level(logging.DEBUG, logger="app.core.v2.performance"):
        log_elapsed("JSON persist", 0.2)
        log_elapsed("Density.md", 0.2, always_info=True)
        log_elapsed("Density compute", 32.6)
    info = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    debug = [r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG]
    assert any("Density.md: 0.2s" in m for m in info)
    assert any("Density compute: 32.6s" in m for m in info)
    assert any("JSON persist: 0.2s" in m for m in debug)
    assert not any("JSON persist" in m for m in info)


def test_no_cursor_debug_log_writes():
    root = Path(__file__).resolve().parents[2] / "app"
    offenders = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "/app/.cursor/debug.log" in text:
            offenders.append(str(path))
    assert offenders == []
