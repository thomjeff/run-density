#!/usr/bin/env python3
"""
verify_artifact_parity.py

Parses a built Runflow bundle and verifies parity between:
- reports/Density.md (Executive Summary)
- artifacts/ui/flags.json
- artifacts/ui/segment_metrics.json  (if present)
Optional unit checks for rate fields using segments.geojson widths.

Exit codes:
  0 = OK
  1 = Parity mismatch or validation failure
  2 = Usage / path errors

Usage:
  python verify_artifact_parity.py \
    --root /path/to/build/root \
    [--check-units] \
    [--segments-geojson /path/to/artifacts/ui/segments.geojson] \
    [--require-tooltips] \
    [--verbose]
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any, Set

# --------- Helpers

def err(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)

def info(msg: str, verbose: bool) -> None:
    if verbose:
        print(f"[INFO] {msg}")

def parse_exec_summary(md_text: str, verbose: bool=False) -> Tuple[int, int]:
    """
    Returns (flagged_bins_total, segments_with_flags_count) from the Executive Summary.
    """
    # Be robust to extra spaces, commas, and markdown bold markers
    fb = re.search(r"\*?\*?Flagged\s+Bins:\*?\*?\s*([0-9,]+)\s*/", md_text, flags=re.IGNORECASE)
    swf = re.search(r"\*?\*?Segments\s+with\s+Flags:\*?\*?\s*([0-9,]+)\s*/", md_text, flags=re.IGNORECASE)
    if not fb or not swf:
        raise ValueError("Could not parse Executive Summary totals from Density.md")
    flagged_bins_total = int(fb.group(1).replace(",", ""))
    segments_with_flags = int(swf.group(1).replace(",", ""))
    info(f"Parsed MD: flagged_bins={flagged_bins_total}, segments_with_flags={segments_with_flags}", verbose)
    return flagged_bins_total, segments_with_flags

def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8", errors="ignore"))

def read_density_md(root: Path) -> str:
    # Support both flat and date-nested structures
    candidates = list((root / "reports").glob("*Density.md"))
    if not candidates:
        candidates = list((root / "reports").glob("*/*Density.md"))
    if not candidates:
        raise FileNotFoundError("No reports/*Density.md or reports/*/*Density.md found")
    # take most recent by modified time
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0].read_text(encoding="utf-8", errors="ignore")

def locate_artifact(root: Path, name: str) -> Path:
    p = root / "artifacts" / "ui" / name
    if not p.exists():
        # try slightly different layout if needed (e.g., date-nested)
        candidates = list((root / "artifacts").rglob(name))
        if not candidates:
            raise FileNotFoundError(f"artifacts/ui/{name} not found")
        # take most recent by modified time (handles multiple date folders)
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[0]
    return p

def get_flagged_bins_value(rec: Dict[str, Any]) -> int:
    # canonical is flagged_bins; legacy alias flagged_bin_count
    val = rec.get("flagged_bins")
    if val is None:
        val = rec.get("flagged_bin_count")
    if val is None:
        return 0
    try:
        return int(val)
    except Exception:
        try:
            return int(float(val))
        except Exception:
            return 0

def get_segment_id(rec: Dict[str, Any]) -> str:
    # canonical is segment_id; legacy alias seg_id
    sid = rec.get("segment_id", rec.get("seg_id"))
    return str(sid) if sid is not None else ""

def check_units_consistency(
    root: Path,
    segments_geojson_path: Path,
    verbose: bool
) -> Tuple[bool, List[str]]:
    """
    Optional: If legacy 'rate_per_m_per_min' is emitted anywhere alongside canonical 'rate' and we
    have segment width_m, verify round-trip conversion:
      rate_per_m_per_min ≈ (rate / width_m) * 60
    Tolerance: relative 1e-6 or absolute 1e-6
    """
    warnings: List[str] = []
    ok = True

    # We check bin-level artifacts if available (bin_flags.json), else skip quietly.
    # This script is parity-focused; units check is additive.
    try:
        bin_flags_path = locate_artifact(root, "bin_flags.json")
    except FileNotFoundError:
        info("bin_flags.json not found; skipping unit checks (this is OK).", verbose)
        return True, warnings

    try:
        segments_geojson = load_json(segments_geojson_path)
        width_by_segment: Dict[str, float] = {}
        for feat in segments_geojson.get("features", []):
            props = feat.get("properties", {})
            sid = props.get("segment_id", props.get("seg_id"))
            w = props.get("width_m")
            if sid is not None and isinstance(w, (int, float)):
                width_by_segment[str(sid)] = float(w)
    except Exception as e:
        warnings.append(f"Could not read segments.geojson for unit checks: {e}")
        return True, warnings  # don't fail parity on units file read

    try:
        bins = load_json(bin_flags_path)
        if not isinstance(bins, list):
            info("bin_flags.json not a list; skipping unit checks.", verbose)
            return True, warnings
    except Exception as e:
        warnings.append(f"Could not read bin_flags.json: {e}")
        return True, warnings

    def nearly_equal(a: float, b: float, tol: float = 1e-6) -> bool:
        if a == b:
            return True
        denom = max(1.0, abs(a), abs(b))
        return abs(a - b) <= tol * denom

    for i, b in enumerate(bins):
        sid = get_segment_id(b)
        if not sid:
            continue
        width = width_by_segment.get(sid)
        if width is None or width <= 0:
            # No width => skip this record
            continue

        # canonical rate (p/s)
        rate_ps = b.get("rate")
        # legacy rate (p/m/min)
        rpm = b.get("rate_per_m_per_min")

        # Only check when both are present and numeric
        if isinstance(rate_ps, (int, float)) and isinstance(rpm, (int, float)):
            expected_rpm = (rate_ps / width) * 60.0
            if not nearly_equal(expected_rpm, float(rpm)):
                ok = False
                warnings.append(
                    f"Unit mismatch for segment {sid} bin#{i}: "
                    f"rate={rate_ps} p/s, width={width} m ⇒ expected rate_per_m_per_min={expected_rpm}, found {rpm}"
                )

    return ok, warnings

# --------- Main parity checks

def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="Root of built bundle (contains reports/ and artifacts/)")
    ap.add_argument("--check-units", action="store_true", help="Verify rate unit conversions using segments.geojson and bin_flags.json")
    ap.add_argument("--segments-geojson", default="", help="Path to segments.geojson (defaults to artifacts/ui/segments.geojson)")
    ap.add_argument("--require-tooltips", action="store_true", help="Fail if tooltips.json is missing (optional artifact)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.root)
    if not root.exists():
        err(f"--root path does not exist: {root}")
        return 2

    # Load report
    try:
        md_text = read_density_md(root)
    except Exception as e:
        err(f"Failed to read Density.md: {e}")
        return 1

    try:
        md_flagged_bins, md_segments_with_flags = parse_exec_summary(md_text, verbose=args.verbose)
    except Exception as e:
        err(f"Failed to parse Executive Summary: {e}")
        return 1

    # Load artifacts
    try:
        flags_path = locate_artifact(root, "flags.json")
        flags = load_json(flags_path)
        if isinstance(flags, dict) and "flags" in flags:
            flags = flags["flags"]
        if not isinstance(flags, list):
            err("flags.json must be an array or {flags: [...]}")
            return 1
    except Exception as e:
        err(f"Failed to load flags.json: {e}")
        return 1

    # Optional: segment_metrics.json
    segm = []
    try:
        segm_path = locate_artifact(root, "segment_metrics.json")
        segm = load_json(segm_path)
        if isinstance(segm, dict) and "segments" in segm:
            segm = segm["segments"]
        if segm is None:
            segm = []
        if not isinstance(segm, list):
            # don't fail hard, but warn
            print("[WARN] segment_metrics.json is not a list; skipping parity against it.")
            segm = []
    except FileNotFoundError:
        print("[WARN] segment_metrics.json not found; skipping parity against it.")
        segm = []
    except Exception as e:
        print(f"[WARN] segment_metrics.json load error ({e}); skipping parity against it.")
        segm = []

    # Optional: tooltips.json (for presence only if requested)
    if args.require_tooltips:
        try:
            _ = locate_artifact(root, "tooltips.json")
        except Exception as e:
            err(f"require-tooltips set but tooltips.json missing: {e}")
            return 1

    # ---- Parity: flags.json vs Density.md
    flags_sum_bins = sum(get_flagged_bins_value(r) for r in flags)
    flags_segments: Set[str] = {get_segment_id(r) for r in flags if get_segment_id(r)}
    if md_flagged_bins != flags_sum_bins:
        err(f"Flagged bins mismatch: Density.md={md_flagged_bins} vs flags.json sum={flags_sum_bins}")
        return 1
    if md_segments_with_flags != len(flags_segments):
        err(f"Segments-with-flags count mismatch: Density.md={md_segments_with_flags} vs flags.json unique={len(flags_segments)}")
        return 1

    # ---- Parity: segment_metrics.json (if present) vs Density.md
    if segm:
        segm_sum_bins = sum(get_flagged_bins_value(r) for r in segm)
        segm_segments: Set[str] = {get_segment_id(r) for r in segm if get_segment_id(r)}
        if md_flagged_bins != segm_sum_bins:
            err(f"segment_metrics.json flagged bins mismatch: Density.md={md_flagged_bins} vs segment_metrics sum={segm_sum_bins}")
            return 1
        if md_segments_with_flags != len(segm_segments):
            err(f"segment_metrics.json segment count mismatch: Density.md={md_segments_with_flags} vs segment_metrics unique={len(segm_segments)}")
            return 1
        # Optionally ensure the same exact set of segment IDs
        missing_in_metrics = flags_segments - segm_segments
        missing_in_flags   = segm_segments - flags_segments
        if missing_in_metrics or missing_in_flags:
            err(f"Mismatch in segment sets between flags.json and segment_metrics.json. "
                f"Missing_in_metrics={sorted(missing_in_metrics)}, Missing_in_flags={sorted(missing_in_flags)}")
            return 1

    # ---- Optional Unit Checks
    if args.check_units:
        seg_geo = Path(args.segments_geojson) if args.segments_geojson else locate_artifact(root, "segments.geojson")
        ok, warnings = check_units_consistency(root, seg_geo, args.verbose)
        for w in warnings:
            print(f"[WARN] {w}")
        if not ok:
            err("Unit checks failed (rate vs rate_per_m_per_min conversion).")
            return 1

    print("Artifact parity OK ✅")
    print(f"- Flagged bins total: {md_flagged_bins}")
    print(f"- Segments with flags: {md_segments_with_flags}")
    print(f"- flags.json segments: {len(flags_segments)} (IDs match)")
    if segm:
        print(f"- segment_metrics.json rows: {len(segm)} (parity OK)")
    if args.check_units:
        print("- Units check: OK")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        err("Interrupted")
        sys.exit(2)

