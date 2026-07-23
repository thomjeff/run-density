"""Issue #798 Phase 6: density report stack renamed under app.core.reports.density."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest


PROD_FILES = [
    Path("app/density_report.py"),
    Path("app/save_bins.py"),
    Path("app/core/v2/reports.py"),
]


def test_canonical_imports():
    from app.core.reports.density import apply_flagging, generate_density_report
    from app.core.reports.density.template_engine import DensityReportTemplateEngine
    from app.density_report import (
        generate_density_report_markdown,
        generate_new_density_report_issue246,
    )

    assert callable(generate_density_report)
    assert callable(apply_flagging)
    assert DensityReportTemplateEngine is not None
    assert generate_new_density_report_issue246 is generate_density_report_markdown


def test_shims_warn_and_reexport():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        from app import new_density_report as legacy_report
        from app import new_flagging as legacy_flagging
        from app import new_density_template_engine as legacy_engine

    messages = " ".join(str(w.message) for w in caught if issubclass(w.category, DeprecationWarning))
    assert "deprecated" in messages.lower()

    from app.core.reports.density.report import generate_density_report
    from app.core.reports.density.flagging import apply_flagging
    from app.core.reports.density.template_engine import DensityReportTemplateEngine

    assert legacy_report.generate_new_density_report is generate_density_report
    assert legacy_flagging.apply_new_flagging is apply_flagging
    assert legacy_engine.NewDensityTemplateEngine is DensityReportTemplateEngine


def test_production_modules_do_not_import_app_new_star():
    offenders = []
    for path in PROD_FILES:
        text = path.read_text(encoding="utf-8")
        for needle in ("from app.new_", "import app.new_"):
            if needle in text:
                offenders.append(f"{path}:{needle}")
    assert not offenders, offenders
