#!/usr/bin/env python3
"""
Generate improved per-event density analysis report with better formatting and accuracy.

This script addresses user feedback:
1. Order events by start time
2. Round metrics to 3 decimal places  
3. Fix sustained periods logic for events not yet started
4. Improve table formatting
5. Add A-F LOS scores
6. Format duration as hh:mm:ss
7. Use human-readable column names
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

import pandas as pd
from datetime import datetime, timedelta
from app.density import analyze_density_segments, DensityConfig

def format_duration(seconds):
    """Format duration in seconds as hh:mm:ss."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def get_los_score(density, thresholds):
    """Get LOS score (A-F) for a given density and thresholds."""
    for level, (min_val, max_val) in thresholds.items():
        if min_val <= density < max_val:
            return level
    return "A"  # Default

# Define LOS thresholds (from DensityAnalyzer)
LOS_AREAL_THRESHOLDS = {
    "A": (0.0, 0.11),      # Comfortable
    "C": (0.11, 0.17),     # Moderate  
    "E": (0.17, 0.20),     # Busy
    "F": (0.20, float('inf'))  # Critical
}

LOS_CROWD_THRESHOLDS = {
    "A": (0.0, 0.22),      # Comfortable
    "C": (0.22, 0.35),     # Moderate
    "E": (0.35, 0.60),     # Busy  
    "F": (0.60, float('inf'))  # Critical
}

def generate_improved_per_event_report():
    """Generate improved per-event density report."""
    print("📊 Generating Improved Per-Event Density Analysis Report...")
    
    # Load data
    pace_data = pd.read_csv("data/your_pace_data.csv")
    
    # Set up start times
    start_times = {
        "Full": datetime(2025, 9, 4, 7, 0),   # 07:00
        "10K": datetime(2025, 9, 4, 7, 20),   # 07:20  
        "Half": datetime(2025, 9, 4, 7, 40)   # 07:40
    }
    
    # Create analyzer
    config = DensityConfig(step_km=0.3, bin_seconds=30)
    
    # Run analysis
    print("🔍 Running density analysis...")
    results = analyze_density_segments(pace_data, start_times, config)
    
    # Generate report
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    report_path = f"reports/analysis/{timestamp}_Improved_Per_Event_Density_Report.md"
    
    print(f"📝 Generating report: {report_path}")
    
    with open(report_path, 'w') as f:
        f.write("# Improved Per-Event Density Analysis Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Analysis Period:** {results['summary']['analysis_start']} to {results['summary']['analysis_end']}\n")
        f.write(f"**Time Bin Size:** {results['summary']['time_bin_seconds']} seconds\n")
        f.write(f"**Total Segments:** {results['summary']['total_segments']}\n")
        f.write(f"**Processed Segments:** {results['summary']['processed_segments']}\n")
        f.write(f"**Skipped Segments:** {results['summary']['skipped_segments']}\n\n")
        
        f.write("## Legend\n\n")
        f.write("- **TOT**: Time Over Threshold (seconds above E/F LOS thresholds)\n")
        f.write("- **LOS**: Level of Service (A=Comfortable, C=Moderate, E=Busy, F=Critical)\n")
        f.write("- **Experienced Density**: What runners actually experience (includes co-present runners from other events)\n")
        f.write("- **Self Density**: Only that event's runners (not shown in this report)\n")
        f.write("- **Active Window**: Time period when the event has runners present in the segment\n\n")
        
        f.write("## Event Start Times\n\n")
        f.write("| Event | Start Time | Runners |\n")
        f.write("|-------|------------|----------|\n")
        for event, start_time in start_times.items():
            count = len(pace_data[pace_data["event"] == event])
            f.write(f"| {event} | {start_time.strftime('%H:%M:%S')} | {count:,} |\n")
        f.write("\n")
        
        # Process each segment
        for seg_id, seg_data in results["segments"].items():
            f.write(f"## {seg_id}: {seg_data['physical_name']}\n\n")
            f.write(f"**Events Included:** {', '.join(seg_data['events_included'])}\n")
            f.write(f"**Physical Name:** {seg_data['physical_name']}\n\n")
            
            # Combined view (existing)
            f.write("### Combined View (All Events)\n\n")
            summary = seg_data['summary']
            
            f.write("**Active Window Summary**\n")
            f.write("| Metric | Value |\n")
            f.write("|--------|-------|\n")
            f.write(f"| Active Start/End | {summary.active_start or 'N/A'} - {summary.active_end or 'N/A'} |\n")
            f.write(f"| Active Duration | {format_duration(summary.active_duration_s)} |\n")
            f.write(f"| Occupancy Rate | {summary.occupancy_rate:.1%} |\n")
            f.write(f"| Peak Concurrency | {summary.active_peak_concurrency:,} |\n")
            f.write(f"| Peak Areal Density | {summary.active_peak_areal:.3f} runners/m² |\n")
            f.write(f"| Peak Crowd Density | {summary.active_peak_crowd:.3f} runners/m |\n")
            f.write(f"| P95 Areal Density | {summary.active_p95_areal:.3f} runners/m² |\n")
            f.write(f"| P95 Crowd Density | {summary.active_p95_crowd:.3f} runners/m |\n")
            f.write(f"| Active Mean Areal | {summary.active_mean_areal:.3f} runners/m² |\n")
            f.write(f"| Active Mean Crowd | {summary.active_mean_crowd:.3f} runners/m |\n")
            f.write(f"| TOT Areal (E/F) | {summary.active_tot_areal_sec}s |\n")
            f.write(f"| TOT Crowd (E/F) | {summary.active_tot_crowd_sec}s |\n")
            f.write("\n")
            
            # Per-event views - ORDER BY START TIME
            if 'per_event' in seg_data and seg_data['per_event']:
                f.write("### Per-Event Analysis (Experienced Density)\n\n")
                
                # Sort events by start time
                event_order = sorted(seg_data['per_event'].keys(), 
                                  key=lambda e: start_times[e])
                
                for event in event_order:
                    event_summary = seg_data['per_event'][event]
                    f.write(f"#### {event} Event — Start {start_times[event].strftime('%H:%M:%S')} — N={event_summary.n_event_runners:,}\n\n")
                    
                    f.write("**Active Window (Experienced)**\n")
                    f.write("| Metric | Value |\n")
                    f.write("|--------|-------|\n")
                    f.write(f"| Active Start/End | {event_summary.active_start or 'N/A'} – {event_summary.active_end or 'N/A'} |\n")
                    f.write(f"| Active Duration | {format_duration(event_summary.active_duration_s)} |\n")
                    f.write(f"| Occupancy Rate | {event_summary.occupancy_rate:.1%} |\n")
                    f.write(f"| Peak Concurrency (Experienced) | {event_summary.peak_concurrency_exp:,} |\n")
                    f.write(f"| Peak Areal Density (Experienced) | {event_summary.peak_areal_exp:.3f} runners/m² |\n")
                    f.write(f"| Peak Crowd Density (Experienced) | {event_summary.peak_crowd_exp:.3f} runners/m |\n")
                    f.write(f"| P95 Areal Density (Experienced) | {event_summary.p95_areal_exp:.3f} runners/m² |\n")
                    f.write(f"| P95 Crowd Density (Experienced) | {event_summary.p95_crowd_exp:.3f} runners/m |\n")
                    f.write(f"| Active Mean Areal (Experienced) | {event_summary.active_mean_areal_exp:.3f} runners/m² |\n")
                    f.write(f"| Active Mean Crowd (Experienced) | {event_summary.active_mean_crowd_exp:.3f} runners/m |\n")
                    f.write(f"| TOT Areal (E/F) | {event_summary.active_tot_areal_exp_sec}s |\n")
                    f.write(f"| TOT Crowd (E/F) | {event_summary.active_tot_crowd_exp_sec}s |\n")
                    f.write("\n")
                    
                    # Add LOS scores
                    f.write("**Level of Service Scores**\n")
                    f.write("| Metric | Value | LOS Score |\n")
                    f.write("|--------|-------|----------|\n")
                    f.write(f"| Peak Areal Density | {event_summary.peak_areal_exp:.3f} runners/m² | {get_los_score(event_summary.peak_areal_exp, LOS_AREAL_THRESHOLDS)} |\n")
                    f.write(f"| Peak Crowd Density | {event_summary.peak_crowd_exp:.3f} runners/m | {get_los_score(event_summary.peak_crowd_exp, LOS_CROWD_THRESHOLDS)} |\n")
                    f.write(f"| P95 Areal Density | {event_summary.p95_areal_exp:.3f} runners/m² | {get_los_score(event_summary.p95_areal_exp, LOS_AREAL_THRESHOLDS)} |\n")
                    f.write(f"| P95 Crowd Density | {event_summary.p95_crowd_exp:.3f} runners/m | {get_los_score(event_summary.p95_crowd_exp, LOS_CROWD_THRESHOLDS)} |\n")
                    f.write(f"| Mean Areal Density | {event_summary.active_mean_areal_exp:.3f} runners/m² | {get_los_score(event_summary.active_mean_areal_exp, LOS_AREAL_THRESHOLDS)} |\n")
                    f.write(f"| Mean Crowd Density | {event_summary.active_mean_crowd_exp:.3f} runners/m | {get_los_score(event_summary.active_mean_crowd_exp, LOS_CROWD_THRESHOLDS)} |\n")
                    f.write("\n")
                    
                    # Sustained periods for this event - FIXED LOGIC
                    if event_summary.sustained_periods:
                        f.write("**Sustained Periods (Experienced)**\n")
                        f.write("| Start | End | Duration | LOS Areal | LOS Crowd | Avg Areal | Avg Crowd | Peak Conc | Events Present |\n")
                        f.write("|-------|-----|----------|-----------|-----------|-----------|-----------|----------|---------------|\n")
                        
                        for period in event_summary.sustained_periods:
                            # Only show events that are actually present during this time period
                            # This is a simplified check - in a full implementation, we would
                            # analyze the actual runner counts by event during each period
                            present_events = [event]  # At minimum, the current event is present
                            
                            # Check if other events could be present during this time period
                            period_start = datetime.strptime(period['start_time'], "%H:%M:%S")
                            period_end = datetime.strptime(period['end_time'], "%H:%M:%S")
                            
                            for other_event in seg_data['events_included']:
                                if other_event != event:
                                    other_start = start_times[other_event]
                                    # Convert to same day for comparison
                                    other_start = other_start.replace(year=period_start.year, month=period_start.month, day=period_start.day)
                                    
                                    # If the other event starts before or during this period, it could be present
                                    if other_start <= period_end:
                                        present_events.append(other_event)
                            
                            events_present = ', '.join(sorted(present_events))
                            f.write(f"| {period['start_time']} | {period['end_time']} | {period['duration_minutes']:.1f} min | "
                                   f"{period['los_areal']} | {period['los_crowd']} | "
                                   f"{period['avg_areal_density']:.3f} | {period['avg_crowd_density']:.3f} | "
                                   f"{period['peak_concurrent_runners']} | {events_present} |\n")
                        f.write("\n")
                    else:
                        f.write("*No sustained periods identified for this event.*\n\n")
            else:
                f.write("### Per-Event Analysis\n\n")
                f.write("*Per-event analysis not available for this segment.*\n\n")
            
            # Combined sustained periods
            if seg_data['sustained_periods']:
                f.write("### Combined Sustained Periods\n\n")
                f.write("| Start | End | Duration | LOS Areal | LOS Crowd | Avg Areal | Avg Crowd | Peak Conc |\n")
                f.write("|-------|-----|----------|-----------|-----------|-----------|-----------|----------|\n")
                
                for period in seg_data['sustained_periods']:
                    f.write(f"| {period['start_time']} | {period['end_time']} | {period['duration_minutes']:.1f} min | "
                           f"{period['los_areal']} | {period['los_crowd']} | "
                           f"{period['avg_areal_density']:.3f} | {period['avg_crowd_density']:.3f} | "
                           f"{period['peak_concurrent_runners']} |\n")
                f.write("\n")
            else:
                f.write("### Combined Sustained Periods\n\n")
                f.write("*No sustained periods identified.*\n\n")
            
            f.write("---\n\n")
    
    print(f"✅ Improved report generated successfully: {report_path}")
    return report_path

if __name__ == "__main__":
    try:
        report_path = generate_improved_per_event_report()
        print(f"\n🎉 Improved Per-Event Density Analysis Report completed!")
        print(f"📄 Report saved to: {report_path}")
    except Exception as e:
        print(f"\n❌ Report generation failed: {e}")
        import traceback
        traceback.print_exc()
