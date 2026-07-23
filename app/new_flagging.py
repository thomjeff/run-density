"""
Deprecated import path — use ``app.core.reports.density.flagging``.

Issue #798 Phase 6: thin forwarding shim (removal after one release).
"""

from __future__ import annotations

import warnings

warnings.warn(
    "app.new_flagging is deprecated; import from app.core.reports.density.flagging",
    DeprecationWarning,
    stacklevel=2,
)

from app.core.reports.density.flagging import (  # noqa: E402,F401
    FlaggingConfig,
    FlaggingConfig as NewFlaggingConfig,
    _load_and_apply_segment_metadata,
    apply_flagging,
    apply_flagging as apply_new_flagging,
    calculate_rate_per_m_per_min,
    get_flagged_bins,
    get_flagged_bins as get_flagged_bins_new,
    get_flagging_statistics,
    get_flagging_statistics as get_flagging_statistics_new,
    get_severity_rank,
    get_severity_rank as get_severity_rank_new,
    summarize_segment_flags,
    summarize_segment_flags as summarize_segment_flags_new,
)

__all__ = [
    "FlaggingConfig",
    "NewFlaggingConfig",
    "apply_flagging",
    "apply_new_flagging",
    "calculate_rate_per_m_per_min",
    "get_flagged_bins",
    "get_flagged_bins_new",
    "get_severity_rank",
    "get_severity_rank_new",
    "summarize_segment_flags",
    "summarize_segment_flags_new",
    "get_flagging_statistics",
    "get_flagging_statistics_new",
    "_load_and_apply_segment_metadata",
]
