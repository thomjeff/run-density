from __future__ import annotations

"""
New Density Template Engine for Issue #246

DEPRECATED: This module is marked as deprecated and scheduled for replacement in Phase 2.
Please use `density_template_engine.py` as the primary entry point.

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

import warnings
warnings.warn(
    "This module is marked as deprecated and scheduled for replacement in Phase 2. "
    "Please use `density_template_engine.py` as the primary entry point.",
    DeprecationWarning
)
import os
import math
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
    
    @staticmethod
    def _round_half_up(n: float, decimals: int = 1) -> float:
        """Round half up (away from zero) for consistent percentage formatting.
        
        Python's default round() uses round-half-to-even which causes inconsistency.
        This method ensures consistent rounding for percentage display.
        
        Args:
            n: Number to round
            decimals: Number of decimal places (default 1)
            
        Returns:
            Rounded number using round-half-up behavior
        """
        multiplier = 10 ** decimals
        return math.floor(n * multiplier + 0.5) / multiplier
    
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
        import logging
        logger = logging.getLogger(__name__)
        
        content = []
        
        try:
            # 1. Title & Metadata
            logger.info("Template: Generating title & metadata...")
            content.append(self._generate_title_metadata(context))
            content.append("")
            content.append("---")
            content.append("")
            
            # 2. Executive Summary
            logger.info("Template: Generating executive summary...")
            # Pass context to _generate_executive_summary for RES data (Issue #573)
            stats_with_context = {**stats, '_context': context}
            content.append(self._generate_executive_summary(stats_with_context, segment_summary_df))
            content.append("")
            content.append("---")
            content.append("")
            
            # 3. Methodology & Inputs
            logger.info("Template: Generating methodology & inputs...")
            content.append(self._generate_methodology_inputs(context))
            content.append("")
            content.append("---")
            content.append("")
            
            # 4. Start Times & Cohorts
            logger.info("Template: Generating start times & cohorts...")
            content.append(self._generate_start_times_cohorts(context))
            content.append("")
            content.append("---")
            content.append("")
            
            # 5. Course Overview
            logger.info("Template: Generating course overview...")
            content.append(self._generate_course_overview(segments_df, segment_windows_df, bins_df))
            content.append("")
            content.append("---")
            content.append("")
            
            # 6. Flagged Segments
            logger.info("Template: Generating flagged segments...")
            content.append(self._generate_flagged_segments_complete(segment_summary_df, segments_df))
            content.append("")
            content.append("---")
            content.append("")
            
            # 7. Flagged Bins Summary (merged into Flagged Segments)
            # content.append(self._generate_flagged_bins_summary(segment_summary_df))
            # content.append("")
            # content.append("---")
            # content.append("")
            
            # 8. Operational Heatmap (placeholder)
            logger.info("Template: Generating operational heatmap placeholder...")
            content.append(self._generate_operational_heatmap_placeholder())
            content.append("")
            content.append("---")
            content.append("")
            
            # 9. Bin-Level Detail
            logger.info("Template: Generating bin-level detail...")
            content.append(self._generate_bin_level_detail(flagged_bins_df))
            content.append("")
            content.append("---")
            content.append("")
            
            # 10. Segment Details
            logger.info("Template: Generating segment details...")
            content.append(self._generate_segment_details(segments_df, segment_windows_df, segment_summary_df))
            content.append("")
            content.append("---")
            content.append("")
            
            # 10. Mitigations
            logger.info("Template: Generating mitigations...")
            content.append(self._generate_mitigations(segment_summary_df))
            content.append("")
            content.append("---")
            content.append("")
            
            # 11. Appendix
            logger.info("Template: Generating appendix...")
            content.append(self._generate_appendix())
            
            logger.info("Template: Report generation complete, joining content...")
            return "\n".join(content)
        except Exception as e:
            logger.error(f"Template: Error generating report: {e}", exc_info=True)
            raise
    
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
        """Generate executive summary with operational status and RES scores (Issue #573)."""
        lines = [
            "## Executive Summary"
        ]
        
        # Key metrics
        # Convert peak_rate_per_m_per_min to p/s for display
        peak_rate_per_m_per_min = stats.get('peak_rate_per_m_per_min', 0)
        peak_rate_ps = peak_rate_per_m_per_min / 60.0  # Convert to persons/second
        
        lines.extend([
            f"- **Peak Density:** {stats.get('peak_density', 0):.4f} p/m² (LOS {stats.get('worst_los', 'A')})",
            f"- **Peak Rate:** {peak_rate_ps:.2f} p/s",
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
            f"- **Operational Status:** {operational_status} ({alert_reason})"
        ])
        
        # Issue #573: Add Runner Experience Scores (RES) section if available
        context = stats.get('_context', {})  # Get context from stats if passed
        event_groups_res = context.get('event_groups_res') if isinstance(context, dict) else None
        
        if event_groups_res:
            lines.append("")
            lines.append("- **Runner Experience Scores (RES):**")
            # Sort groups by name for consistent ordering
            for group_id in sorted(event_groups_res.keys()):
                group_data = event_groups_res[group_id]
                res_score = group_data.get('res', 0.0)
                lines.append(f"  - {group_id}: {res_score:.2f}")
            lines.append("")
            lines.append("> RES (Runner Experience Score) is a composite score (0.0-5.0) representing overall race experience, combining density and flow metrics. Higher scores indicate better runner experience.")
        else:
            lines.append("")
        
        lines.append("> LOS (Level of Service) describes how comfortable runners are within a section — A means free-flowing, while E/F indicate crowding. Even when overall LOS is good, short-lived surges in runner flow can stress aid stations or intersections, requiring active flow management.")
        
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
        lines = ["## Start Times & Cohorts"]
        
        # Use events from context if provided (v2 dynamic events)
        events = context.get('events')
        if events:
            # Sort events by start_time
            sorted_events = sorted(events.items(), key=lambda x: x[1].get('start_time', 0))
            
            # Event name mapping for display
            event_display_names = {
                'full': 'Full Marathon',
                'half': 'Half Marathon',
                '10k': '10K',
                'elite': 'Elite 5K',
                'open': 'Open 5K'
            }
            
            for event_name, event_info in sorted_events:
                display_name = event_display_names.get(event_name, event_name.capitalize())
                start_time_str = event_info.get('start_time_formatted', 'N/A')
                runner_count = event_info.get('runner_count', 0)
                lines.append(f"- **{display_name}** — {start_time_str} ({runner_count:,} runners)")
        else:
            # Issue #512: No fallback to hardcoded values - events must be provided
            raise ValueError(
                "events parameter is required in context. Start times must come from API request, "
                "not from hardcoded constants. (Issue #512)"
            )
        
        lines.extend([
            "",
            "> Bins may include runners from multiple events as waves overlap in time."
        ])
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
            segment_type = row.get('segment_type', 'N/A')
            lines.append(
                f"| {row['segment_id']} | {row['seg_label']} | {segment_type} | "
                f"{row['width_m']} | {row['spatial_bins']} |"
            )
        
        lines.append("")
        lines.append("> Note: Each spatial bin is analyzed across 80 time windows (30-second intervals). Total space-time bins per segment = spatial bins × 80 (e.g., A1: 5 × 80 = 400; I1: 121 × 80 = 9,680).")
        
        return "\n".join(lines)
    
    def _generate_flagged_segments_complete(self, segment_summary_df: pd.DataFrame, segments_df: pd.DataFrame) -> str:
        """Generate complete list of flagged segments (no truncation)."""
        lines = [
            "## Flagged Segments",
            "",
            "| Segment | Label | Flagged Bins | Total Bins | % | Worst Bin (km) | Time | Density (p/m²) | Rate (p/s) | Util% | LOS | Severity | Reason |",
            "|----------|--------|--------------|------------|---|----------------|-------|----------------|-------------|-------|-----|-----------|---------|"
        ]
        
        # Merge with segments to get segment_type and width_m for Util% calculation and peak_rate conversion
        # segment_type is optional - use schema_key from bins if available
        segment_cols = ['segment_id']
        if 'segment_type' in segments_df.columns:
            segment_cols.append('segment_type')
        if 'width_m' in segments_df.columns:
            segment_cols.append('width_m')
        flagged_with_schema = segment_summary_df[segment_summary_df['flagged_bins'] > 0].merge(
            segments_df[segment_cols], on='segment_id', how='left'
        ).sort_values('segment_id')
        
        # If segment_type not in segments, try to get from schema_key if available
        if 'segment_type' not in flagged_with_schema.columns and 'schema_key' in flagged_with_schema.columns:
            # Map schema_key to segment_type (simplified mapping)
            schema_to_type = {
                'start_corral': 'start_corral',
                'on_course_narrow': 'on_course_narrow',
                'on_course_open': 'on_course_open'
            }
            flagged_with_schema['segment_type'] = flagged_with_schema['schema_key'].map(schema_to_type).fillna('on_course_open')
        
        if len(flagged_with_schema) == 0:
            lines.append("| *No flagged segments* | | | | | | | | | | | | |")
        else:
            for _, row in flagged_with_schema.iterrows():
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
                
                # Calculate Util% based on segment schema
                # Issue #548 Bug 4: Load flow_ref.critical from rulebook dynamically
                from app.rulebook import get_thresholds, classify_los
                segment_type = row.get('segment_type', 'on_course_open')
                thresholds = get_thresholds(segment_type)
                flow_ref_critical = thresholds.flow_ref.critical if thresholds.flow_ref else None
                
                util_display = "N/A"
                if flow_ref_critical and row['peak_rate_per_m_per_min'] > 0:
                    util_display = f"{(row['peak_rate_per_m_per_min'] / flow_ref_critical * 100):.0f}%"
                
                # Bug fix: Use peak_rate (converted from peak_rate_per_m_per_min) instead of worst_bin_rate
                # to match the UI's peak_rate display. The UI shows peak_rate for the segment, not the worst bin rate.
                # Conversion: peak_rate (p/s) = peak_rate_per_m_per_min (p/m/min) * width_m (m) / 60
                width_m = row.get('width_m', 0.0)
                if width_m and width_m > 0 and row['peak_rate_per_m_per_min'] > 0:
                    peak_rate_ps = row['peak_rate_per_m_per_min'] * width_m / 60.0
                    peak_rate_display = f"{peak_rate_ps:.3f}"
                else:
                    peak_rate_display = "N/A"
                
                # Bug fix: Recalculate LOS from worst_bin_density to ensure it matches the density shown
                # The worst_bin_los field is the LOS of the worst bin (by severity), which may not match
                # the density value shown. Recalculate LOS from the density to ensure consistency.
                worst_bin_density = row['worst_bin_density']
                los_from_density = classify_los(worst_bin_density, thresholds.los)
                
                # Bug fix: Use consistent round-half-up for percentage formatting
                flagged_pct = self._round_half_up(row['flagged_percentage'], 1)
                
                lines.append(
                    f"| {row['segment_id']} | {row['seg_label']} | {row['flagged_bins']} | {row['total_bins']} | "
                    f"{flagged_pct:.1f}% | {worst_km} | {worst_time} | {worst_bin_density:.4f} | {peak_rate_display} | {util_display} | "
                    f"{los_from_density} | {row['worst_severity']} | {row['worst_reason']} |"
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
        
        # Bug fix: Use consistent round-half-up for percentage formatting (same as flagged segments table)
        for _, row in segment_summary_df.iterrows():
            if row['flagged_bins'] > 0:
                flagged_pct = self._round_half_up(row['flagged_percentage'], 1)
                lines.append(
                    f"| {row['segment_id']} | {row['seg_label']} | {row['flagged_bins']} | "
                    f"{row['total_bins']} | {flagged_pct:.1f}% | {row['worst_reason']} |"
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
        
        # Calculate active windows for each segment from segment_windows_df
        # Bug fix: Calculate actual active windows instead of hardcoded values
        active_windows = {}
        if len(segment_windows_df) > 0 and 'segment_id' in segment_windows_df.columns:
            if 't_start' in segment_windows_df.columns and 't_end' in segment_windows_df.columns:
                try:
                    # Work with a copy to avoid modifying the original
                    windows_copy = segment_windows_df.copy()
                    
                    # Convert to datetime if not already datetime type
                    if not pd.api.types.is_datetime64_any_dtype(windows_copy['t_start']):
                        windows_copy['t_start'] = pd.to_datetime(windows_copy['t_start'], utc=True, errors='coerce')
                    if not pd.api.types.is_datetime64_any_dtype(windows_copy['t_end']):
                        windows_copy['t_end'] = pd.to_datetime(windows_copy['t_end'], utc=True, errors='coerce')
                    
                    # Group by segment_id and find min t_start and max t_end
                    segment_groups = windows_copy.groupby('segment_id')
                    for seg_id, group in segment_groups:
                        min_start = group['t_start'].min()
                        max_end = group['t_end'].max()
                        if pd.notna(min_start) and pd.notna(max_end):
                            # Format as HH:MM → HH:MM
                            start_str = min_start.strftime('%H:%M') if hasattr(min_start, 'strftime') else str(min_start)[:5]
                            end_str = max_end.strftime('%H:%M') if hasattr(max_end, 'strftime') else str(max_end)[:5]
                            active_windows[seg_id] = f"{start_str} → {end_str}"
                except Exception as e:
                    # If calculation fails, active_windows will remain empty and fallback to "N/A"
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Could not calculate active windows from segment_windows_df: {e}")
        
        for _, seg_row in segments_df.iterrows():
            seg_id = seg_row['segment_id']
            seg_label = seg_row['seg_label']
            
            # Get summary data for this segment
            seg_summary = segment_summary_df[segment_summary_df['segment_id'] == seg_id]
            
            if len(seg_summary) > 0:
                summary = seg_summary.iloc[0]
                
                # Convert rate from p/m/min to p/s
                peak_rate_ps = summary['peak_rate_per_m_per_min'] / 60.0
                
                # Calculate Util% if we have rate thresholds for this schema
                # Issue #548 Bug 4: Load flow_ref.critical from rulebook dynamically
                from app.rulebook import get_thresholds
                segment_type = seg_row.get('segment_type', 'on_course_open')
                thresholds = get_thresholds(segment_type)
                flow_ref_critical = thresholds.flow_ref.critical if thresholds.flow_ref else None
                
                util_pct = "N/A"
                if flow_ref_critical and summary['peak_rate_per_m_per_min'] > 0:
                    util_pct = f"{(summary['peak_rate_per_m_per_min'] / flow_ref_critical * 100):.0f}%"
                
                # Format worst bin details
                worst_km = f"{summary['worst_bin_start_km']:.1f}-{summary['worst_bin_end_km']:.1f}"
                worst_time = summary['worst_bin_t_start'].strftime('%H:%M') if hasattr(summary['worst_bin_t_start'], 'strftime') else str(summary['worst_bin_t_start']).split('T')[1][:5] if 'T' in str(summary['worst_bin_t_start']) else "N/A"
                
                # Build peaks line with Util%
                peaks_line = f"- **Peaks:** Density {summary['peak_density']:.4f} p/m² (LOS {summary['peak_los']}), Rate {peak_rate_ps:.2f} p/s"
                if util_pct != "N/A":
                    peaks_line += f", Util {util_pct}"
                
                segment_type = seg_row.get('segment_type', 'on_course_open')
                # Get active window for this segment, or use fallback
                active_window = active_windows.get(seg_id, "N/A")
                lines.extend([
                    "",
                    f"### {seg_label} ({seg_id})",
                    f"- **Schema:** {segment_type} · **Width:** {seg_row['width_m']} m · **Bins:** {summary['total_bins']}",
                    f"- **Active:** {active_window}",
                    peaks_line,
                    f"- **Worst Bin:** {worst_km} km at {worst_time} — {summary['worst_severity']} ({summary['worst_reason']})",
                    f"- **Mitigations:** {self._get_mitigations_for_segment(seg_id, summary['worst_reason'], segment_type)}"
                ])
            else:
                segment_type = seg_row.get('segment_type', 'on_course_open')
                lines.extend([
                    "",
                    f"### {seg_label} ({seg_id})",
                    f"- **Schema:** {segment_type} · **Width:** {seg_row['width_m']} m",
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
            "- **Utilization (%):** Current flow rate / reference flow rate (critical). Shows \"N/A\" when \`flow_ref.critical\` is not defined for the segment schema in the rulebook.",
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
    
    def _get_mitigations_for_segment(self, segment_id: str, reason: str, segment_type: str = None) -> str:
        """Get mitigation text for a specific segment based on schema and reason."""
        if reason == 'none':
            return "No mitigations required"
        
        # Schema-specific base mitigations
        schema_mitigations = {
            'start_corral': "Expand chute width and manage wave timing",
            'on_course_narrow': "Deploy lateral barriers and regulate inflow",
            'on_course_open': "Monitor via visual flow sensors"
        }
        
        base_mitigation = schema_mitigations.get(segment_type, "Monitor flow management")
        
        # Add reason-specific actions
        if reason == 'los_high':
            return f"{base_mitigation}; monitor crowd density"
        elif reason == 'rate_high':
            return f"{base_mitigation}; consider temporary holds"
        elif reason == 'both':
            return f"{base_mitigation}; implement density controls and flow metering"
        else:
            return base_mitigation
