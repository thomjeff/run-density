"""Format timestamps for UI display in DISPLAY_TIMEZONE (Issue #868)."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.utils.constants import DISPLAY_DATETIME_FMT, DISPLAY_TIMEZONE


def format_local_display_datetime(
    created_at: str,
    fmt: str = DISPLAY_DATETIME_FMT,
) -> str:
    """Convert an ISO timestamp to DISPLAY_TIMEZONE for run-history labels."""
    if not created_at:
        return ""
    try:
        dt = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ZoneInfo(DISPLAY_TIMEZONE)).strftime(fmt)
    except Exception:
        text = str(created_at)
        return text[:16] if len(text) > 16 else text
