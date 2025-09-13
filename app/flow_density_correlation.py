"""
Flow↔Density Correlation Analysis Module

This module provides correlation analysis between temporal flow patterns and density peaks.
It identifies relationships between flow interactions (overtaking, merging, counterflow) 
and density concentrations to provide insights for race management.

Author: AI Assistant
Version: 1.6.0
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import logging
from datetime import datetime
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def analyze_flow_density_correlation(
    flow_results: Dict[str, Any],
    density_results: Dict[str, Any],
    segments_config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Analyze correlation between flow patterns and density peaks.
    
    Args:
        flow_results: Results from analyze_temporal_flow_segments
        density_results: Results from analyze_density_segments
        segments_config: Configuration from load_density_cfg
        
    Returns:
        Dict with correlation analysis results
    """
    logger.info("Starting Flow↔Density correlation analysis")
    
    # Extract flow data
    flow_segments = flow_results.get("segments", [])
    flow_summary = {
        "total_segments": flow_results.get("total_segments", 0),
        "segments_with_convergence": flow_results.get("segments_with_convergence", 0),
        "convergence_rate": flow_results.get("segments_with_convergence", 0) / max(flow_results.get("total_segments", 1), 1) * 100
    }
    
    # Extract density data
    density_segments = density_results.get("segments", {})
    density_summary = {
        "total_segments": len(density_segments),
        "processed_segments": len(density_segments),
        "high_density_segments": 0,
        "peak_density_value": 0.0
    }
    
    # Calculate density statistics
    for segment_id, segment_data in density_segments.items():
        if isinstance(segment_data, dict) and segment_data.get("ok", False):
            density_value = segment_data.get("density_value", 0.0)
            density_summary["peak_density_value"] = max(density_summary["peak_density_value"], density_value)
            if density_value >= 1.08:  # E/F threshold
                density_summary["high_density_segments"] += 1
    
    # Create correlation analysis
    correlations = []
    
    # Analyze each segment for flow-density relationships
    for flow_seg in flow_segments:
        seg_id = flow_seg.get("seg_id", "")
        flow_type = flow_seg.get("flow_type", "none")
        has_convergence = flow_seg.get("has_convergence", False)
        
        # Find corresponding density segment
        density_seg = density_segments.get(seg_id)
        
        if density_seg and isinstance(density_seg, dict) and density_seg.get("ok", False):
            density_value = density_seg.get("density_value", 0.0)
            density_class = classify_density_level(density_value)
            
            # Calculate flow intensity metrics
            flow_intensity = calculate_flow_intensity(flow_seg)
            
            # Determine correlation type
            correlation_type = determine_correlation_type(
                flow_type, has_convergence, density_class, flow_intensity
            )
            
            correlation = {
                "segment_id": seg_id,
                "segment_label": segments_config.get(seg_id, {}).get("seg_label", seg_id),
                "flow_type": flow_type,
                "has_convergence": has_convergence,
                "density_value": density_value,
                "density_class": density_class,
                "flow_intensity": flow_intensity,
                "correlation_type": correlation_type,
                "insights": generate_correlation_insights(
                    seg_id, flow_type, density_class, flow_intensity, has_convergence
                )
            }
            correlations.append(correlation)
    
    # Generate summary insights
    summary_insights = generate_summary_insights(correlations, flow_summary, density_summary)
    
    return {
        "ok": True,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "analysis_type": "flow_density_correlation",
        "flow_summary": flow_summary,
        "density_summary": density_summary,
        "correlations": correlations,
        "summary_insights": summary_insights,
        "total_correlations": len(correlations)
    }


def classify_density_level(density_value: float) -> str:
    """Classify density level based on LOS thresholds."""
    if density_value >= 1.63:
        return "F"  # Extremely Dense
    elif density_value >= 1.08:
        return "E"  # Very Dense
    elif density_value >= 0.72:
        return "D"  # Dense
    elif density_value >= 0.54:
        return "C"  # Moderate
    elif density_value >= 0.36:
        return "B"  # Comfortable
    else:
        return "A"  # Free Flow


def calculate_flow_intensity(flow_segment: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate flow intensity metrics for a segment."""
    # Extract flow metrics
    total_a = flow_segment.get("total_a", 0)
    total_b = flow_segment.get("total_b", 0)
    overtakes_a = flow_segment.get("overtakes_a", 0)
    overtakes_b = flow_segment.get("overtakes_b", 0)
    
    # Calculate intensity metrics
    total_runners = total_a + total_b
    total_overtakes = overtakes_a + overtakes_b
    
    if total_runners > 0:
        overtake_rate = (total_overtakes / total_runners) * 100
    else:
        overtake_rate = 0.0
    
    # Classify intensity
    if overtake_rate >= 50:
        intensity_level = "high"
    elif overtake_rate >= 25:
        intensity_level = "medium"
    elif overtake_rate > 0:
        intensity_level = "low"
    else:
        intensity_level = "none"
    
    return {
        "total_runners": total_runners,
        "total_overtakes": total_overtakes,
        "overtake_rate": overtake_rate,
        "intensity_level": intensity_level
    }


def determine_correlation_type(
    flow_type: str,
    has_convergence: bool,
    density_class: str,
    flow_intensity: Dict[str, Any]
) -> str:
    """Determine the type of flow-density correlation."""
    intensity_level = flow_intensity.get("intensity_level", "none")
    
    # High density + high flow intensity = critical correlation
    if density_class in ["E", "F"] and intensity_level == "high":
        return "critical_correlation"
    
    # High density + medium flow intensity = significant correlation
    elif density_class in ["E", "F"] and intensity_level in ["medium", "high"]:
        return "significant_correlation"
    
    # Medium density + high flow intensity = moderate correlation
    elif density_class in ["C", "D"] and intensity_level == "high":
        return "moderate_correlation"
    
    # Low density + high flow intensity = flow_dominant
    elif density_class in ["A", "B"] and intensity_level in ["medium", "high"]:
        return "flow_dominant"
    
    # High density + low flow intensity = density_dominant
    elif density_class in ["E", "F"] and intensity_level in ["none", "low"]:
        return "density_dominant"
    
    # No convergence = no_correlation
    elif not has_convergence:
        return "no_correlation"
    
    else:
        return "minimal_correlation"


def generate_correlation_insights(
    seg_id: str,
    flow_type: str,
    density_class: str,
    flow_intensity: Dict[str, Any],
    has_convergence: bool
) -> List[str]:
    """Generate specific insights for a segment's flow-density correlation."""
    insights = []
    
    intensity_level = flow_intensity.get("intensity_level", "none")
    overtake_rate = flow_intensity.get("overtake_rate", 0.0)
    
    # Density-based insights
    if density_class in ["E", "F"]:
        insights.append(f"High density area (LOS {density_class}) - requires careful monitoring")
    elif density_class in ["C", "D"]:
        insights.append(f"Moderate density (LOS {density_class}) - standard monitoring")
    
    # Flow-based insights
    if intensity_level == "high":
        insights.append(f"High flow intensity ({overtake_rate:.1f}% overtake rate) - complex runner interactions")
    elif intensity_level == "medium":
        insights.append(f"Medium flow intensity ({overtake_rate:.1f}% overtake rate) - moderate interactions")
    
    # Flow type insights
    if flow_type == "counterflow":
        insights.append("Counterflow pattern - bidirectional runner movement")
    elif flow_type == "merge":
        insights.append("Merge pattern - runners converging from different directions")
    elif flow_type == "overtake":
        insights.append("Overtake pattern - unidirectional passing")
    
    # Convergence insights
    if has_convergence:
        insights.append("Active convergence zone - runners from different events interact")
    else:
        insights.append("No convergence - single event or no temporal overlap")
    
    return insights


def generate_summary_insights(
    correlations: List[Dict[str, Any]],
    flow_summary: Dict[str, Any],
    density_summary: Dict[str, Any]
) -> List[str]:
    """Generate high-level summary insights."""
    insights = []
    
    # Count correlation types
    correlation_counts = {}
    for corr in correlations:
        corr_type = corr.get("correlation_type", "unknown")
        correlation_counts[corr_type] = correlation_counts.get(corr_type, 0) + 1
    
    # Flow summary insights
    convergence_rate = flow_summary.get("convergence_rate", 0)
    insights.append(f"Flow Analysis: {convergence_rate:.1f}% of segments have convergence zones")
    
    # Density summary insights
    high_density_count = density_summary.get("high_density_segments", 0)
    total_segments = density_summary.get("total_segments", 1)
    high_density_rate = (high_density_count / total_segments) * 100
    insights.append(f"Density Analysis: {high_density_rate:.1f}% of segments have high density (E/F LOS)")
    
    # Critical correlations
    critical_count = correlation_counts.get("critical_correlation", 0)
    if critical_count > 0:
        insights.append(f"⚠️  {critical_count} segments have critical flow-density correlations (high density + high flow intensity)")
    
    # Significant correlations
    significant_count = correlation_counts.get("significant_correlation", 0)
    if significant_count > 0:
        insights.append(f"📊 {significant_count} segments have significant flow-density correlations")
    
    # Flow-dominant areas
    flow_dominant_count = correlation_counts.get("flow_dominant", 0)
    if flow_dominant_count > 0:
        insights.append(f"🔄 {flow_dominant_count} segments are flow-dominant (low density but high flow activity)")
    
    # Density-dominant areas
    density_dominant_count = correlation_counts.get("density_dominant", 0)
    if density_dominant_count > 0:
        insights.append(f"👥 {density_dominant_count} segments are density-dominant (high density but low flow activity)")
    
    return insights


def export_correlation_report(
    correlation_results: Dict[str, Any],
    output_dir: str = "reports"
) -> Dict[str, str]:
    """Export correlation analysis to markdown and CSV files."""
    import os
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate markdown report
    md_content = generate_correlation_markdown(correlation_results)
    md_path = os.path.join(output_dir, f"{timestamp}-Flow-Density-Correlation.md")
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    # Generate CSV report
    csv_content = generate_correlation_csv(correlation_results)
    csv_path = os.path.join(output_dir, f"{timestamp}-Flow-Density-Correlation.csv")
    with open(csv_path, 'w', encoding='utf-8') as f:
        f.write(csv_content)
    
    return {
        "markdown_path": md_path,
        "csv_path": csv_path,
        "timestamp": timestamp
    }


def generate_correlation_markdown(correlation_results: Dict[str, Any]) -> str:
    """Generate markdown report for correlation analysis."""
    timestamp = correlation_results.get("timestamp", "Unknown")
    flow_summary = correlation_results.get("flow_summary", {})
    density_summary = correlation_results.get("density_summary", {})
    correlations = correlation_results.get("correlations", [])
    summary_insights = correlation_results.get("summary_insights", [])
    
    md = f"""# Flow↔Density Correlation Analysis Report

**Generated:** {timestamp}

**Analysis Type:** Flow-Density Correlation

## Summary

This report analyzes the correlation between temporal flow patterns and density concentrations to provide insights for race management.

### Flow Analysis Summary

| Metric | Value |
|--------|-------|
| Total Segments | {flow_summary.get('total_segments', 0)} |
| Segments with Convergence | {flow_summary.get('segments_with_convergence', 0)} |
| Convergence Rate | {flow_summary.get('convergence_rate', 0):.1f}% |

### Density Analysis Summary

| Metric | Value |
|--------|-------|
| Total Segments | {density_summary.get('total_segments', 0)} |
| Processed Segments | {density_summary.get('processed_segments', 0)} |
| High Density Segments (E/F LOS) | {density_summary.get('high_density_segments', 0)} |
| Peak Density Value | {density_summary.get('peak_density_value', 0):.2f} runners/m² |

## Key Insights

"""
    
    for insight in summary_insights:
        md += f"- {insight}\n"
    
    md += f"""
## Segment Correlation Analysis

| Segment | Flow Type | Convergence | Density Class | Flow Intensity | Correlation Type | Insights |
|---------|-----------|-------------|---------------|----------------|------------------|----------|
"""
    
    for corr in correlations:
        insights_str = "; ".join(corr.get("insights", []))
        md += f"| {corr.get('segment_id', 'N/A')} | {corr.get('flow_type', 'N/A')} | {'Yes' if corr.get('has_convergence', False) else 'No'} | {corr.get('density_class', 'N/A')} | {corr.get('flow_intensity', {}).get('intensity_level', 'N/A')} | {corr.get('correlation_type', 'N/A')} | {insights_str} |\n"
    
    md += f"""
## Methodology

### Density Classification
- **A**: Free Flow (0.00-0.36 runners/m²)
- **B**: Comfortable (0.36-0.54 runners/m²)
- **C**: Moderate (0.54-0.72 runners/m²)
- **D**: Dense (0.72-1.08 runners/m²)
- **E**: Very Dense (1.08-1.63 runners/m²)
- **F**: Extremely Dense (1.63+ runners/m²)

### Flow Intensity Classification
- **High**: ≥50% overtake rate
- **Medium**: 25-49% overtake rate
- **Low**: 1-24% overtake rate
- **None**: 0% overtake rate

### Correlation Types
- **Critical**: High density + High flow intensity
- **Significant**: High density + Medium/High flow intensity
- **Moderate**: Medium density + High flow intensity
- **Flow Dominant**: Low density + High flow intensity
- **Density Dominant**: High density + Low flow intensity
- **Minimal**: Other combinations
- **No Correlation**: No convergence zones

## Recommendations

Based on the correlation analysis:

1. **Monitor Critical Correlations**: Segments with critical correlations require immediate attention
2. **Plan for Significant Correlations**: Segments with significant correlations need careful planning
3. **Optimize Flow Dominant Areas**: Consider flow management strategies for flow-dominant segments
4. **Address Density Dominant Areas**: Implement density reduction strategies for density-dominant segments

---
*Report generated by Flow↔Density Correlation Analysis Module v1.6.0*
"""
    
    return md


def generate_correlation_csv(correlation_results: Dict[str, Any]) -> str:
    """Generate CSV report for correlation analysis."""
    correlations = correlation_results.get("correlations", [])
    
    if not correlations:
        return "segment_id,flow_type,has_convergence,density_class,flow_intensity,correlation_type,insights\n"
    
    # Create CSV content
    csv_lines = ["segment_id,flow_type,has_convergence,density_class,flow_intensity,correlation_type,insights"]
    
    for corr in correlations:
        insights_str = "; ".join(corr.get("insights", []))
        csv_lines.append(f"{corr.get('segment_id', '')},{corr.get('flow_type', '')},{corr.get('has_convergence', False)},{corr.get('density_class', '')},{corr.get('flow_intensity', {}).get('intensity_level', '')},{corr.get('correlation_type', '')},\"{insights_str}\"")
    
    return "\n".join(csv_lines) + "\n"
