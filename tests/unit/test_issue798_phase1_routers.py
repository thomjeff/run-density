"""
Issue #798 Phase 1: composition root imports canonical routers (no empty/shim modules).
"""

from __future__ import annotations

import importlib.util


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


def test_main_registers_flow_routes_without_empty_reports_prefix():
    from app.main import app

    paths = []
    for route in app.routes:
        path = getattr(route, "path", None)
        if path is not None:
            paths.append(path)

    # Empty /reports shim must be gone; UI reports API remains under /api/reports
    assert not any(p == "/reports" or p.startswith("/reports/") for p in paths)
    assert any("/api/" in p and "flow" in p for p in paths) or any(
        getattr(r, "path", "").endswith("/flow") or "flow" in getattr(r, "path", "")
        for r in app.routes
    )


def test_dead_flow_csv_audit_helpers_removed():
    import app.core.flow.flow as flow_mod

    assert not hasattr(flow_mod, "_ShardWriter")
    assert not hasattr(flow_mod, "_write_index_csv")
    assert not hasattr(flow_mod, "_write_topk_csv")
