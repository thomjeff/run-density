"""
Generate Front-End Data from Analytics Outputs

Temporary script to convert analytics reports into front-end JSON artifacts.
This demonstrates the Phase 5 export module using real E2E data.

Usage:
    python scripts/generate_frontend_data.py
"""

import sys
import os
from pathlib import Path
import pandas as pd
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from analytics.export_frontend_artifacts import (
    write_segments_geojson,
    write_segment_metrics_json,
    write_flags_json,
    write_meta_json
)

def load_segments_from_csv():
    """Load segments from segments.csv and convert to GeoJSON."""
    print("[Generate] Loading segments from segments.csv...")
    
    # Build GeoJSON from segments.csv
    df = pd.read_csv("data/segments.csv")
    features = []
    
    for _, row in df.iterrows():
        # Determine which events use this segment
        events = []
        if row.get("full") == "y":
            events.append("Full")
        if row.get("half") == "y":
            events.append("Half")
        if row.get("10K") == "y":
            events.append("10K")
        
        # Calculate segment length (use Full as default)
        length_m = row.get("full_length", 0) * 1000  # Convert km to m
        
        features.append({
            "type": "Feature",
            "properties": {
                "segment_id": row["seg_id"],
                "label": row["seg_label"],
                "length_m": float(length_m),
                "events": events
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [[0, 0], [0.001, 0.001]]  # Placeholder coordinates
            }
        })
    
    print(f"[Generate]    ✅ Created {len(features)} segments from CSV")
    return {"type": "FeatureCollection", "features": features}


def extract_segment_metrics_from_flow():
    """Extract segment metrics from latest Flow.csv."""
    print("[Generate] Extracting metrics from Flow.csv...")
    
    # Find latest Flow.csv
    flow_files = sorted(Path("reports").rglob("*-Flow.csv"), reverse=True)
    if not flow_files:
        print("[Generate]    ⚠️  No Flow.csv found")
        return []
    
    flow_csv = flow_files[0]
    print(f"[Generate]    📄 Using {flow_csv}")
    
    df = pd.read_csv(flow_csv)
    
    # Group by segment to get worst-case metrics
    metrics = []
    for seg_id in df["seg_id"].unique():
        seg_data = df[df["seg_id"] == seg_id]
        
        # Calculate metrics
        max_copresence = seg_data["copresence_a"].fillna(0).max()
        max_overtaking = seg_data["overtaking_a"].fillna(0).max()
        
        # Simple LOS classification based on activity
        if max_copresence > 100 or max_overtaking > 50:
            worst_los = "E"
        elif max_copresence > 50 or max_overtaking > 20:
            worst_los = "D"
        elif max_copresence > 20 or max_overtaking > 10:
            worst_los = "C"
        elif max_copresence > 10 or max_overtaking > 5:
            worst_los = "B"
        else:
            worst_los = "A"
        
        metrics.append({
            "segment_id": seg_id,
            "worst_los": worst_los,
            "peak_density_window": "08:00–08:20",  # Simplified for demo
            "co_presence_pct": float(min(max_copresence / seg_data["total_a"].max() * 100 if seg_data["total_a"].max() > 0 else 0, 100)),
            "overtaking_pct": float(min(max_overtaking / seg_data["total_a"].max() * 100 if seg_data["total_a"].max() > 0 else 0, 100)),
            "utilization_pct": 50.0  # Placeholder
        })
    
    print(f"[Generate]    ✅ Extracted metrics for {len(metrics)} segments")
    return metrics


def extract_flags_from_flow():
    """Extract flags from Flow.csv based on convergence and overtaking."""
    print("[Generate] Extracting flags from Flow.csv...")
    
    # Find latest Flow.csv
    flow_files = sorted(Path("reports").rglob("*-Flow.csv"), reverse=True)
    if not flow_files:
        return []
    
    df = pd.read_csv(flow_files[0])
    
    flags = []
    for _, row in df.iterrows():
        # Flag high convergence
        if row.get("has_convergence") == True:
            flags.append({
                "segment_id": row["seg_id"],
                "flag_type": "co_presence",
                "severity": "warn",
                "window": "08:00–08:20",
                "note": f"{row['event_a']}/{row['event_b']} convergence"
            })
        
        # Flag high overtaking
        if row.get("overtaking_a", 0) > 20 or row.get("overtaking_b", 0) > 20:
            flags.append({
                "segment_id": row["seg_id"],
                "flag_type": "overtaking",
                "severity": "info",
                "window": "08:00–08:20",
                "note": f"{int(row.get('overtaking_a', 0))} overtakes"
            })
    
    print(f"[Generate]    ✅ Extracted {len(flags)} flags")
    return flags


def main():
    """Generate all front-end data files from analytics outputs."""
    print("\n" + "="*60)
    print("GENERATE FRONT-END DATA FROM ANALYTICS")
    print("="*60 + "\n")
    
    # 1. Segments GeoJSON
    segments_geojson = load_segments_from_csv()
    write_segments_geojson(segments_geojson)
    
    # 2. Segment Metrics
    segment_metrics = extract_segment_metrics_from_flow()
    write_segment_metrics_json(segment_metrics)
    
    # 3. Flags
    flags = extract_flags_from_flow()
    write_flags_json(flags)
    
    # 4. Meta
    write_meta_json(env="local")
    
    print("\n" + "="*60)
    print("✅ FRONT-END DATA GENERATION COMPLETE")
    print("="*60)
    print("\nNext steps:")
    print("  1. Run Phase 1 validator: python frontend/validation/scripts/validate_data.py")
    print("  2. Run E2E parity: python frontend/e2e/e2e_validate.py")
    print("  3. Build map: python frontend/map/scripts/generate_map.py")
    print("  4. Build dashboard: python frontend/dashboard/scripts/generate_dashboard.py")
    print("  5. Build report: python frontend/reports/scripts/build_density_report.py")
    print("  6. Create bundle: python frontend/release/build_bundle.py")
    print("\nOr run all at once:")
    print("  ./scripts/build_all_frontend.sh\n")


if __name__ == "__main__":
    main()

