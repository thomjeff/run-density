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
        content.append(self._generate_course_overview(segments_df, segment_windows_df))
        content.append("")
        content.append("---")
        content.append("")
        
        # 6. Flagged Segments — Complete List
        content.append(self._generate_flagged_segments_complete(segment_summary_df))
        content.append("")
        content.append("---")
        content.append("")
        
        # 7. Flagged Bins Summary
        content.append(self._generate_flagged_bins_summary(segment_summary_df))
        content.append("")
        content.append("---")
        content.append("")
        
        # 8. Operational Heatmap (placeholder)
        content.append(self._generate_operational_heatmap_placeholder())
        content.append("")
        content.append("---")
        content.append("")
        
        # 9. Segment Details
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
            "> Note: LOS = comfort index; operational flags reflect throughput surges even under LOS A/B."
        ])
        
        return "\n".join(lines)
    
    def _generate_methodology_inputs(self, context: Dict[str, Any]) -> str:
        """Generate methodology and inputs section."""
        lines = [
            "## Methodology & Inputs",
            f"- **Window Size:** {context.get('window_s', 30)} s; **Bin Size:** {context.get('bin_km', 0.2)} km",
            "- LOS & Rate triggers per `density_rulebook.yml`.",
            "- Data read from Parquet sources only."
        ]
        return "\n".join(lines)
    
    def _generate_start_times_cohorts(self, context: Dict[str, Any]) -> str:
        """Generate start times and cohorts section."""
        lines = [
            "## Start Times & Cohorts",
            "Full: 07:00 | 10K: 07:20 | Half: 07:40",
            "Bins may contain multiple event cohorts simultaneously."
        ]
        return "\n".join(lines)
    
    def _generate_course_overview(self, segments_df: pd.DataFrame, segment_windows_df: pd.DataFrame) -> str:
        """Generate course overview table."""
        lines = [
            "## Course Overview",
            "",
            "| Segment | Label | Type | Width (m) | Bins | Windows Active |",
            "|----------|--------|-------|-----------|-------|----------------|"
        ]
        
        # Merge segments with window counts
        if len(segment_windows_df) > 0:
            window_counts = segment_windows_df.groupby('segment_id').size().reset_index(name='windows_active')
            segments_with_windows = segments_df.merge(window_counts, on='segment_id', how='left')
            segments_with_windows['windows_active'] = segments_with_windows['windows_active'].fillna(0)
        else:
            segments_with_windows = segments_df.copy()
            segments_with_windows['windows_active'] = 0
        
        # Add bin counts (assuming 5 bins per segment for now - this should be calculated)
        segments_with_windows['bins'] = 5  # TODO: Calculate actual bin counts
        
        for _, row in segments_with_windows.iterrows():
            lines.append(
                f"| {row['segment_id']} | {row['seg_label']} | {row['segment_type']} | "
                f"{row['width_m']} | {row['bins']} | {row['windows_active']} |"
            )
        
        return "\n".join(lines)
    
    def _generate_flagged_segments_complete(self, segment_summary_df: pd.DataFrame) -> str:
        """Generate complete list of flagged segments (no truncation)."""
        lines = [
            "## Flagged Segments — Complete List",
            "",
            "| Segment | Label | Worst Bin (km) | Time | Density (p/m²) | Rate (p/s) | Util% | LOS | Severity | Reason |",
            "|----------|--------|----------------|-------|----------------|-------------|--------|------|-----------|---------|"
        ]
        
        # Filter to only flagged segments
        flagged_segments = segment_summary_df[segment_summary_df['flagged_bins'] > 0]
        
        if len(flagged_segments) == 0:
            lines.append("| *No flagged segments* | | | | | | | | | |")
        else:
            for _, row in flagged_segments.iterrows():
                # TODO: Get actual worst bin details (km range, time, rate, util%)
                lines.append(
                    f"| {row['segment_id']} | {row['seg_label']} | 0.8-1.0 | 07:20 | "
                    f"{row['peak_density']:.4f} | N/A | N/A | {row['peak_los']} | "
                    f"{row['worst_severity']} | {row['worst_reason']} |"
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
