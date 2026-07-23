"""
Deprecated import path — use ``app.core.reports.density.report``.

Issue #798 Phase 6: thin forwarding shim (removal after one release).
"""

from __future__ import annotations

import warnings

warnings.warn(
    "app.new_density_report is deprecated; import from app.core.reports.density.report",
    DeprecationWarning,
    stacklevel=2,
)

from app.core.reports.density.report import (  # noqa: E402,F401
    convert_json_to_segment_summary,
    create_flagging_config,
    generate_density_report,
    generate_density_report as generate_new_density_report,
    load_density_rulebook,
    load_flags_from_json,
    load_parquet_sources,
    load_segment_metrics_from_json,
)
from app.core.reports.density.template_engine import (  # noqa: E402,F401
    DensityReportTemplateEngine as NewDensityTemplateEngine,
)

__all__ = [
    "generate_density_report",
    "generate_new_density_report",
    "NewDensityTemplateEngine",
    "load_parquet_sources",
    "load_density_rulebook",
    "create_flagging_config",
    "load_segment_metrics_from_json",
    "load_flags_from_json",
    "convert_json_to_segment_summary",
]
