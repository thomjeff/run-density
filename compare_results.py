#!/usr/bin/env python3
"""Compare actual v2 results against expected results."""
import pandas as pd
import re
import sys

# Read actual files
actual_flow = pd.read_csv("/app/runflow/NWciG7emXmAEqjieDmqorg/sun/reports/Flow.csv")
actual_locations = pd.read_csv("/app/runflow/NWciG7emXmAEqjieDmqorg/sun/reports/Locations.csv")
with open("/app/runflow/NWciG7emXmAEqjieDmqorg/sun/reports/Density.md", 'r') as f:
    actual_density = f.read()

# Read expected files
expected_flow = pd.read_csv("/app/cursor/expected_results/reports/expect_Flow.csv")
expected_locations = pd.read_csv("/app/cursor/expected_results/reports/expect_Locations.csv")
with open("/app/cursor/expected_results/reports/expect_Density.md", 'r') as f:
    expected_density = f.read()

print("=" * 70)
print("COMPREHENSIVE RESULTS COMPARISON")
print("=" * 70)

# ===== FLOW.CSV COMPARISON =====
print("\n" + "=" * 70)
print("1. FLOW.CSV COMPARISON")
print("=" * 70)

print(f"\nRow Count:")
print(f"  Actual: {len(actual_flow)} rows")
print(f"  Expected: {len(expected_flow)} rows")
print(f"  Status: {'✓ MATCH' if len(actual_flow) == len(expected_flow) else '✗ MISMATCH'}")

# Segments
actual_segs = set(actual_flow['seg_id'].unique())
expected_segs = set(expected_flow['seg_id'].unique())
print(f"\nSegments:")
print(f"  Actual: {len(actual_segs)} segments - {sorted(actual_segs)}")
print(f"  Expected: {len(expected_segs)} segments - {sorted(expected_segs)}")
print(f"  Status: {'✓ MATCH' if actual_segs == expected_segs else '✗ MISMATCH'}")
if actual_segs != expected_segs:
    missing = expected_segs - actual_segs
    extra = actual_segs - expected_segs
    if missing:
        print(f"  Missing in actual: {sorted(missing)}")
    if extra:
        print(f"  Extra in actual: {sorted(extra)}")

# Event pairs
actual_pairs = set(tuple(sorted([r['event_a'], r['event_b']])) for _, r in actual_flow[['event_a', 'event_b']].drop_duplicates().iterrows())
expected_pairs = set(tuple(sorted([r['event_a'], r['event_b']])) for _, r in expected_flow[['event_a', 'event_b']].drop_duplicates().iterrows())
print(f"\nEvent Pairs:")
print(f"  Actual: {sorted(actual_pairs)}")
print(f"  Expected: {sorted(expected_pairs)}")
print(f"  Status: {'✓ MATCH' if actual_pairs == expected_pairs else '✗ MISMATCH'}")

# Segment-pair combinations
actual_combos = set((r['seg_id'], tuple(sorted([r['event_a'], r['event_b']]))) for _, r in actual_flow.iterrows())
expected_combos = set((r['seg_id'], tuple(sorted([r['event_a'], r['event_b']]))) for _, r in expected_flow.iterrows())
print(f"\nSegment-Pair Combinations:")
print(f"  Actual: {len(actual_combos)} combinations")
print(f"  Expected: {len(expected_combos)} combinations")
print(f"  Status: {'✓ MATCH' if actual_combos == expected_combos else '✗ MISMATCH'}")

if actual_combos != expected_combos:
    missing = expected_combos - actual_combos
    extra = actual_combos - expected_combos
    if missing:
        print(f"  Missing in actual ({len(missing)}): {sorted(list(missing))[:10]}")
        if len(missing) > 10:
            print(f"    ... and {len(missing) - 10} more")
    if extra:
        print(f"  Extra in actual ({len(extra)}): {sorted(list(extra))[:10]}")
        if len(extra) > 10:
            print(f"    ... and {len(extra) - 10} more")

# Value comparison for matching segments
common_combos = actual_combos & expected_combos
if common_combos:
    mismatches = []
    for seg_id, pair in sorted(common_combos):
        event_a, event_b = pair
        actual_rows = actual_flow[(actual_flow['seg_id'] == seg_id) & 
                                (actual_flow['event_a'] == event_a) & 
                                (actual_flow['event_b'] == event_b)]
        expected_rows = expected_flow[(expected_flow['seg_id'] == seg_id) & 
                                   (expected_flow['event_a'] == event_a) & 
                                   (expected_flow['event_b'] == event_b)]
        
        if len(actual_rows) == 0 or len(expected_rows) == 0:
            continue
            
        actual_row = actual_rows.iloc[0]
        expected_row = expected_rows.iloc[0]
        
        for col in ['overtaking_a', 'overtaking_b', 'copresence_a', 'copresence_b']:
            if col in actual_row and col in expected_row:
                a_val = actual_row[col]
                e_val = expected_row[col]
                try:
                    if pd.notna(a_val) and pd.notna(e_val):
                        if abs(float(a_val) - float(e_val)) > 0.01:
                            mismatches.append((seg_id, pair, col, a_val, e_val))
                except:
                    if str(a_val) != str(e_val):
                        mismatches.append((seg_id, pair, col, a_val, e_val))
    
    print(f"\nValue Mismatches:")
    if mismatches:
        print(f"  Found {len(mismatches)} mismatches (showing first 10):")
        for seg_id, pair, col, a_val, e_val in mismatches[:10]:
            print(f"    {seg_id} {pair}: {col} = {a_val} (expected {e_val})")
    else:
        print(f"  ✓ All values match for {len(common_combos)} common segment-pairs")

# ===== LOCATIONS.CSV COMPARISON =====
print("\n" + "=" * 70)
print("2. LOCATIONS.CSV COMPARISON")
print("=" * 70)

print(f"\nRow Count:")
print(f"  Actual: {len(actual_locations)} rows")
print(f"  Expected: {len(expected_locations)} rows")
print(f"  Status: {'✓ MATCH' if len(actual_locations) == len(expected_locations) else '✗ MISMATCH'}")

# Columns
actual_cols = set(actual_locations.columns)
expected_cols = set(expected_locations.columns)
print(f"\nColumns:")
print(f"  Actual: {len(actual_cols)} columns")
print(f"  Expected: {len(expected_cols)} columns")
print(f"  Status: {'✓ MATCH' if actual_cols == expected_cols else '✗ MISMATCH'}")
if actual_cols != expected_cols:
    missing = expected_cols - actual_cols
    extra = actual_cols - expected_cols
    if missing:
        print(f"  Missing in actual: {sorted(missing)}")
    if extra:
        print(f"  Extra in actual: {sorted(extra)}")

# Location IDs
if 'loc_id' in actual_locations.columns and 'loc_id' in expected_locations.columns:
    actual_locs = set(actual_locations['loc_id'].unique())
    expected_locs = set(expected_locations['loc_id'].unique())
    print(f"\nLocation IDs:")
    print(f"  Actual: {len(actual_locs)} locations")
    print(f"  Expected: {len(expected_locs)} locations")
    print(f"  Status: {'✓ MATCH' if actual_locs == expected_locs else '✗ MISMATCH'}")

# ===== DENSITY.MD COMPARISON =====
print("\n" + "=" * 70)
print("3. DENSITY.MD COMPARISON")
print("=" * 70)

# Extract metrics
def extract_metrics(content):
    metrics = {}
    
    # Flagged segments/bins
    flagged_seg_match = re.search(r'Segments with Flags:\s*(\d+)\s*/\s*(\d+)', content)
    if flagged_seg_match:
        metrics['flagged_segments'] = (int(flagged_seg_match.group(1)), int(flagged_seg_match.group(2)))
    
    flagged_bin_match = re.search(r'Flagged Bins:\s*(\d+)\s*/\s*(\d+)', content)
    if flagged_bin_match:
        metrics['flagged_bins'] = (int(flagged_bin_match.group(1)), int(flagged_bin_match.group(2)))
    
    # Operational status
    status_match = re.search(r'Operational Status:\s*(.+?)(?:\n|$)', content)
    if status_match:
        metrics['operational_status'] = status_match.group(1).strip()
    
    # Extract segment IDs from tables
    seg_matches = re.findall(r'\|\s*([A-Z]\d+)\s*\|', content)
    if seg_matches:
        metrics['segments'] = sorted(set(seg_matches))
    
    # Extract flagged segments from segment sections
    flagged_segs = []
    seg_sections = re.finditer(r'###\s+Segment\s+([A-Z]\d+)([\s\S]*?)(?=###|$)', content)
    for match in seg_sections:
        seg_id = match.group(1)
        seg_text = match.group(2)
        if 'Watch' in seg_text or 'Flagged' in seg_text or '🔴' in seg_text or '⚠️' in seg_text:
            flagged_segs.append(seg_id)
    metrics['flagged_segment_list'] = sorted(flagged_segs)
    
    return metrics

actual_metrics = extract_metrics(actual_density)
expected_metrics = extract_metrics(expected_density)

print(f"\nFlagged Segments:")
if 'flagged_segments' in actual_metrics and 'flagged_segments' in expected_metrics:
    a_seg = actual_metrics['flagged_segments']
    e_seg = expected_metrics['flagged_segments']
    print(f"  Actual: {a_seg[0]} / {a_seg[1]}")
    print(f"  Expected: {e_seg[0]} / {e_seg[1]}")
    print(f"  Status: {'✓ MATCH' if a_seg == e_seg else '✗ MISMATCH'}")

print(f"\nFlagged Bins:")
if 'flagged_bins' in actual_metrics and 'flagged_bins' in expected_metrics:
    a_bin = actual_metrics['flagged_bins']
    e_bin = expected_metrics['flagged_bins']
    print(f"  Actual: {a_bin[0]} / {a_bin[1]}")
    print(f"  Expected: {e_bin[0]} / {e_bin[1]}")
    print(f"  Status: {'✓ MATCH' if a_bin == e_bin else '✗ MISMATCH'}")

print(f"\nOperational Status:")
if 'operational_status' in actual_metrics and 'operational_status' in expected_metrics:
    a_status = actual_metrics['operational_status']
    e_status = expected_metrics['operational_status']
    print(f"  Actual: {a_status}")
    print(f"  Expected: {e_status}")
    print(f"  Status: {'✓ MATCH' if a_status == e_status else '✗ MISMATCH'}")

print(f"\nSegments in Report:")
if 'segments' in actual_metrics and 'segments' in expected_metrics:
    a_segs = set(actual_metrics['segments'])
    e_segs = set(expected_metrics['segments'])
    print(f"  Actual: {len(a_segs)} segments")
    print(f"  Expected: {len(e_segs)} segments")
    print(f"  Status: {'✓ MATCH' if a_segs == e_segs else '✗ MISMATCH'}")
    if a_segs != e_segs:
        missing = e_segs - a_segs
        extra = a_segs - e_segs
        if missing:
            print(f"  Missing in actual: {sorted(missing)}")
        if extra:
            print(f"  Extra in actual: {sorted(extra)}")

print(f"\nFlagged Segment List:")
if 'flagged_segment_list' in actual_metrics and 'flagged_segment_list' in expected_metrics:
    a_flagged = set(actual_metrics['flagged_segment_list'])
    e_flagged = set(expected_metrics['flagged_segment_list'])
    print(f"  Actual: {len(a_flagged)} flagged - {sorted(a_flagged)}")
    print(f"  Expected: {len(e_flagged)} flagged - {sorted(e_flagged)}")
    print(f"  Status: {'✓ MATCH' if a_flagged == e_flagged else '✗ MISMATCH'}")
    if a_flagged != e_flagged:
        missing = e_flagged - a_flagged
        extra = a_flagged - e_flagged
        if missing:
            print(f"  Missing in actual: {sorted(missing)}")
        if extra:
            print(f"  Extra in actual: {sorted(extra)}")

print("\n" + "=" * 70)
print("COMPARISON COMPLETE")
print("=" * 70)

