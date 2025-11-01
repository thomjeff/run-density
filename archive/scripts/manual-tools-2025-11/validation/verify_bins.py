#!/usr/bin/env python3
"""
verify_bins.py — Validate local bin artifacts by content, not just presence.

Usage:
  python verify_bins.py --reports-dir ./reports --strict
"""
import argparse, os, sys, gzip, json, re, glob
from datetime import datetime
from pathlib import Path

REQUIRED_PROPS = ["bin_id","segment_id","start_km","end_km","t_start","t_end","density","rate","los_class","bin_size_km"]

def find_latest_daily_dir(reports_dir: Path) -> Path:
    if not reports_dir.exists():
        raise FileNotFoundError(f"reports dir not found: {reports_dir}")
    dated = []
    for p in reports_dir.iterdir():
        if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name):
            dated.append(p)
    if not dated:
        raise FileNotFoundError(f"No YYYY-MM-DD folders under {reports_dir}")
    # max by folder name (lex order works for ISO dates)
    return sorted(dated)[-1]

def load_geojson_gz(path: Path):
    with gzip.open(path, "rb") as f:
        return json.loads(f.read().decode("utf-8"))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports-dir", default="./reports", help="Path to /reports root")
    ap.add_argument("--strict", action="store_true", help="Exit non-zero on any failure")
    args = ap.parse_args()

    reports_root = Path(args.reports_dir).resolve()
    try:
        daydir = find_latest_daily_dir(reports_root)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1 if args.strict else 0

    # Find artifacts (first match in the day folder)
    gj = None
    pq = None
    for cand in ["bins.geojson.gz"] + [p.name for p in daydir.glob("*.geojson.gz")]:
        p = daydir / cand
        if p.exists():
            gj = p; break
    for cand in ["bins.parquet"] + [p.name for p in daydir.glob("*.parquet")]:
        p = daydir / cand
        if p.exists():
            pq = p; break

    if gj is None or pq is None:
        print(f"ERROR: Missing artifacts in {daydir} "
              f"(geojson={bool(gj)} parquet={bool(pq)})", file=sys.stderr)
        return 1 if args.strict else 0

    # GeoJSON checks
    try:
        fc = load_geojson_gz(gj)
    except Exception as e:
        print(f"ERROR: Failed to read {gj}: {e}", file=sys.stderr)
        return 1

    feats = fc.get("features") or []
    md = fc.get("metadata") or {}
    occ = int(md.get("occupied_bins", 0) or 0)
    nz  = int(md.get("nonzero_density_bins", 0) or 0)
    tot = int(md.get("total_features", len(feats)) or len(feats))

    if tot <= 0 or occ <= 0 or nz <= 0:
        print(f"ERROR: Empty occupancy in {gj.name}: total={tot} occupied={occ} nonzero={nz}", file=sys.stderr)
        return 1

    # Property sanity
    props = feats[0].get("properties") or {}
    missing = [k for k in REQUIRED_PROPS if k not in props]
    if missing:
        print(f"ERROR: Missing properties on first feature: {missing}", file=sys.stderr)
        return 1

    # Parquet checks
    try:
        import pyarrow.parquet as pq_mod
        table = pq_mod.read_table(pq)
        if table.num_rows != len(feats):
            print(f"ERROR: Parquet rows ({table.num_rows}) != GeoJSON features ({len(feats)})", file=sys.stderr)
            return 1
    except ModuleNotFoundError:
        print("WARN: pyarrow not installed; skipping Parquet validation.", file=sys.stderr)
    except Exception as e:
        print(f"ERROR: Failed to read Parquet {pq}: {e}", file=sys.stderr)
        return 1

    # Pretty print a small summary (sizes may vary)
    try:
        gz_size_kb = gj.stat().st_size / 1024.0
        pq_size_kb = pq.stat().st_size / 1024.0
    except Exception:
        gz_size_kb = pq_size_kb = -1

    sample = {k: props.get(k) for k in ["bin_id","t_start","density","flow","los_class","bin_size_km"] if k in props}
    print(f"OK  bins: features={len(feats)} occupied={occ} nonzero={nz} "
          f"gz={gz_size_kb:.1f}KB parquet={pq_size_kb:.1f}KB")
    print("sample:", sample)
    return 0

if __name__ == "__main__":
    sys.exit(main())
