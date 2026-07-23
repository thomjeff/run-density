"""
Issue #798 Phase 5: density report bin/window provenance from bins artifacts.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from app.core.bin.provenance import BinProvenanceError, resolve_bin_report_params


def _sample_bins(bin_km: float = 0.2, window_s: int = 120, n: int = 4) -> pd.DataFrame:
    t0 = datetime(2026, 7, 1, 11, 0, tzinfo=timezone.utc)
    rows = []
    for i in range(n):
        start = t0 + timedelta(seconds=i * window_s)
        end = start + timedelta(seconds=window_s)
        rows.append(
            {
                "bin_size_km": bin_km,
                "t_start": start.isoformat().replace("+00:00", "Z"),
                "t_end": end.isoformat().replace("+00:00", "Z"),
            }
        )
    return pd.DataFrame(rows)


def test_resolve_bin_report_params_from_bins():
    params = resolve_bin_report_params(_sample_bins(bin_km=0.2, window_s=120))
    assert params["bin_km"] == 0.2
    assert params["step_km"] == 0.2
    assert params["window_s"] == 120
    assert params["window_seconds"] == 120


def test_resolve_rejects_empty_and_missing_columns():
    with pytest.raises(BinProvenanceError):
        resolve_bin_report_params(pd.DataFrame())
    with pytest.raises(BinProvenanceError):
        resolve_bin_report_params(pd.DataFrame({"bin_size_km": [0.2]}))
    with pytest.raises(BinProvenanceError):
        resolve_bin_report_params(
            pd.DataFrame(
                {
                    "t_start": ["2026-07-01T11:00:00Z"],
                    "t_end": ["2026-07-01T11:02:00Z"],
                }
            )
        )


def test_new_density_report_context_uses_artifact_values(tmp_path, monkeypatch):
    """Context must not invent 30s / 0.2km when bins say otherwise."""
    from app.core.reports.density import report as ndr

    bins_df = _sample_bins(bin_km=0.15, window_s=90)
    bins_df["flag_severity"] = "none"
    bins_df["segment_id"] = "A1"
    segments_df = pd.DataFrame({"seg_id": ["A1"], "width_m": [4.0]})
    segment_windows_df = pd.DataFrame()

    monkeypatch.setattr(
        ndr,
        "load_parquet_sources",
        lambda *a, **k: {
            "bins": bins_df,
            "segments": segments_df,
            "segment_windows": segment_windows_df,
        },
    )
    monkeypatch.setattr(ndr, "load_segment_metrics_from_json", lambda p: {"A1": {"peak_rate": 0.0}})
    monkeypatch.setattr(ndr, "load_flags_from_json", lambda p: {"A1": {"worst_severity": "none"}})
    monkeypatch.setattr(
        ndr,
        "convert_json_to_segment_summary",
        lambda *a, **k: pd.DataFrame(
            {
                "segment_id": ["A1"],
                "total_bins": [1],
                "flagged_bins": [0],
                "worst_severity": ["none"],
                "peak_los": ["A"],
                "peak_density": [0.0],
                "peak_rate_per_m_per_min": [0.0],
            }
        ),
    )

    class _FakeEngine:
        def generate_report(self, context, **kwargs):
            assert context["window_s"] == 90
            assert context["bin_km"] == 0.15
            assert context["window_seconds"] == 90
            return "# report"

    monkeypatch.setattr(ndr, "DensityReportTemplateEngine", _FakeEngine)
    monkeypatch.setattr(ndr, "load_density_rulebook", lambda: {})
    monkeypatch.setattr(
        ndr,
        "create_flagging_config",
        lambda *a, **k: type("C", (), {"rate_warn_threshold": 1.0, "rate_critical_threshold": 2.0})(),
    )

    metrics = tmp_path / "segment_metrics.json"
    metrics.write_text("{}")
    results = ndr.generate_density_report(
        reports_dir=tmp_path,
        segment_metrics_path=metrics,
        app_version="test",
    )
    assert results["context"]["window_s"] == 90
    assert results["context"]["bin_km"] == 0.15


def test_no_fabricated_window_bin_literals_in_density_report():
    from pathlib import Path

    text = Path("app/core/reports/density/report.py").read_text(encoding="utf-8")
    assert "window_s': 30" not in text
    assert 'window_s": 30' not in text
    assert "bin_km': 0.2" not in text
    assert 'bin_km": 0.2' not in text
    assert "TODO: Get from actual data" not in text
