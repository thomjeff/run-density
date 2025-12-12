#!/usr/bin/env python3
"""Compare actual Flow.csv with expected Flow.csv."""
import pandas as pd

actual = pd.read_csv("/app/runflow/nHLFrTorDGnT6JGMq6MjRd/sun/reports/Flow.csv")
expected = pd.read_csv("/app/cursor/expected_results/reports/expect_Flow.csv")

print("=" * 70)
print("FLOW.CSV VALUE DIFFERENCES")
print("=" * 70)

# Compare key metrics
key_cols = ['overtaking_a', 'overtaking_b', 'copresence_a', 'copresence_b', 'total_a', 'total_b', 'conflict_length_m']

mismatches = []
for _, exp_row in expected.iterrows():
    seg_id = exp_row['seg_id']
    event_a = exp_row['event_a']
    event_b = exp_row['event_b']
    
    act_rows = actual[(actual['seg_id'] == seg_id) & 
                     (actual['event_a'] == event_a) & 
                     (actual['event_b'] == event_b)]
    
    if len(act_rows) == 0:
        mismatches.append((seg_id, event_a, event_b, 'MISSING', 'Segment-pair missing', None))
        continue
    
    act_row = act_rows.iloc[0]
    
    for col in key_cols:
        if col in exp_row and col in act_row:
            exp_val = exp_row[col]
            act_val = act_row[col]
            
            try:
                if pd.notna(exp_val) and pd.notna(act_val):
                    if abs(float(exp_val) - float(act_val)) > 0.01:
                        mismatches.append((seg_id, event_a, event_b, col, exp_val, act_val))
            except:
                if str(exp_val) != str(act_val):
                    mismatches.append((seg_id, event_a, event_b, col, exp_val, act_val))

if mismatches:
    print(f"\nFound {len(mismatches)} value mismatches:\n")
    by_segment = {}
    for seg_id, ev_a, ev_b, col, exp_val, act_val in mismatches:
        key = (seg_id, ev_a, ev_b)
        if key not in by_segment:
            by_segment[key] = []
        by_segment[key].append((col, exp_val, act_val))
    
    for (seg_id, ev_a, ev_b), cols in sorted(by_segment.items()):
        print(f"{seg_id} ({ev_a}/{ev_b}):")
        for col, exp_val, act_val in cols:
            print(f"  {col}: {exp_val} → {act_val}")
        print()
else:
    print("\n✓ All values match!")

# Check specific segments
print("\n" + "=" * 70)
print("SPECIFIC SEGMENT ANALYSIS (F1, H1, I1)")
print("=" * 70)

for seg_id in ['F1', 'H1', 'I1']:
    print(f"\n--- Segment {seg_id} ---")
    
    exp_fh = expected[(expected['seg_id'] == seg_id) & 
                     (expected['event_a'] == 'Full') & 
                     (expected['event_b'] == 'Half')]
    act_fh = actual[(actual['seg_id'] == seg_id) & 
                   (actual['event_a'] == 'Full') & 
                   (actual['event_b'] == 'Half')]
    
    if len(exp_fh) > 0 and len(act_fh) > 0:
        exp = exp_fh.iloc[0]
        act = act_fh.iloc[0]
        
        print(f"Full-Half pair:")
        print(f"  overtaking_a: {act.get('overtaking_a', 'N/A')} (expected {exp.get('overtaking_a', 'N/A')})")
        print(f"  overtaking_b: {act.get('overtaking_b', 'N/A')} (expected {exp.get('overtaking_b', 'N/A')})")
        print(f"  copresence_a: {act.get('copresence_a', 'N/A')} (expected {exp.get('copresence_a', 'N/A')})")
        print(f"  copresence_b: {act.get('copresence_b', 'N/A')} (expected {exp.get('copresence_b', 'N/A')})")
        print(f"  from_km_a: {act.get('from_km_a', 'N/A')} (expected {exp.get('from_km_a', 'N/A')})")
        print(f"  to_km_a: {act.get('to_km_a', 'N/A')} (expected {exp.get('to_km_a', 'N/A')})")
        print(f"  from_km_b: {act.get('from_km_b', 'N/A')} (expected {exp.get('from_km_b', 'N/A')})")
        print(f"  to_km_b: {act.get('to_km_b', 'N/A')} (expected {exp.get('to_km_b', 'N/A')})")
        print(f"  conflict_length_m: {act.get('conflict_length_m', 'N/A')} (expected {exp.get('conflict_length_m', 'N/A')})")

