"""
Canonical Density Report Generator

This module orchestrates the generation of operational intelligence reports
from canonical bins data. It produces:
- Executive Summary: One-page segment-level rollup with worst-case metrics
- Appendices: Detailed per-segment bin-level analysis
- Tooltips JSON: Interactive map data
- Map Snippets: PNG visualizations (if map engine available)

Issue #233: Operational Intelligence - Report Orchestration
"""

from __future__ import annotations
import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any

import yaml
import pandas as pd

from app.io_bins import load_bins, get_bins_metadata
from app.los import DEFAULT_LOS_THRESHOLDS, get_los_description, get_los_color
from app.bin_intelligence import (
    FlaggingConfig,
    apply_bin_flagging,
    get_flagged_bins,
    summarize_segment_flags,
    get_flagging_statistics
)

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to config/reporting.yml
        
    Returns:
        Configuration dictionary
    """
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        logger.info(f"Loaded configuration from {config_path}")
        return config
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        raise


def generate_executive_summary(
    segment_summary: pd.DataFrame,
    config: Dict[str, Any],
    stats: Dict[str, Any],
    output_path: str
) -> bool:
    """
    Generate executive summary markdown report.
    
    Args:
        segment_summary: DataFrame with segment-level rollup
        config: Configuration dictionary
        stats: Flagging statistics
        output_path: Path to output file
        
    Returns:
        True on success, False on error
    """
    try:
        with open(output_path, 'w') as f:
            # Header with metadata
            f.write("# Density Executive Summary\n\n")
            f.write(f"**Generated:** {datetime.utcnow().isoformat()}Z\n\n")
            f.write(f"**Schema Version:** {config.get('schema_version', '1.1.0')}\n\n")
            f.write(f"**Density Method:** {config.get('density_method', 'segments_from_bins')}\n\n")
            f.write(f"**Methodology:** Bottom-up aggregation from canonical bins\n\n")
            
            f.write("---\n\n")
            
            # Key Metrics
            f.write("## Key Metrics\n\n")
            f.write("| Metric | Value |\n")
            f.write("|--------|-------|\n")
            f.write(f"| Total Bins | {stats['total_bins']} |\n")
            f.write(f"| Flagged Bins | {stats['flagged_bins']} ({stats['flagged_percentage']:.1f}%) |\n")
            f.write(f"| Worst Severity | {stats['worst_severity']} |\n")
            f.write(f"| Worst LOS | {stats['worst_los']} |\n")
            f.write(f"| Peak Density Range | {stats['peak_density_range']['min']:.2f} - {stats['peak_density_range']['max']:.2f} people/m² |\n")
            
            f.write("\n")
            
            # Severity Distribution
            f.write("## Severity Distribution\n\n")
            f.write("| Severity | Count |\n")
            f.write("|----------|-------|\n")
            for severity in ['CRITICAL', 'CAUTION', 'WATCH', 'NONE']:
                count = stats['severity_distribution'].get(severity, 0)
                f.write(f"| {severity} | {count} |\n")
            
            f.write("\n")
            
            # LOS Distribution
            f.write("## LOS Distribution\n\n")
            f.write("| LOS | Description | Count |\n")
            f.write("|-----|-------------|-------|\n")
            for los_level in ['A', 'B', 'C', 'D', 'E', 'F']:
                count = stats['los_distribution'].get(los_level, 0)
                desc = get_los_description(los_level)
                f.write(f"| {los_level} | {desc} | {count} |\n")
            
            f.write("\n")
            
            # Flagged Segments Table
            if len(segment_summary) > 0:
                f.write("## Flagged Segments\n\n")
                f.write("Segments with operational intelligence flags (worst bin per segment):\n\n")
                f.write("| Segment | Range (km) | LOS | Density | Flagged Bins | Severity | Reason |\n")
                f.write("|---------|------------|-----|---------|--------------|----------|--------|\n")
                
                for _, row in segment_summary.iterrows():
                    seg_label = row.get('seg_label', row['segment_id'])
                    range_str = f"{row['worst_bin_start_km']:.2f} - {row['worst_bin_end_km']:.2f}"
                    los = row['worst_los']
                    density = f"{row['peak_density']:.2f}"
                    count = row['flagged_bin_count']
                    severity = row['severity']
                    reason = row['flag_reason']
                    
                    f.write(f"| {seg_label} | {range_str} | {los} | {density} | {count} | {severity} | {reason} |\n")
                
                f.write("\n")
            else:
                f.write("## Flagged Segments\n\n")
                f.write("✅ **No segments flagged** - All bins operating within acceptable parameters.\n\n")
            
            # Legend
            f.write("## Legend\n\n")
            f.write("### Severity Levels\n\n")
            f.write("- **CRITICAL**: Both LOS >= C AND top 5% utilization\n")
            f.write("- **CAUTION**: LOS >= C only\n")
            f.write("- **WATCH**: Top 5% utilization only\n")
            f.write("- **NONE**: No thresholds exceeded\n\n")
            
            f.write("### LOS (Level of Service)\n\n")
            f.write("Based on Fruin's pedestrian level of service standards:\n\n")
            for los_level in ['A', 'B', 'C', 'D', 'E', 'F']:
                desc = get_los_description(los_level)
                f.write(f"- **{los_level}**: {desc}\n")
            
            f.write("\n")
            
            # Action Items (if any flags exist)
            if stats['flagged_bins'] > 0:
                f.write("## Recommended Actions\n\n")
                
                critical_count = stats['severity_distribution'].get('CRITICAL', 0)
                caution_count = stats['severity_distribution'].get('CAUTION', 0)
                watch_count = stats['severity_distribution'].get('WATCH', 0)
                
                if critical_count > 0:
                    f.write(f"### Critical ({critical_count} bins)\n\n")
                    f.write("- **Immediate attention required**: Both high density and high utilization\n")
                    f.write("- Consider operational interventions (staging, flow control, additional resources)\n")
                    f.write("- Review detailed appendices for specific bin-level analysis\n\n")
                
                if caution_count > 0:
                    f.write(f"### Caution ({caution_count} bins)\n\n")
                    f.write("- **Monitor closely**: High density levels detected\n")
                    f.write("- Prepare contingency plans for these segments\n")
                    f.write("- Consider preventive measures if conditions worsen\n\n")
                
                if watch_count > 0:
                    f.write(f"### Watch ({watch_count} bins)\n\n")
                    f.write("- **Elevated utilization**: In top 5% globally\n")
                    f.write("- Continue monitoring for density trends\n")
                    f.write("- Review historical patterns in appendices\n\n")
            
            # Footer
            f.write("---\n\n")
            f.write("**Note**: This report is generated from canonical bins data using bottom-up aggregation. ")
            f.write("See appendices for detailed per-segment bin-level analysis.\n")
        
        logger.info(f"Executive summary written to {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error generating executive summary: {e}")
        return False


def generate_appendices(
    flagged_bins: pd.DataFrame,
    config: Dict[str, Any],
    output_dir: str
) -> bool:
    """
    Generate detailed appendix files for each flagged segment.
    
    Args:
        flagged_bins: DataFrame with flagged bins
        config: Configuration dictionary
        output_dir: Directory for appendix files
        
    Returns:
        True on success, False on error
    """
    try:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        if len(flagged_bins) == 0:
            logger.info("No flagged bins - skipping appendix generation")
            return True
        
        # Group by segment
        for segment_id in flagged_bins['segment_id'].unique():
            seg_bins = flagged_bins[flagged_bins['segment_id'] == segment_id]
            seg_label = seg_bins.iloc[0].get('seg_label', segment_id)
            
            appendix_path = output_path / f"{segment_id}.md"
            
            with open(appendix_path, 'w') as f:
                f.write(f"# Appendix: {seg_label} ({segment_id})\n\n")
                f.write(f"**Generated:** {datetime.utcnow().isoformat()}Z\n\n")
                f.write(f"**Flagged Bins:** {len(seg_bins)}\n\n")
                
                f.write("## Bin-Level Detail\n\n")
                f.write("| Start (km) | End (km) | Length (m) | Peak Density | LOS | Severity | Reason |\n")
                f.write("|------------|----------|------------|--------------|-----|----------|--------|\n")
                
                # Sort by severity, then density
                seg_bins_sorted = seg_bins.sort_values(
                    by=['severity_rank', 'density_peak'],
                    ascending=[False, False]
                )
                
                for _, bin_row in seg_bins_sorted.iterrows():
                    start_km = f"{bin_row['start_km']:.3f}"
                    end_km = f"{bin_row['end_km']:.3f}"
                    length_m = f"{bin_row.get('bin_len_m', 0):.1f}"
                    density = f"{bin_row['density_peak']:.2f}"
                    los = bin_row['los']
                    severity = bin_row['severity']
                    reason = bin_row['flag_reason']
                    
                    f.write(f"| {start_km} | {end_km} | {length_m} | {density} | {los} | {severity} | {reason} |\n")
                
                f.write("\n")
                
                # Time window analysis if available
                if 't_start' in seg_bins.columns and 't_end' in seg_bins.columns:
                    f.write("## Time Window Analysis\n\n")
                    f.write("Distribution of flagged bins by time:\n\n")
                    # This is a placeholder - could be enhanced with actual time-based grouping
                    f.write("*Time-based analysis available in future releases*\n\n")
                
                # Summary statistics for this segment
                f.write("## Segment Summary\n\n")
                f.write("| Metric | Value |\n")
                f.write("|--------|-------|\n")
                f.write(f"| Total Flagged Bins | {len(seg_bins)} |\n")
                f.write(f"| Worst Severity | {seg_bins.iloc[0]['severity']} |\n")
                f.write(f"| Worst LOS | {seg_bins.iloc[0]['los']} |\n")
                f.write(f"| Peak Density | {seg_bins['density_peak'].max():.2f} people/m² |\n")
                f.write(f"| Mean Density | {seg_bins['density_peak'].mean():.2f} people/m² |\n")
            
            logger.debug(f"Created appendix for segment {segment_id}")
        
        logger.info(f"Generated {len(flagged_bins['segment_id'].unique())} appendix files in {output_dir}")
        return True
        
    except Exception as e:
        logger.error(f"Error generating appendices: {e}")
        return False


def generate_tooltips_json(
    flagged_bins: pd.DataFrame,
    config: Dict[str, Any],
    output_path: str
) -> bool:
    """
    Generate tooltips JSON for interactive map visualization.
    
    Args:
        flagged_bins: DataFrame with flagged bins
        config: Configuration dictionary
        output_path: Path to output JSON file
        
    Returns:
        True on success, False on error
    """
    try:
        tooltips = []
        
        for _, row in flagged_bins.iterrows():
            tooltip = {
                'segment_id': row['segment_id'],
                'seg_label': row.get('seg_label', row['segment_id']),
                'start_km': float(row['start_km']),
                'end_km': float(row['end_km']),
                'density_peak': float(row['density_peak']),
                'los': row['los'],
                'los_description': get_los_description(row['los']),
                'los_color': get_los_color(row['los']),
                'severity': row['severity'],
                'flag_reason': row['flag_reason']
            }
            
            # Add time window if available
            if 't_start' in row and pd.notna(row['t_start']):
                tooltip['t_start'] = row['t_start'].isoformat() if hasattr(row['t_start'], 'isoformat') else str(row['t_start'])
            if 't_end' in row and pd.notna(row['t_end']):
                tooltip['t_end'] = row['t_end'].isoformat() if hasattr(row['t_end'], 'isoformat') else str(row['t_end'])
            
            tooltips.append(tooltip)
        
        # Write JSON
        with open(output_path, 'w') as f:
            json.dump({
                'generated': datetime.utcnow().isoformat() + 'Z',
                'schema_version': config.get('schema_version', '1.1.0'),
                'density_method': config.get('density_method', 'segments_from_bins'),
                'tooltips': tooltips
            }, f, indent=2)
        
        logger.info(f"Generated tooltips JSON with {len(tooltips)} entries: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error generating tooltips JSON: {e}")
        return False


def generate_map_snippets(
    segment_summary: pd.DataFrame,
    config: Dict[str, Any],
    output_dir: str
) -> bool:
    """
    Generate map snippet PNGs for flagged segments.
    
    Args:
        segment_summary: DataFrame with segment-level rollup
        config: Configuration dictionary
        output_dir: Directory for map snippets
        
    Returns:
        True on success, False on error (non-blocking)
    """
    try:
        from app.map_data_generator import export_snippet
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        snippet_config = config.get('reporting', {})
        width_px = snippet_config.get('snippet_width_px', 1200)
        padding_m = snippet_config.get('zoom_padding_m', 200)
        
        success_count = 0
        for _, row in segment_summary.iterrows():
            segment_id = row['segment_id']
            start_m = row['worst_bin_start_km'] * 1000
            end_m = row['worst_bin_end_km'] * 1000
            los = row['worst_los']
            utilization_pct = (row['peak_density'] / 1.0) * 100  # Normalize to percentage
            
            outfile = output_path / f"{segment_id}_{int(start_m)}-{int(end_m)}.png"
            
            if export_snippet(segment_id, start_m, end_m, los, utilization_pct,
                            str(outfile), width_px=width_px, padding_m=padding_m):
                success_count += 1
                logger.debug(f"Generated snippet for {segment_id}")
        
        if success_count > 0:
            logger.info(f"Generated {success_count} map snippets in {output_dir}")
            return True
        else:
            logger.warning("No map snippets generated (map engine may be unavailable)")
            return False
            
    except ImportError:
        logger.warning("Map export function not available - skipping snippet generation")
        return False
    except Exception as e:
        logger.warning(f"Map snippet generation failed (non-blocking): {e}")
        return False


def main():
    """Main entry point for canonical density report generation."""
    parser = argparse.ArgumentParser(
        description='Generate operational intelligence reports from canonical bins',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--config', default='config/reporting.yml',
                       help='Path to configuration file')
    parser.add_argument('--density-mode', choices=['peak', 'mean', 'sustained'],
                       help='Density analysis mode (overrides config)')
    parser.add_argument('--reports-dir', help='Reports directory (overrides config)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("="*60)
    logger.info("CANONICAL DENSITY REPORT GENERATOR")
    logger.info("="*60)
    
    try:
        # Load configuration
        config = load_config(args.config)
        
        # Override density mode if specified
        if args.density_mode:
            config['reporting']['density_mode'] = args.density_mode
            logger.info(f"Density mode overridden to: {args.density_mode}")
        
        # Override reports directory if specified
        if args.reports_dir:
            config['outputs']['reports_dir'] = args.reports_dir
        
        # Load canonical bins
        logger.info("Loading canonical bins...")
        bins_df = load_bins(reports_dir=config['outputs']['reports_dir'])
        
        if bins_df is None:
            logger.error("Failed to load canonical bins")
            return 1
        
        logger.info(f"Loaded {len(bins_df)} canonical bins")
        
        # Create flagging configuration
        flagging_cfg = FlaggingConfig(
            min_los_flag=config['flagging']['min_los_flag'],
            utilization_pctile=config['flagging']['utilization_pctile'],
            require_min_bin_len_m=config['flagging']['require_min_bin_len_m'],
            density_field='density_peak'  # Use peak density (conservative)
        )
        
        # Apply bin flagging
        logger.info("Applying operational intelligence flagging...")
        bins_flagged = apply_bin_flagging(
            bins_df,
            config=flagging_cfg,
            los_thresholds=config.get('los', None)
        )
        
        # Get flagging statistics
        stats = get_flagging_statistics(bins_flagged)
        logger.info(f"Flagging complete: {stats['flagged_bins']}/{stats['total_bins']} bins flagged")
        
        # Summarize to segment level
        logger.info("Rolling up to segment level...")
        segment_summary = summarize_segment_flags(bins_flagged)
        
        # Get flagged bins for detailed outputs
        flagged_bins = get_flagged_bins(bins_flagged)
        
        # Generate outputs
        reports_dir = Path(config['outputs']['reports_dir'])
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Executive Summary
        logger.info("Generating executive summary...")
        summary_path = reports_dir / "density-executive-summary.md"
        if not generate_executive_summary(segment_summary, config, stats, str(summary_path)):
            logger.error("Failed to generate executive summary")
            return 1
        
        # Appendices
        logger.info("Generating appendices...")
        appendix_dir = config['outputs']['appendix_dir']
        if not generate_appendices(flagged_bins, config, appendix_dir):
            logger.warning("Appendix generation had errors")
        
        # Tooltips JSON
        logger.info("Generating tooltips JSON...")
        tooltips_path = config['outputs']['tooltips_json']
        if not generate_tooltips_json(flagged_bins, config, tooltips_path):
            logger.warning("Tooltips JSON generation had errors")
        
        # Map Snippets (non-blocking)
        logger.info("Attempting to generate map snippets...")
        snippets_dir = config['outputs']['snippets_dir']
        generate_map_snippets(segment_summary, config, snippets_dir)
        
        logger.info("="*60)
        logger.info("REPORT GENERATION COMPLETE")
        logger.info("="*60)
        logger.info(f"Executive Summary: {summary_path}")
        logger.info(f"Appendices: {appendix_dir}")
        logger.info(f"Tooltips: {tooltips_path}")
        logger.info(f"Snippets: {snippets_dir}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())

