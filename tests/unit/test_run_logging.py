"""Issue #870: run file log is not the root logger and omits HTTP polls."""

from __future__ import annotations

import logging

from app.utils.run_logging import OmitHttpPollsFilter, RunLogHandler


def test_omit_http_polls_filter():
    f = OmitHttpPollsFilter()
    pipeline = logging.LogRecord("app.core.v2.pipeline", logging.INFO, "", 0, "ok", (), None)
    routes = logging.LogRecord("app.routes.api_dashboard", logging.WARNING, "", 0, "poll", (), None)
    uvicorn = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, "GET /api", (), None)
    assert f.filter(pipeline)
    assert not f.filter(routes)
    assert not f.filter(uvicorn)


def test_run_log_attaches_to_app_not_root(tmp_path):
    app_logger = logging.getLogger("app")
    root = logging.getLogger()
    with RunLogHandler("rid870", tmp_path) as handler:
        assert handler.file_handler is not None
        assert handler.file_handler in app_logger.handlers
        assert handler.file_handler not in root.handlers
        logging.getLogger("app.core.v2.pipeline").info("Density compute: 1.0s")
        logging.getLogger("app.routes.api_dashboard").warning("Failed to load meta.json")
        logging.getLogger("uvicorn.access").info('GET /api/runs/rid870/progress')

    text = (tmp_path / "analysis" / "rid870" / "logs" / "app.log").read_text()
    assert "Density compute: 1.0s" in text
    assert "Run rid870 started" in text
    assert "Run rid870 completed" in text
    assert "====" not in text
    assert "Failed to load" not in text
    assert "GET /api" not in text
