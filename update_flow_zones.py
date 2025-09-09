#!/usr/bin/env python3
"""
Update flow_zone values in segments_new.csv based on the diff file
"""

import pandas as pd

# Load the segments file
segments_df = pd.read_csv('data/segments_new.csv')

# Load the flow_zone diff file
flow_zone_df = pd.read_csv('segments_new.flow_zone.diff.csv')

# Create a mapping from seg_id to flow_zone
flow_zone_map = dict(zip(flow_zone_df['seg_id'], flow_zone_df['flow_zone']))

# Update the flow_zone column
segments_df['flow_zone'] = segments_df['seg_id'].map(flow_zone_map).fillna(segments_df['flow_zone'])

# For segments not in the diff file, use the existing flow_type as fallback
segments_df['flow_zone'] = segments_df['flow_zone'].fillna(segments_df['flow_type'])

# Save the updated file
segments_df.to_csv('data/segments_new.csv', index=False)

print("Updated segments_new.csv with flow_zone values")
print(f"Flow zones updated: {len(flow_zone_map)} segments")
print(f"Total segments: {len(segments_df)}")
