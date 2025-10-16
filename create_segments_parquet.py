#!/usr/bin/env python3
"""
Create segments.parquet from segments.csv for Issue #246
Converts the existing segments.csv to the required parquet format with proper schema.
"""

import pandas as pd
import numpy as np
from pathlib import Path

def create_segments_parquet():
    """Convert segments.csv to segments.parquet with the required schema."""
    
    # Read the existing segments.csv
    segments_csv_path = Path("data/segments.csv")
    if not segments_csv_path.exists():
        raise FileNotFoundError(f"segments.csv not found at {segments_csv_path}")
    
    df = pd.read_csv(segments_csv_path)
    print(f"📊 Loaded {len(df)} segments from {segments_csv_path}")
    
    # Map segment types based on flow_type and other characteristics
    def determine_segment_type(row):
        """Determine segment_type based on flow_type and other characteristics."""
        flow_type = row.get('flow_type', '')
        seg_id = row.get('seg_id', '')
        
        # Start corral
        if seg_id == 'A1':
            return 'start_corral'
        
        # Narrow segments (bi-directional or narrow width)
        if row.get('direction') == 'bi' or row.get('width_m', 0) <= 1.5:
            return 'on_course_narrow'
        
        # Open segments (uni-directional with wider width)
        if row.get('direction') == 'uni' and row.get('width_m', 0) > 1.5:
            return 'on_course_open'
        
        # Default fallback
        return 'on_course_open'
    
    # Create the new dataframe with required schema
    segments_parquet = pd.DataFrame({
        'segment_id': df['seg_id'],
        'seg_label': df['seg_label'],
        'segment_type': df.apply(determine_segment_type, axis=1),
        'width_m': df['width_m'].astype(float),
        'schema_key': df.apply(lambda row: f"{determine_segment_type(row)}_schema", axis=1),
        'order_index': range(len(df))  # Simple ordering based on CSV order
    })
    
    # Add any additional useful fields from the original CSV
    segments_parquet['direction'] = df['direction']
    segments_parquet['full_enabled'] = df['full'] == 'y'
    segments_parquet['half_enabled'] = df['half'] == 'y'
    segments_parquet['10k_enabled'] = df['10K'] == 'y'
    segments_parquet['overtake_flag'] = df['overtake_flag'] == 'y'
    segments_parquet['flow_type'] = df['flow_type']
    segments_parquet['notes'] = df['notes']
    
    # Save to parquet
    output_path = Path("data/segments.parquet")
    segments_parquet.to_parquet(output_path, index=False)
    
    print(f"✅ Created {output_path} with {len(segments_parquet)} segments")
    print(f"📋 Schema:")
    for col in segments_parquet.columns:
        print(f"  - {col}: {segments_parquet[col].dtype}")
    
    # Show sample data
    print(f"\n📊 Sample data:")
    print(segments_parquet[['segment_id', 'seg_label', 'segment_type', 'width_m', 'schema_key']].head())
    
    return output_path

if __name__ == "__main__":
    create_segments_parquet()
