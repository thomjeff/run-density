"""Issue #868: Overview poll interval, footer year, Last updated, display TZ."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.utils.constants import DISPLAY_TIMEZONE
from app.utils.display_time import format_local_display_datetime

REPO_ROOT = Path(__file__).resolve().parents[2]
PROGRESS_JS = REPO_ROOT / "frontend" / "static" / "js" / "run_overview_progress.js"
OVERVIEW_HTML = REPO_ROOT / "frontend" / "templates" / "pages" / "overview.html"
BASE_HTML = REPO_ROOT / "frontend" / "templates" / "base.html"
DASHBOARD_HTML = REPO_ROOT / "frontend" / "templates" / "pages" / "dashboard.html"


def test_overview_progress_polls_every_15s():
    src = PROGRESS_JS.read_text(encoding="utf-8")
    assert "return 15000;" in src
    assert "4000 : 2000" not in src
    assert "Math.min(delayMs(), 2500)" not in src
    assert "setTimeout(tick, delayMs())" in src
    assert "setInterval(function ()" in src
    overview = OVERVIEW_HTML.read_text(encoding="utf-8")
    assert "run_overview_progress.js?v=868" in overview


def test_footer_year_is_2026():
    src = BASE_HTML.read_text(encoding="utf-8")
    assert "&copy; 2026 Runflow" in src
    assert "&copy; 2025 Runflow" not in src


def test_run_history_has_no_stuck_last_updated():
    src = DASHBOARD_HTML.read_text(encoding="utf-8")
    assert 'id="last-updated"' not in src
    assert "Last updated:" not in src


def test_display_timezone_is_halifax():
    assert DISPLAY_TIMEZONE == "America/Halifax"


def test_format_local_display_datetime_converts_utc():
    # 16:00 UTC in August is 13:00 Atlantic Daylight (GMT-3).
    utc = datetime(2026, 8, 16, 16, 0, tzinfo=timezone.utc).isoformat()
    assert format_local_display_datetime(utc) == "08-16 13:00"
    naive = "2026-08-16T16:00:00"
    assert format_local_display_datetime(naive) == "08-16 13:00"
    assert format_local_display_datetime("") == ""
