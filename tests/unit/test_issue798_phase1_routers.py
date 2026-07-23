"""
Issue #798 Phase 1: composition root imports canonical routers (no empty/shim modules).
"""

from __future__ import annotations

import importlib.util
from typing import Iterable, List


def _collect_route_paths(routes: Iterable) -> List[str]:
    """Flatten FastAPI/_IncludedRouter nested route tables to path strings."""
    paths: List[str] = []
    for route in routes:
        path = getattr(route, "path", None)
        if path is not None:
            paths.append(path)
        original = getattr(route, "original_router", None)
        if original is not None and hasattr(original, "routes"):
            paths.extend(_collect_route_paths(original.routes))
        nested = getattr(route, "routes", None)
        if nested:
            paths.extend(_collect_route_paths(nested))
    return paths


def test_legacy_router_shim_modules_removed():
    assert importlib.util.find_spec("app.routes.reports") is None
    assert importlib.util.find_spec("app.routes.api_flow") is None
    assert importlib.util.find_spec("app.routes.api_bidirectional") is None


def test_canonical_flow_and_bidirectional_routers_importable():
    from app.api.flow import router as flow_router
    from app.api.bidirectional import router as bi_router

    assert flow_router is not None
    assert bi_router is not None
    assert len(flow_router.routes) > 0
    assert len(bi_router.routes) > 0


def test_main_keeps_reports_ui_page_without_empty_reports_router_module():
    """
    Phase 1 removed empty ``app.routes.reports`` — not the authenticated UI page.

    ``GET /reports`` from ``app.routes.ui`` remains the Reports workspace.
    Reports JSON/API remains under ``/api/reports``.
    """
    from app.main import app
    from app.routes.ui import reports as ui_reports_endpoint

    paths = _collect_route_paths(app.routes)

    assert "/reports" in paths
    assert any(p == "/api/reports" or p.startswith("/api/reports/") for p in paths)
    assert any("flow" in p for p in paths)

    # UI page handler still lives on the ui router (not a deleted empty module)
    assert ui_reports_endpoint.__module__ == "app.routes.ui"


def test_dead_flow_csv_audit_helpers_removed():
    import app.core.flow.flow as flow_mod

    assert not hasattr(flow_mod, "_ShardWriter")
    assert not hasattr(flow_mod, "_write_index_csv")
    assert not hasattr(flow_mod, "_write_topk_csv")
