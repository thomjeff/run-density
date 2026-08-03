"""Unit tests for analysis enqueue threading (#825 follow-up)."""

from __future__ import annotations

import threading
import time

from app.core.v2 import analysis_submit


def test_enqueue_analysis_run_starts_daemon_thread(monkeypatch):
    started = threading.Event()

    def fake_run(**kwargs):
        assert kwargs["run_id"] == "enqueue-test"
        started.set()
        time.sleep(0.05)

    monkeypatch.setattr(analysis_submit, "run_analysis_background", fake_run)

    thread = analysis_submit.enqueue_analysis_run(
        events=[],
        segments_file="segments.csv",
        locations_file="locations.csv",
        flow_file="flow.csv",
        data_dir="/tmp",
        run_id="enqueue-test",
        request_payload={},
    )
    assert thread.daemon is True
    assert started.wait(timeout=2.0)
    thread.join(timeout=2.0)
    assert not thread.is_alive()
