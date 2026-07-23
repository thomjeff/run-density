"""Canonical density Markdown report stack (Issue #798 Phase 6)."""

from app.core.reports.density.report import generate_density_report
from app.core.reports.density.template_engine import DensityReportTemplateEngine
from app.core.reports.density.flagging import apply_flagging

__all__ = [
    "generate_density_report",
    "DensityReportTemplateEngine",
    "apply_flagging",
]
