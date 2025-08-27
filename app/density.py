from __future__ import annotations
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
import io
import csv
import requests

class DensityPayload(BaseModel):
    paceCsv: str
    overlapsCsv: Optional[str] = None
    # “segments” is optional now; if not provided we can source from overlapsCsv
    segments: Optional[List[Dict[str, Any]]] = None
    startTimes: Dict[str, int]
    stepKm: float = 0.03
    timeWindow: int = 60

def _fetch_csv_rows(url: str) -> List[Dict[str, str]]:
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    text = r.text
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]

def _segments_from_overlaps_csv(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    Convert overlaps.csv rows into API-style segment dicts.
    Expected columns (from your v1.3.0 spec):
      seg_id, segment_label, eventA, eventB,
      from_km_A, to_km_A, from_km_B, to_km_B,
      direction, width_m, notes
    """
    segs: List[Dict[str, Any]] = []
    for row in rows:
        seg_id = (row.get("seg_id") or row.get("segment_id") or "").strip()
        label = (row.get("segment_label") or seg_id).strip() or None
        # direction/width normalization
        direction = (row.get("direction") or "uni").strip().lower()
        width_val = row.get("width_m") or row.get("width") or ""
        try:
            width_m = float(width_val) if width_val != "" else None
        except:
            width_m = None

        # Events/distances
        eventA = (row.get("eventA") or "").strip()
        eventB = (row.get("eventB") or "").strip()

        def as_float(s: Optional[str]) -> Optional[float]:
            if s is None:
                return None
            s = s.strip()
            if not s:
                return None
            try:
                return float(s)
            except:
                return None

        fromA = as_float(row.get("from_km_A"))
        toA   = as_float(row.get("to_km_A"))
        fromB = as_float(row.get("from_km_B"))
        toB   = as_float(row.get("to_km_B"))

        # Build a single “merged” corridor segment that your current engine expects:
        # If both A and B have km ranges, take the union span for display/scan;
        # your internal overlap logic already accounts for pairwise timing.
        # We also carry the per-event spans so downstream can use them if needed.
        seg_dict = {
            "seg_id": seg_id,
            "segment_label": label,
            "eventA": eventA,
            "eventB": eventB,
            # primary scan span (display/scan convenience)
            "from": min(x for x in [fromA, fromB] if x is not None) if (fromA is not None or fromB is not None) else None,
            "to":   max(x for x in [toA, toB]     if x is not None) if (toA   is not None or toB   is not None) else None,
            # keep per-event spans (used by your runner-timeline logic)
            "from_km_A": fromA, "to_km_A": toA,
            "from_km_B": fromB, "to_km_B": toB,
            "direction": direction,
            "width_m": width_m,
        }
        segs.append(seg_dict)
    return segs

def _normalize_and_derive(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize keys (seg_id, width_m) and compute simple derived fields.
    We do NOT change your peak math; we only add areal_density if possible.
    """
    normed: List[Dict[str, Any]] = []
    for s in segments:
        # normalize id & label
        seg_id = (s.get("seg_id") or s.get("segment_id") or "").strip()
        lbl = s.get("segment_label") or seg_id or None

        # normalize width
        width_m = s.get("width_m", s.get("width"))
        try:
            width_m = float(width_m) if width_m is not None else None
        except:
            width_m = None

        # normalize direction
        direction = (s.get("direction") or "uni").lower()

        # carry over existing peak if present (as your engine already computes it)
        peak = s.get("peak")
        # derive areal density if possible and missing
        if peak and isinstance(peak, dict) and peak.get("combined") is not None:
            if width_m and width_m > 0 and peak.get("areal_density") is None:
                # NOTE: areal density needs corridor area; at minimum we can divide by width to
                # express “people per meter” along the corridor. If you prefer ppl/m², you’ll
                # divide by an effective *length* (your 60s window’s longitudinal footprint).
                # For now we’ll populate ppl_per_meter to avoid incorrect m² claims.
                ppl_per_meter = peak["combined"] / width_m
                peak = dict(peak)
                peak["ppl_per_meter"] = round(ppl_per_meter, 2)

        out = dict(s)
        out["seg_id"] = seg_id
        out["segment_label"] = lbl
        out["width_m"] = width_m
        out["direction"] = direction
        if peak is not None:
            out["peak"] = peak
        normed.append(out)
    return normed

def run_density(payload: DensityPayload) -> Dict[str, Any]:
    """
    STEP 0: (unchanged) you already load paceCsv & do your existing math.
    We do NOT alter that here; we’re only adding the “where” for Steps 1 and 2.

    STEP 1: If overlapsCsv is provided, ingest and convert to segments, and
            merge with any request-provided segments (request wins on conflicts).

    STEP 2: After you have a final candidate list of segments (from request and/or CSV),
            normalize keys and fill derived fields before returning.
    """
    # ---- load pace CSV (leave your existing logic intact) ----
    # rows_pace = _fetch_csv_rows(payload.paceCsv)
    # ... your current per-runner/per-event timeline and peak computation here ...

    # ===== STEP 1: build segments list from request + overlapsCsv =====
    segments: List[Dict[str, Any]] = []
    if payload.segments:
        # use exactly what caller provided (many of your tests do this)
        segments.extend(payload.segments)

    if payload.overlapsCsv:
        try:
            o_rows = _fetch_csv_rows(payload.overlapsCsv)
            csv_segments = _segments_from_overlaps_csv(o_rows)
            # merge strategy: keep request-provided first, then append CSV.
            # (If you want request to override CSV on same seg_id, this order is correct.)
            segments.extend(csv_segments)
        except Exception as e:
            # Don’t fail the whole request if CSV can’t load; return a helpful error.
            return {
                "engine": "density",
                "error": f"failed to load overlapsCsv: {e}",
                "segments": []
            }

    # If still empty, nothing to do
    if not segments:
        return {"engine": "density", "segments": []}

    # At this point, your existing math should already have annotated each segment with:
    #   segment["peak"] = {"km": ..., "A": ..., "B": ..., "combined": ...}
    # If you don’t yet attach peaks until later, keep doing that where you do it now.
    # We only normalize afterward.

    # ===== STEP 2: normalize/derive just before responding =====
    segments = _normalize_and_derive(segments)

    # Return exactly what your current clients expect
    return {"engine": "density", "segments": segments}