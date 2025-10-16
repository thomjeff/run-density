"""
New Density Template Engine for Issue #246

Implements the new report structure as specified in Issue #246:
1. Title & Metadata
2. Executive Summary
3. Methodology & Inputs
4. Start Times & Cohorts
5. Course Overview
6. Flagged Segments — Complete List
7. Flagged Bins Summary
8. Operational Heatmap (placeholder)
9. Segment Details
10. Mitigations
11. Appendix
"""

from __future__ import annotations
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import pandas as pd


class NewDensityTemplateEngine:
    """Template engine for the new density report structure per Issue #246."""
    
    def __init__(self):
        self.template_sections = [
            'title_metadata',
            'executive_summary', 
            'methodology_inputs',
            'start_times_cohorts',
            'course_overview',
            'flagged_segments_complete',
            'flagged_bins_summary',
            'operational_heatmap_placeholder',
            'segment_details',
            'mitigations',
            'appendix'
        ]
    
    def generate_report(
        self,
        context: Dict[str, Any],
        bins_df: pd.DataFrame,
        segments_df: pd.DataFrame,
        segment_windows_df: pd.DataFrame,
        flagged_bins_df: pd.DataFrame,
        segment_summary_df: pd.DataFrame,
        stats: Dict[str, Any]
    ) -> str:
        """Generate the complete new density report."""
        
        content = []
        
        # 1. Title & Metadata
        content.append(self._generate_title_metadata(context))
        content.append("")
        content.append("---")
        content.append("")
        
        # 2. Executive Summary
        content.append(self._generate_executive_summary(stats, segment_summary_df))
        content.append("")
        content.append("---")
        content.append("")
        
        # 3. Methodology & Inputs
        content.append(self._generate_methodology_inputs(context))
        content.append("")
        content.append("---")
        content.append("")
        
        # 4. Start Times & Cohorts
        content.append(self._generate_start_times_cohorts(context))
        content.append("")
        content.append("---")
        content.append("")
        
        # 5. Course Overview
        content.append(self._generate_course_overview(segments_df, segment_windows_df, bins_df))
        content.append("")
        content.append("---")
        content.append("")
        
        # 6. Flagged Segments — Complete List
        content.append(self._generate_flagged_segments_complete(segment_summary_df))
        content.append("")
        content.append("---")
        content.append("")
        
        # 7. Flagged Bins Summary (merged into Flagged Segments)
        # content.append(self._generate_flagged_bins_summary(segment_summary_df))
        # content.append("")
        # content.append("---")
        # content.append("")
        
        # 8. Operational Heatmap (placeholder)
        content.append(self._generate_operational_heatmap_placeholder())
        content.append("")
        content.append("---")
        content.append("")
        
        # 9. Bin-Level Detail
        content.append(self._generate_bin_level_detail(flagged_bins_df))
        content.append("")
        content.append("---")
        content.append("")
        
        # 10. Segment Details
        content.append(self._generate_segment_details(segments_df, segment_windows_df, segment_summary_df))
        content.append("")
        content.append("---")
        content.append("")
        
        # 10. Mitigations
        content.append(self._generate_mitigations(segment_summary_df))
        content.append("")
        content.append("---")
        content.append("")
        
        # 11. Appendix
        content.append(self._generate_appendix())
        
        return "\n".join(content)
    
    def _generate_title_metadata(self, context: Dict[str, Any]) -> str:
        """Generate title and metadata section."""
        lines = [
            "# Fredericton Marathon — Density Report",
            f"**Schema:** {context.get('schema_version', '1.0.0')}",
            f"**Method:** segments_from_bins",
            f"**Date:** {context.get('report_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}",
            f"**Inputs:** bins.parquet, segments.parquet, segment_windows_from_bins.parquet",
            f"**App:** v{context.get('app_version', '1.0.0')}"
        ]
        return "\n".join(lines)
    
    def _generate_executive_summary(self, stats: Dict[str, Any], segment_summary_df: pd.DataFrame) -> str:
        """Generate executive summary with operational status."""
        lines = [
            "## Executive Summary"
        ]
        
        # Key metrics
        lines.extend([
            f"- **Peak Density:** {stats.get('peak_density', 0):.4f} p/m² (LOS {stats.get('worst_los', 'A')})",
            f"- **Peak Rate:** {stats.get('peak_rate_per_m_per_min', 0):.2f} p/m/min",
            f"- **Segments with Flags:** {len(segment_summary_df[segment_summary_df['flagged_bins'] > 0])} / {len(segment_summary_df)}",
            f"- **Flagged Bins:** {stats.get('flagged_bins', 0)} / {stats.get('total_bins', 0)}"
        ])
        
        # Operational Status
        worst_severity = stats.get('worst_severity', 'none')
        if worst_severity == 'critical':
            operational_status = "🔴 Action Required"
            alert_reason = "Critical density/rate conditions detected"
        elif worst_severity == 'watch':
            operational_status = "⚠️ Attention Required"
            alert_reason = "Watch conditions detected"
        else:
            operational_status = "✅ All Clear"
            alert_reason = "No operational flags"
        
        lines.extend([
            f"- **Operational Status:** {operational_status} ({alert_reason})",
            "",
            "> LOS (Level of Service) describes how comfortable runners are within a section — A means free-flowing, while E/F indicate crowding. Even when the average LOS is good (A/B), short-lived surges in runner volume or pace can temporarily push sections toward operational limits, which is why some areas are flagged."
        ])
        
        return "\n".join(lines)
    
    def _generate_methodology_inputs(self, context: Dict[str, Any]) -> str:
        """Generate methodology and inputs section."""
        lines = [
            "## Methodology & Inputs",
            f"- **Window Size:** {context.get('window_s', 30)} s; **Bin Size:** {context.get('bin_km', 0.2)} km",
            "",
            "### LOS and Rate Triggers (from Rulebook)",
            "- **LOS thresholds** define crowding levels based on density (p/m²):",
            "  - A: < 0.36 | B: 0.36–0.54 | C: 0.54–0.72 | D: 0.72–1.08 | E: 1.08–1.63 | F: > 1.63",
            "- **Rate thresholds** define throughput risk based on flow references (persons/m/min):",
            f"  - Warning: {context.get('rate_warn_threshold', 0):.1f} | Critical: {context.get('rate_critical_threshold', 0):.1f}",
            "",
            "These thresholds come from the Fredericton Marathon rulebook and align with crowd management standards for mass participation events."
        ]
        return "\n".join(lines)
    
    def _generate_start_times_cohorts(self, context: Dict[str, Any]) -> str:
        """Generate start times and cohorts section."""
        # Get runner counts from context if available
        full_count = context.get('full_runners', 368)
        tenk_count = context.get('10k_runners', 618)
        half_count = context.get('half_runners', 912)
        
        lines = [
            "## Start Times & Cohorts",
            f"- **Full Marathon** — 07:00 ({full_count:,} runners)",
            f"- **10K** — 07:20 ({tenk_count:,} runners)",
            f"- **Half Marathon** — 07:40 ({half_count:,} runners)",
            "",
            "> Bins may include runners from multiple events as waves overlap in time."
        ]
        return "\n".join(lines)
    
    def _generate_course_overview(self, segments_df: pd.DataFrame, segment_windows_df: pd.DataFrame, bins_df: pd.DataFrame) -> str:
        """Generate course overview table."""
        lines = [
            "## Course Overview",
            "",
            "| Segment | Label | Schema | Width (m) | Spatial Bins |",
            "|----------|--------|--------|-----------|--------------|"
        ]
        
        # Calculate spatial bin counts per segment (unique start_km values)
        spatial_bins = bins_df.groupby('segment_id')['start_km'].nunique().to_dict()
        
        # Sort segments by segment_id for course order
        segments_sorted = segments_df.sort_values('segment_id').copy()
        
        # Add spatial bin counts
        segments_sorted['spatial_bins'] = segments_sorted['segment_id'].map(spatial_bins).fillna(0).astype(int)
        
        for _, row in segments_sorted.iterrows():
            lines.append(
                f"| {row['segment_id']} | {row['seg_label']} | {row['segment_type']} | "
                f"{row['width_m']} | {row['spatial_bins']} |"
            )
        
        lines.append("")
        lines.append("> Note: Each spatial bin is analyzed across 80 time windows (30-second intervals), creating ~400 space-time bins per segment.")
        
        return "\n".join(lines)
    
    def _generate_flagged_segments_complete(self, segment_summary_df: pd.DataFrame) -> str:
        """Generate complete list of flagged segments (no truncation)."""
        lines = [
            "## Flagged Segments",
            "",
            "| Segment | Label | Flagged Bins | Total Bins | % | Worst Bin (km) | Time | Density (p/m²) | Rate (p/s) | LOS | Severity | Reason |",
            "|----------|--------|--------------|------------|---|----------------|-------|----------------|-------------|-----|-----------|---------|"
        ]
        
        # Filter to only flagged segments and sort by segment_id for course order
        flagged_segments = segment_summary_df[segment_summary_df['flagged_bins'] > 0].sort_values('segment_id')
        
        if len(flagged_segments) == 0:
            lines.append("| *No flagged segments* | | | | | | | | | | | |")
        else:
            for _, row in flagged_segments.iterrows():
                # Format worst bin km range
                worst_km = f"{row['worst_bin_start_km']:.1f}-{row['worst_bin_end_km']:.1f}"
                
                # Format worst bin time (HH:MM only)
                if pd.notna(row['worst_bin_t_start']):
                    t_start = row['worst_bin_t_start']
                    # Handle pandas Timestamp
                    if hasattr(t_start, 'strftime'):
                        worst_time = t_start.strftime('%H:%M')
                    # Handle string timestamps
                    elif isinstance(t_start, str):
                        # Extract HH:MM from ISO format (e.g., "2025-10-16T07:20:00Z")
                        if 'T' in t_start:
                            time_part = t_start.split('T')[1]
                            worst_time = time_part[:5]  # HH:MM
                        else:
                            worst_time = t_start[:5]
                    else:
                        worst_time = str(t_start)[:5]
                else:
                    worst_time = "N/A"
                
                # Format worst bin rate
                worst_rate = f"{row['worst_bin_rate']:.3f}" if row['worst_bin_rate'] > 0 else "N/A"
                
                lines.append(
                    f"| {row['segment_id']} | {row['seg_label']} | {row['flagged_bins']} | {row['total_bins']} | "
                    f"{row['flagged_percentage']:.1f}% | {worst_km} | {worst_time} | {row['worst_bin_density']:.4f} | {worst_rate} | "
                    f"{row['worst_bin_los']} | {row['worst_severity']} | {row['worst_reason']} |"
                )
        
        return "\n".join(lines)
    
    def _generate_flagged_bins_summary(self, segment_summary_df: pd.DataFrame) -> str:
        """Generate flagged bins summary by segment."""
        lines = [
            "## Flagged Bins Summary",
            "",
            "| Segment | Label | Flagged | Total | % | Top Reasons |",
            "|----------|--------|----------|--------|----|--------------|"
        ]
        
        for _, row in segment_summary_df.iterrows():
            if row['flagged_bins'] > 0:
                lines.append(
                    f"| {row['segment_id']} | {row['seg_label']} | {row['flagged_bins']} | "
                    f"{row['total_bins']} | {row['flagged_percentage']:.1f}% | {row['worst_reason']} |"
                )
        
        if len(segment_summary_df[segment_summary_df['flagged_bins'] > 0]) == 0:
            lines.append("| *No flagged segments* | | | | | |")
        
        return "\n".join(lines)
    
    def _generate_operational_heatmap_placeholder(self) -> str:
        """Generate operational heatmap placeholder."""
        lines = [
            "## Operational Heatmap",
            "",
            "*Operational heatmap visualization will be added in a future release via new maps capability.*",
            "",
            "This section will provide:",
            "- Visual density/rate heatmaps across course segments",
            "- Time-based animation of crowd flows",
            "- Interactive bin-level detail views"
        ]
        return "\n".join(lines)
    
    def _generate_bin_level_detail(self, flagged_bins_df: pd.DataFrame) -> str:
        """Generate bin-level detail table for diagnostic visibility."""
        lines = [
            "## Bin-Level Detail",
            "",
            "Detailed bin-by-bin breakdown for segments with operational intelligence flags:",
            ""
        ]
        
        if len(flagged_bins_df) == 0:
            lines.append("*No flagged bins to display*")
            return "\n".join(lines)
        
        # Group by segment and sort by segment_id, then by t_start
        flagged_bins_sorted = flagged_bins_df.sort_values(['segment_id', 't_start'])
        
        current_segment = None
        for _, row in flagged_bins_sorted.iterrows():
            segment_id = row['segment_id']
            seg_label = row.get('seg_label', segment_id)
            
            # Start new segment section
            if current_segment != segment_id:
                if current_segment is not None:
                    lines.append("")  # Add spacing between segments
                
                current_segment = segment_id
                lines.extend([
                    f"### {seg_label} ({segment_id})",
                    "",
                    "| Start (km) | End (km) | Start (t) | End (t) | Density (p/m²) | Rate (p/s) | LOS |",
                    "|------------|----------|-----------|---------|----------------|-------------|-----|"
                ])
            
            # Format time as HH:MM
            t_start = row['t_start']
            t_end = row['t_end']
            
            # Handle pandas Timestamp
            if hasattr(t_start, 'strftime'):
                start_time = t_start.strftime('%H:%M')
                end_time = t_end.strftime('%H:%M')
            # Handle string timestamps (ISO format)
            elif isinstance(t_start, str) and 'T' in t_start:
                start_time = t_start.split('T')[1][:5]  # HH:MM
                end_time = t_end.split('T')[1][:5] if isinstance(t_end, str) and 'T' in t_end else str(t_end)[:5]
            else:
                start_time = str(t_start)[:5]
                end_time = str(t_end)[:5]
            
            lines.append(
                f"| {row.get('start_km', 0):.1f} | {row.get('end_km', 0):.1f} | {start_time} | {end_time} | "
                f"{row['density']:.3f} | {row['rate']:.3f} | {row['los']} |"
            )
        
        return "\n".join(lines)
    
    def _generate_segment_details(self, segments_df: pd.DataFrame, segment_windows_df: pd.DataFrame, segment_summary_df: pd.DataFrame) -> str:
        """Generate segment details cards."""
        lines = [
            "## Segment Details"
        ]
        
        for _, seg_row in segments_df.iterrows():
            seg_id = seg_row['segment_id']
            seg_label = seg_row['seg_label']
            
            # Get summary data for this segment
            seg_summary = segment_summary_df[segment_summary_df['segment_id'] == seg_id]
            
            if len(seg_summary) > 0:
                summary = seg_summary.iloc[0]
                lines.extend([
                    "",
                    f"### {seg_label} ({seg_id})",
                    f"- **Type:** {seg_row['segment_type']} · **Width:** {seg_row['width_m']} m · **Bins:** {summary['total_bins']}",
                    f"- **Active:** 07:00 → 10:00",  # TODO: Calculate actual active times
                    f"- **Peaks:** Density {summary['peak_density']:.4f} p/m² (LOS {summary['peak_los']}), Rate {summary['peak_rate_per_m_per_min']:.2f} p/m/min",
                    f"- **Worst Bin:** 0.8-1.0 km at 07:20 — {summary['worst_severity']} ({summary['worst_reason']})",  # TODO: Get actual worst bin details
                    f"- **Mitigations:** {self._get_mitigations_for_segment(seg_id, summary['worst_reason'])}"
                ])
            else:
                lines.extend([
                    "",
                    f"### {seg_label} ({seg_id})",
                    f"- **Type:** {seg_row['segment_type']} · **Width:** {seg_row['width_m']} m",
                    "- **Status:** No operational flags"
                ])
        
        return "\n".join(lines)
    
    def _generate_mitigations(self, segment_summary_df: pd.DataFrame) -> str:
        """Generate consolidated mitigations list."""
        lines = [
            "## Mitigations"
        ]
        
        # Collect unique mitigation reasons
        flagged_segments = segment_summary_df[segment_summary_df['flagged_bins'] > 0]
        
        if len(flagged_segments) == 0:
            lines.append("No operational mitigations required.")
        else:
            lines.append("")
            mitigation_reasons = flagged_segments['worst_reason'].unique()
            
            for reason in mitigation_reasons:
                if reason == 'los_high':
                    lines.append("- **High Density (LOS ≥ C):** Monitor crowd density, consider flow management")
                elif reason == 'rate_high':
                    lines.append("- **High Throughput Rate:** Monitor flow rates, consider temporary holds")
                elif reason == 'both':
                    lines.append("- **High Density + High Rate:** Implement flow management and density controls")
        
        return "\n".join(lines)
    
    def _generate_appendix(self) -> str:
        """Generate appendix with definitions and thresholds."""
        lines = [
            "## Appendix",
            "",
            "### Definitions of Metrics",
            "- **Density (ρ):** Areal density in persons per square meter (p/m²)",
            "- **Rate (q):** Throughput rate in persons per second (p/s)",
            "- **Rate per meter per minute:** (rate / width_m) × 60 in persons/m/min",
            "- **LOS (Level of Service):** Crowd comfort class (A–F)",
            "- **Bin:** Space–time cell [segment_id, start_km–end_km, t_start–t_end]",
            "",
            "### LOS Thresholds",
            "| LOS | Density Range (p/m²) | Description |",
            "|-----|---------------------|-------------|",
            "| A | 0.00 - 0.36 | Free Flow |",
            "| B | 0.36 - 0.54 | Comfortable |",
            "| C | 0.54 - 0.72 | Moderate |",
            "| D | 0.72 - 1.08 | Dense |",
            "| E | 1.08 - 1.63 | Very Dense |",
            "| F | 1.63+ | Extremely Dense |",
            "",
            "### Trigger Logic & Severity",
            "- **los_high:** Density ≥ LOS C threshold",
            "- **rate_high:** Rate per m per min ≥ warning threshold",
            "- **both:** Both density and rate conditions met",
            "- **Severity:** critical > watch > none",
            "",
            "### Terminology Notes",
            "- \"Rate\" = persons/s (formerly \"Flow\")",
            "- Note: operational heatmap to be added in future release"
        ]
        
        return "\n".join(lines)
    
    def _get_mitigations_for_segment(self, segment_id: str, reason: str) -> str:
        """Get mitigation text for a specific segment and reason."""
        if reason == 'los_high':
            return "Monitor crowd density, consider flow management"
        elif reason == 'rate_high':
            return "Monitor flow rates, consider temporary holds"
        elif reason == 'both':
            return "Implement flow management and density controls"
        else:
            return "No mitigations required"
