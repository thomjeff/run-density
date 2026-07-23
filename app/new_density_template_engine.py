"""
Deprecated import path — use ``app.core.reports.density.template_engine``.

Issue #798 Phase 6: thin forwarding shim (removal after one release).
"""

from __future__ import annotations

import warnings

warnings.warn(
    "app.new_density_template_engine is deprecated; "
    "import from app.core.reports.density.template_engine",
    DeprecationWarning,
    stacklevel=2,
)

from app.core.reports.density.template_engine import (  # noqa: E402,F401
    DensityReportTemplateEngine,
    DensityReportTemplateEngine as NewDensityTemplateEngine,
)

__all__ = [
    "DensityReportTemplateEngine",
    "NewDensityTemplateEngine",
]
