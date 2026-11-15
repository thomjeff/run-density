"""Issue #964: Run History mm:ss display from total_elapsed_seconds."""

from app.core.v2.run_time_display import format_elapsed_mmss, resolve_run_time_display


def test_format_elapsed_mmss_sub_minute():
    assert format_elapsed_mmss(32.6) == "00:33"
    assert format_elapsed_mmss(23.4) == "00:23"
    assert format_elapsed_mmss(0) == "00:00"


def test_format_elapsed_mmss_multi_minute():
    assert format_elapsed_mmss(300.6) == "05:01"
    assert format_elapsed_mmss(3725) == "62:05"


def test_resolve_prefers_seconds_over_legacy_shaped_string():
    # Stored "00:32" must stay 32 seconds, not become 32:00 via hh:mm rewrite
    mmss, seconds = resolve_run_time_display(
        total_elapsed_seconds=32.646,
        stored_format="00:32",
    )
    assert mmss == "00:33"
    assert seconds == 32.646


def test_resolve_falls_back_to_mmss_string():
    mmss, seconds = resolve_run_time_display(
        total_elapsed_seconds=None,
        stored_format="05:00",
    )
    assert mmss == "05:00"
    assert seconds == 300.0
