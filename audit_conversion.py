#!/usr/bin/env python3
"""
Audit script for segments_new.csv conversion logic
Tests the convert_segments_new_to_flow_format function
"""

import pandas as pd
import sys
import os

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import from app directory
from app.flow import convert_segments_new_to_flow_format

def audit_conversion():
    """Audit the conversion function to see what pairs are generated"""
    
    # Load segments_new.csv
    segments_df = pd.read_csv('data/segments_new.csv')
    
    print("=== SEGMENTS_NEW.CSV AUDIT ===")
    print(f"Total segments: {len(segments_df)}")
    print()
    
    # Check segments with overtake_flag = 'y'
    overtake_segments = segments_df[segments_df['overtake_flag'] == 'y']
    print(f"Segments with overtake_flag='y': {len(overtake_segments)}")
    for _, seg in overtake_segments.iterrows():
        events = []
        if seg.get('full') == 'y':
            events.append('Full')
        if seg.get('half') == 'y':
            events.append('Half')
        if seg.get('10K') == 'y':
            events.append('10K')
        print(f"  {seg['seg_id']}: {events} (flow_type: {seg.get('flow_type', 'N/A')})")
    
    print()
    
    # Convert to flow format
    converted_df = convert_segments_new_to_flow_format(segments_df)
    
    print("=== CONVERSION RESULTS ===")
    print(f"Total converted pairs: {len(converted_df)}")
    print()
    
    # Group by seg_id to see what pairs are generated
    for seg_id in converted_df['seg_id'].unique():
        seg_pairs = converted_df[converted_df['seg_id'] == seg_id]
        print(f"{seg_id} ({len(seg_pairs)} pairs):")
        for _, pair in seg_pairs.iterrows():
            print(f"  {pair['eventa']} vs {pair['eventb']} - {pair.get('flow_type', 'N/A')} - overtake_flag: {pair.get('overtake_flag', 'N/A')}")
        print()
    
    # Check for missing pairs (F1 should have 3 pairs)
    f1_pairs = converted_df[converted_df['seg_id'] == 'F1']
    print(f"F1 pairs found: {len(f1_pairs)}")
    if len(f1_pairs) < 3:
        print("WARNING: F1 should have 3 pairs (10K/Half, 10K/Full, Half/Full)")
        expected_pairs = [('10K', 'Half'), ('10K', 'Full'), ('Half', 'Full')]
        for event_a, event_b in expected_pairs:
            found = False
            for _, pair in f1_pairs.iterrows():
                if (pair['eventa'] == event_a and pair['eventb'] == event_b) or \
                   (pair['eventa'] == event_b and pair['eventb'] == event_a):
                    found = True
                    break
            if not found:
                print(f"  MISSING: {event_a} vs {event_b}")
    
    # Check for B2 segment
    b2_pairs = converted_df[converted_df['seg_id'] == 'B2']
    print(f"B2 pairs found: {len(b2_pairs)}")
    if len(b2_pairs) == 0:
        print("WARNING: B2 segment missing from conversion")

if __name__ == "__main__":
    audit_conversion()
