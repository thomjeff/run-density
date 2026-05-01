"""
Finish-area operational PDF (Issue #743 extension).

Generates one PDF per analysis day from finish_times.csv:
- Bar chart: predicted finishers by 20-minute block (event=all)
- Cumulative finishers curve (same ordering as windows)
- Table: time block, count, operational tier (Low / Moderate / High / Peak)

Uses matplotlib (Agg) + ReportLab; matches existing stack (see one_pager.py).
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any, List, Optional
from xml.sax.saxutils import escape

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)


def _operational_tier(count: int, max_count: int) -> str:
    """Relative-to-peak labels for finish-area demand (same day)."""
    if count <= 0 or max_count <= 0:
        return "—"
    ratio = count / max_count
    if ratio >= 0.85:
        return "Peak / surge"
    if ratio >= 0.45:
        return "High"
    if ratio >= 0.12:
        return "Moderate"
    return "Low"


def _window_label(start: str, end: str) -> str:
    """Compact label for charts/tables: HH:MM–HH:MM (strip seconds if present)."""
    def short(t: str) -> str:
        t = t.strip()
        if len(t) >= 8 and t.count(":") >= 2:
            return t[:5]
        return t

    return f"{short(start)}–{short(end)}"


def _build_charts_png(
    labels: List[str],
    counts: List[int],
) -> io.BytesIO:
    """Stacked bar + cumulative line; returns PNG bytes buffer."""
    n = len(labels)
    cum = []
    s = 0
    for c in counts:
        s += c
        cum.append(s)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6.5), dpi=120)
    x = range(n)

    ax1.bar(x, counts, color="#3498db", width=0.85)
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax1.set_ylabel("Predicted finishers")
    ax1.set_title("Predicted finishers by 20-minute block — all events")
    ax1.grid(axis="y", alpha=0.3)
    ax1.set_axisbelow(True)

    ax2.plot(x, cum, color="#2980b9", marker="o", markersize=4)
    ax2.fill_between(list(x), cum, alpha=0.15, color="#3498db")
    ax2.set_xticks(list(x))
    ax2.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax2.set_ylabel("Cumulative finishers")
    ax2.set_title("Cumulative predicted finishers")
    ax2.grid(axis="y", alpha=0.3)
    ax2.set_axisbelow(True)

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _takeaway_text(
    day_name: str,
    labels: List[str],
    counts: List[int],
    total_runners: Optional[int],
) -> str:
    """Short operational narrative from peaks and sustained high blocks."""
    if not counts:
        return ""
    mx = max(counts)
    peak_idx = counts.index(mx)
    peak_label = labels[peak_idx]

    high_thresh = 0.45 * mx
    surge_windows = [labels[i] for i, c in enumerate(counts) if c >= high_thresh]
    if len(surge_windows) > 3:
        surge_span = f"{surge_windows[0]} through {surge_windows[-1]}"
    elif surge_windows:
        surge_span = ", ".join(surge_windows)
    else:
        surge_span = peak_label

    lines = [
        f"<b>Peak demand</b> occurs in <b>{peak_label}</b> ({mx} predicted finishers in that 20-minute block).",
        f"<b>High-demand windows</b> (≥45% of peak): {surge_span}.",
    ]
    if total_runners is not None:
        sum_counts = sum(counts)
        match = "matches" if sum_counts == total_runners else "should match"
        lines.append(
            f"Sum of finish-window totals ({sum_counts}) {match} declared runners for {day_name} ({total_runners}) in analysis.json."
        )
    return " ".join(lines)


def generate_finish_area_demand_pdf(
    *,
    finish_times_csv: Path,
    output_pdf: Path,
    day_display_name: str,
    run_id: str,
    expected_runner_total: Optional[int] = None,
) -> bool:
    """
    Write operational finish-area PDF next to finish_times.csv.

    Args:
        finish_times_csv: Path to finish_times.csv for this day
        output_pdf: e.g. .../reports/finish_area_demand.pdf
        day_display_name: "Saturday" | "Sunday"
        run_id: Run identifier for header
        expected_runner_total: Optional QA total from analysis.json (runners that day)

    Returns:
        True if PDF written.
    """
    if not finish_times_csv.exists():
        logger.warning("finish_area PDF: missing %s", finish_times_csv)
        return False

    df = pd.read_csv(finish_times_csv)
    if df.empty:
        logger.warning("finish_area PDF: empty CSV %s", finish_times_csv)
        return False

    all_rows = df[df["event"].astype(str).str.lower() == "all"].copy()
    if all_rows.empty:
        logger.warning("finish_area PDF: no 'all' rows in %s", finish_times_csv)
        return False

    all_rows = all_rows.sort_values(
        ["time_window_start", "time_window_end"]
    ).reset_index(drop=True)

    labels = [
        _window_label(str(r["time_window_start"]), str(r["time_window_end"]))
        for _, r in all_rows.iterrows()
    ]
    counts = [int(r["count"]) for _, r in all_rows.iterrows()]
    max_c = max(counts)

    tiers = [_operational_tier(c, max_c) for c in counts]

    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    chart_buf = _build_charts_png(labels, counts)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "title",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=12,
    )
    sub_style = ParagraphStyle(
        "sub",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#555555"),
        spaceAfter=14,
    )

    doc = SimpleDocTemplate(
        str(output_pdf),
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
    )
    story: List[Any] = []

    story.append(
        Paragraph(
            f"{day_display_name} — finish-area demand (predicted)",
            title_style,
        )
    )
    story.append(
        Paragraph(
            f"Run <b>{escape(str(run_id))}</b> · Source: <i>finish_times.csv</i> "
            "(combined event flow per window)",
            sub_style,
        )
    )

    img = RLImage(chart_buf, width=7 * inch, height=4.55 * inch)
    story.append(img)
    story.append(Spacer(1, 14))

    table_data: List[List[str]] = [
        ["Time block", "Predicted finishers", "Operational signal"],
    ]
    for lab, cnt, tier in zip(labels, counts, tiers):
        table_data.append([lab, str(cnt), tier])

    t = Table(table_data, colWidths=[2.6 * inch, 1.4 * inch, 2.4 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ecf0f1")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bdc3c7")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 16))

    takeaway = _takeaway_text(day_display_name, labels, counts, expected_runner_total)
    story.append(Paragraph("<b>Operational summary</b>", styles["Heading2"]))
    story.append(Paragraph(takeaway, styles["Normal"]))

    doc.build(story)
    logger.info("Wrote finish-area PDF: %s", output_pdf)
    return True


def expected_runners_for_day(analysis_config: dict, day_code: str) -> Optional[int]:
    """Sum analysis.json runners field for events on this day."""
    if not analysis_config or "events" not in analysis_config:
        return None
    total = 0
    found = False
    for ev in analysis_config["events"]:
        if not isinstance(ev, dict):
            continue
        if str(ev.get("day", "")).lower() != day_code.lower():
            continue
        n = ev.get("runners")
        if n is not None:
            total += int(n)
            found = True
    return total if found else None
