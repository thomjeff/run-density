"""
Junction Flow v2 pipeline integration (Issue #818).

Reads package ``junctions.json`` from ``data_dir`` and computes dwell
co-presence metrics per day using constant-pace node timing.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import pandas as pd

from app.core.config_package.junctions import JUNCTIONS_NAME, empty_junctions_doc, validate_junctions_doc
from app.core.junction_flow import (
    analyze_junctions_doc,
    prepare_runners_by_event,
    result_to_ui_payload,
)
from app.core.v2.density import filter_runners_by_day
from app.core.v2.models import Day, Event

if TYPE_CHECKING:
    from app.core.v2.performance import PerformanceMonitor

logger = logging.getLogger(__name__)


def load_junctions_from_data_dir(data_dir: str | Path) -> Dict[str, Any]:
    """Load and validate junctions.json from the analysis package directory."""
    path = Path(data_dir) / JUNCTIONS_NAME
    if not path.is_file():
        logger.info("No %s in %s — Junction Flow will write empty results", JUNCTIONS_NAME, data_dir)
        return empty_junctions_doc()
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return validate_junctions_doc(raw)


def analyze_junction_flow_v2(
    *,
    events: List[Event],
    events_by_day: Dict[Day, List[Event]],
    all_runners_df: pd.DataFrame,
    data_dir: str,
    perf_monitor: Optional["PerformanceMonitor"] = None,
) -> Dict[Day, Dict[str, Any]]:
    """
    Compute Junction Flow for each analysis day.

    Returns:
        Mapping Day → result dict (ok, method, junctions[...]).
    """
    phase = None
    if perf_monitor is not None:
        phase = perf_monitor.start_phase(
            "phase_4_3_junction_flow",
            phase_number="Phase 4.3",
            phase_description="Junction Flow Compute",
        )

    junctions_doc = load_junctions_from_data_dir(data_dir)
    gun_by_event = {event.name.lower(): float(event.start_time) for event in events}
    results: Dict[Day, Dict[str, Any]] = {}

    for day, day_events in events_by_day.items():
        day_runners = filter_runners_by_day(all_runners_df, day, events)
        runners_by_event = prepare_runners_by_event(day_runners)
        # Only include guns for events on this day
        day_guns = {
            e.name.lower(): gun_by_event[e.name.lower()]
            for e in day_events
            if e.name.lower() in gun_by_event
        }
        if not (junctions_doc.get("junctions") or []):
            results[day] = {
                "ok": True,
                "method": {},
                "junctions": [],
                "notes": ["No authored junctions in package."],
            }
            continue
        day_result = analyze_junctions_doc(junctions_doc, runners_by_event, day_guns)
        results[day] = day_result
        n_ix = sum(len(j.get("interactions") or []) for j in day_result.get("junctions") or [])
        logger.info(
            "[Phase 4.3] Junction Flow day=%s junctions=%s interactions=%s",
            day.value,
            len(day_result.get("junctions") or []),
            n_ix,
        )

    if phase is not None and perf_monitor is not None:
        from app.core.v2.performance import get_memory_usage_mb

        phase.finish(memory_mb=get_memory_usage_mb())
        perf_monitor.complete_phase(
            phase,
            phase_number="Phase 4.3",
            phase_description="Junction Flow Compute",
            summary_stats={"days": len(results)},
        )

    return results


def persist_junction_flow_day(
    *,
    day_path: Path,
    day_code: str,
    day_result: Dict[str, Any],
) -> Dict[str, str]:
    """
    Write computation SSOT, UI metrics, and report CSVs for one day.

    Returns relative artifact names written.
    """
    written: Dict[str, str] = {}
    computation_dir = day_path / "computation"
    computation_dir.mkdir(parents=True, exist_ok=True)
    ui_metrics_dir = day_path / "ui" / "metrics"
    ui_metrics_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = day_path / "reports" / "junctions"
    reports_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "day": day_code,
        "ok": bool(day_result.get("ok", True)),
        "method": day_result.get("method") or {},
        "junctions": day_result.get("junctions") or [],
        "notes": day_result.get("notes") or [],
    }

    comp_path = computation_dir / "junction_flow_results.json"
    comp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    written["computation"] = str(comp_path.relative_to(day_path))

    ui_payload = result_to_ui_payload(payload)
    ui_payload["day"] = day_code
    ui_path = ui_metrics_dir / "junctions.json"
    ui_path.write_text(json.dumps(ui_payload, indent=2) + "\n", encoding="utf-8")
    written["ui_metrics"] = str(ui_path.relative_to(day_path))

    summary = {
        "day": day_code,
        "method": payload["method"],
        "junctions": [
            {
                "junction_id": j.get("junction_id"),
                "junction_label": j.get("junction_label"),
                "interactions": [
                    {
                        "id": ix.get("id"),
                        "type": ix.get("type"),
                        "side": ix.get("side"),
                        "label": ix.get("label"),
                        "description": ix.get("description"),
                        "events": ix.get("events"),
                        "window_start": ix.get("window_start"),
                        "window_end": ix.get("window_end"),
                        "window_minutes": ix.get("window_minutes"),
                        "unique_by_role_event": ix.get("unique_by_role_event"),
                        "peak_concurrent": ix.get("peak_concurrent"),
                        "field_crosstab": ix.get("field_crosstab"),
                        "headline_labels": ix.get("headline_labels") or {},
                    }
                    for ix in (j.get("interactions") or [])
                ],
            }
            for j in (payload.get("junctions") or [])
        ],
    }
    summary_path = reports_dir / "junction_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    written["summary"] = str(summary_path.relative_to(day_path))

    for j in payload.get("junctions") or []:
        jid = str(j.get("junction_id") or "junction")
        for ix in j.get("interactions") or []:
            iid = str(ix.get("id") or "ix")
            itype = str(ix.get("type") or "interaction")
            minute_rows = ix.get("minute_rows") or []
            if minute_rows:
                csv_name = f"{jid}_{iid}_{itype}_per_minute.csv"
                csv_path = reports_dir / csv_name
                with csv_path.open("w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=list(minute_rows[0].keys()))
                    writer.writeheader()
                    writer.writerows(minute_rows)
            crosstab = ix.get("field_crosstab") or []
            if crosstab:
                ct_name = f"{jid}_{iid}_{itype}_field_crosstab.csv"
                ct_path = reports_dir / ct_name
                with ct_path.open("w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=list(crosstab[0].keys()))
                    writer.writeheader()
                    writer.writerows(crosstab)

    return written
