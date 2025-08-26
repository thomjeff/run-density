#!/usr/bin/env python3
"""
Validator for overlaps_v2.csv

Checks for:
- required columns
- ascending from_km/to_km
- allowed event names
- allowed direction
- distance plausibility
- gaps/overlaps within same seg_id + event
"""

import sys
import pandas as pd

REQUIRED_COLS = [
    "seg_id","segment_label","eventA","eventB",
    "from_km_A","to_km_A","from_km_B","to_km_B",
    "direction","width_m","notes"
]
ALLOWED_EVENTS = {"10K","Half","Full"}
ALLOWED_DIRS = {"uni","bi"}
DIST_LIMITS = {"10K":10.2,"Half":21.2,"Full":42.4}

def main(path):
    df = pd.read_csv(path)
    errors, warnings = [], []

    # Columns
    for c in REQUIRED_COLS:
        if c not in df.columns:
            errors.append(f"Missing column: {c}")

    # Row-wise checks
    for i,row in df.iterrows():
        sid = row["seg_id"]
        eA,eB = row["eventA"],row["eventB"]
        fA,tA,fB,tB = row["from_km_A"],row["to_km_A"],row["from_km_B"],row["to_km_B"]

        # event validity
        for ev in (eA,eB):
            if ev not in ALLOWED_EVENTS:
                errors.append(f"{sid}: invalid event {ev}")

        # ascending
        if fA > tA: errors.append(f"{sid}: eventA from>to ({fA}>{tA})")
        if fB > tB: errors.append(f"{sid}: eventB from>to ({fB}>{tB})")

        # direction
        if row["direction"] not in ALLOWED_DIRS:
            errors.append(f"{sid}: invalid direction {row['direction']}")

        # width
        if row["width_m"] <= 0:
            errors.append(f"{sid}: non-positive width {row['width_m']}")

        # plausibility
        for ev,dist in [(eA,tA),(eB,tB)]:
            if ev in DIST_LIMITS and dist > DIST_LIMITS[ev]+0.5:
                warnings.append(f"{sid}: {ev} distance {dist} > plausible {DIST_LIMITS[ev]}")

    # Gaps within same segment/event
    for ev in ALLOWED_EVENTS:
        for side in ("A","B"):
            col_from,col_to = f"from_km_{side}",f"to_km_{side}"
            segs = df[df[f"event{side}"]==ev].sort_values([ "seg_id", col_from ])
            for sid,group in segs.groupby("seg_id"):
                prev = None
                for _,row in group.iterrows():
                    if prev is not None and row[col_from] > prev:
                        gap = row[col_from]-prev
                        if gap > 0.01:
                            warnings.append(f"{sid}: gap {gap:.2f}km for {ev} side {side}")
                    prev = row[col_to]

    # Output
    if errors: print("ERRORS:"); [print("  -",e) for e in errors]
    if warnings: print("WARNINGS:"); [print("  -",w) for w in warnings]

    if errors: sys.exit(1)

if __name__=="__main__":
    if len(sys.argv)!=2:
        print("Usage: validate_overlaps.py overlaps_v2.csv"); sys.exit(2)
    main(sys.argv[1])