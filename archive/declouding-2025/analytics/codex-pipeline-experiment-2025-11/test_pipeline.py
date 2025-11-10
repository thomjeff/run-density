"""Tests for the analytics pipeline orchestration."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


class DummyStorage:
    """Lightweight storage service stub for tests."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.config = SimpleNamespace(
            local_reports_dir=str(base_dir / "reports"),
            use_cloud_storage=False,
            bucket_name="test-bucket",
        )

    def save_artifact_json(self, file_path: str, data):
        full_path = self.base_dir / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(json.dumps(data))
        return str(full_path)


def test_run_density_pipeline(monkeypatch, tmp_path):
    pandas_stub = ModuleType("pandas")
    pandas_stub.DataFrame = dict
    pandas_stub.read_csv = lambda *args, **kwargs: None
    pandas_stub.read_parquet = lambda *args, **kwargs: None
    pandas_stub.isna = lambda value: False
    pandas_stub.Series = dict
    pandas_stub.concat = lambda *args, **kwargs: None
    sys.modules.setdefault("pandas", pandas_stub)

    pyarrow_stub = ModuleType("pyarrow")
    pyarrow_stub.Table = SimpleNamespace(from_pylist=lambda *args, **kwargs: SimpleNamespace())
    sys.modules.setdefault("pyarrow", pyarrow_stub)

    parquet_stub = ModuleType("pyarrow.parquet")
    parquet_stub.write_table = lambda *args, **kwargs: None
    sys.modules.setdefault("pyarrow.parquet", parquet_stub)

    numpy_stub = ModuleType("numpy")
    numpy_stub.array = lambda *args, **kwargs: None
    numpy_stub.isnan = lambda value: False
    numpy_stub.isfinite = lambda value: True
    numpy_stub.nan = float("nan")
    numpy_stub.ndarray = list

    def _numpy_default(name):
        def _stub(*args, **kwargs):
            return None

        return _stub

    numpy_stub.__getattr__ = _numpy_default
    sys.modules.setdefault("numpy", numpy_stub)

    yaml_stub = ModuleType("yaml")
    yaml_stub.safe_load = lambda *args, **kwargs: {}
    sys.modules.setdefault("yaml", yaml_stub)

    google_stub = ModuleType("google")
    cloud_stub = ModuleType("google.cloud")
    storage_stub = ModuleType("google.cloud.storage")
    storage_stub.Client = lambda *args, **kwargs: None
    exceptions_stub = ModuleType("google.cloud.exceptions")
    sys.modules.setdefault("google", google_stub)
    sys.modules.setdefault("google.cloud", cloud_stub)
    sys.modules.setdefault("google.cloud.storage", storage_stub)
    sys.modules.setdefault("google.cloud.exceptions", exceptions_stub)

    fastapi_stub = ModuleType("fastapi")

    class _DummyRouter:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def post(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    class _HTTPException(Exception):
        def __init__(self, status_code=500, detail=""):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    fastapi_stub.APIRouter = _DummyRouter
    fastapi_stub.HTTPException = _HTTPException
    fastapi_stub.Query = lambda *args, **kwargs: None
    sys.modules.setdefault("fastapi", fastapi_stub)

    responses_stub = ModuleType("fastapi.responses")
    responses_stub.JSONResponse = SimpleNamespace
    sys.modules.setdefault("fastapi.responses", responses_stub)

    matplotlib_stub = ModuleType("matplotlib")
    pyplot_stub = ModuleType("matplotlib.pyplot")
    colors_stub = ModuleType("matplotlib.colors")

    class _DummyColormap:
        def set_bad(self, *args, **kwargs):
            return None

    colors_stub.LinearSegmentedColormap = SimpleNamespace(from_list=lambda *args, **kwargs: _DummyColormap())

    class _DummyPowerNorm:
        def __init__(self, *args, **kwargs):
            pass

    colors_stub.PowerNorm = _DummyPowerNorm

    matplotlib_stub.pyplot = pyplot_stub
    pyplot_stub.subplots = lambda *args, **kwargs: (SimpleNamespace(), SimpleNamespace())
    pyplot_stub.close = lambda *args, **kwargs: None
    pyplot_stub.Axes = SimpleNamespace
    matplotlib_stub.use = lambda *args, **kwargs: None
    sys.modules.setdefault("matplotlib", matplotlib_stub)
    sys.modules.setdefault("matplotlib.pyplot", pyplot_stub)
    sys.modules.setdefault("matplotlib.colors", colors_stub)

    import analytics.pipeline as pipeline

    storage = DummyStorage(tmp_path)

    monkeypatch.setattr(pipeline, "initialize_storage_service", lambda config: storage)
    monkeypatch.setattr(pipeline, "get_storage_service", lambda: storage)

    def fake_generate_density_report(*_, **kwargs):
        output_dir = Path(kwargs.get("output_dir", storage.config.local_reports_dir))
        source_dir = Path(output_dir) / "2025-01-01"
        source_dir.mkdir(parents=True, exist_ok=True)
        density_path = source_dir / "test-run-Density.md"
        density_path.write_text("density report")
        return {
            "ok": True,
            "report_path": str(density_path),
            "analysis_results": {"segments": []},
        }

    def fake_generate_flow_report(*_, **kwargs):
        output_dir = Path(kwargs.get("output_dir", storage.config.local_reports_dir))
        source_dir = Path(output_dir) / "2025-01-01"
        source_dir.mkdir(parents=True, exist_ok=True)
        flow_md = source_dir / "test-run-Flow.md"
        flow_md.write_text("flow report")
        flow_csv = source_dir / "test-run-Flow.csv"
        flow_csv.write_text("seg_id,overtaking_a,overtaking_b,copresence_a,copresence_b\n")
        return {"ok": True, "report_path": str(flow_md), "segments": []}

    monkeypatch.setattr(pipeline, "generate_density_report", fake_generate_density_report)
    monkeypatch.setattr(pipeline, "generate_temporal_flow_report", fake_generate_flow_report)
    monkeypatch.setattr(pipeline, "calculate_flow_segment_counts", lambda *_: (1, 2))

    def fake_export_ui_artifacts(reports_dir, run_id, *_args, **_kwargs):
        artifacts_dir = storage.base_dir / "artifacts" / run_id / "ui"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        (artifacts_dir / "meta.json").write_text("{}")
        return artifacts_dir

    monkeypatch.setattr(pipeline, "export_ui_artifacts", fake_export_ui_artifacts)
    monkeypatch.setattr(pipeline, "export_heatmaps_and_captions", lambda *_: (2, 1))

    summary = pipeline.run_density_pipeline("test-run", use_cloud=False)

    assert summary["final_run_id"] == "test-run"
    assert summary["heatmaps"] == {"generated": 2, "captions": 1}

    summary_path = storage.base_dir / "artifacts/test-run/ui/pipeline_summary.json"
    assert summary_path.exists()

