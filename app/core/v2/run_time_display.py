"""Format analysis wall-clock duration for Plan → Run History (Issue #964)."""

from __future__ import annotations

from typing import Any, Optional, Tuple


def format_elapsed_mmss(total_elapsed_seconds: float) -> str:
    """
    Format elapsed seconds as mm:ss (minutes may exceed 59).

    Examples: 32.6 → \"00:32\", 300.6 → \"05:00\", 3725 → \"62:05\".
    """
    total = max(0, int(round(float(total_elapsed_seconds))))
    minutes, seconds = divmod(total, 60)
    return f"{minutes:02d}:{seconds:02d}"


def resolve_run_time_display(
    *,
    total_elapsed_seconds: Any = None,
    stored_format: Any = None,
) -> Tuple[Optional[str], Optional[float]]:
    """
    Prefer ``total_elapsed_seconds`` as source of truth for mm:ss display.

    Returns ``(mmss_string_or_None, seconds_or_None)``.
    Does not treat ``00:SS`` as legacy hh:mm — writers already emit mm:ss (#638/#964).
    """
    seconds: Optional[float] = None
    if total_elapsed_seconds is not None:
        try:
            seconds = float(total_elapsed_seconds)
        except (TypeError, ValueError):
            seconds = None

    if seconds is not None:
        return format_elapsed_mmss(seconds), seconds

    if stored_format is None or stored_format == "":
        return None, None

    text = str(stored_format).strip()
    if ":" in text:
        parts = text.split(":")
        if len(parts) == 2:
            try:
                minutes = int(parts[0])
                secs = int(parts[1])
            except ValueError:
                return text, None
            return f"{minutes:02d}:{secs:02d}", float(minutes * 60 + secs)
        return text, None

    try:
        seconds = float(text)
    except ValueError:
        return text, None
    return format_elapsed_mmss(seconds), seconds
