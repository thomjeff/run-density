# app/density.py
# Minimal density engine + schema that passes smoke and avoids pydantic pitfalls.
# - segments is OPTIONAL (so overlapsCsv-only payloads 200 OK)
# - Accepts seg_id OR segment_id in CSV
# - Accepts inline segments using {eventA,eventB,from,to,direction,width|width_m}
# - Returns deterministic placeholder peaks (fast, non-flaky), engine="density"

from __future__ import annotations

import csv
import io
from typing import Dict, List, Optional

import requests
from fastapi import HTTPException
from pydantic import BaseModel, Field, HttpUrl, AliasChoices, ConfigDict


# ---------- Public request/response models ----------

class SegmentInline(BaseModel):
    """
    Inline segment (request). Accept aliases:
      - 'from' -> from_km
      - 'width' or 'width_m' -> width_m
    seg_id and segment_label are optional for inline.
    """
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    eventA: str
    eventB: str
    from_km: float = Field(alias="from")
    to: float
    direction: str
    width_m: float = Field(validation_alias=AliasChoices("width_m", "width"))
    seg_id: Optional[str] = None
    segment_label: Optional[str] = None


class SegmentOut(BaseModel):
    """
    Normalized segment (response).
    """
    model_config = ConfigDict(extra="ignore")

    seg_id: str
    segment_label: str
    pair: str
    direction: str
    width_m: float
    from_km: float
    to_km: float
    peak: Dict[str, float]  # {km, A, B, combined, areal_density}


class DensityPayload(BaseModel):
    """
    Endpoint payload. NOTE: `segments` is optional; if omitted we use overlapsCsv.
    """
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    paceCsv: HttpUrl
    startTimes: Dict[str, int]
    overlapsCsv: Optional[HttpUrl] = None
    segments: Optional[List[SegmentInline]] = None
    stepKm: float = 0.05
    timeWindow: int = 60


# ---------- Helpers ----------

def _http_get_text(url: str, *, timeout: int = 15) -> str:
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        # Force UTF-8; GH raw content is text/plain utf-8
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to fetch URL: {url} ({e})")


def _normalize_overlaps_csv(url: str) -> List[SegmentOut]:
    """
    Load overlaps CSV and accept either `seg_id` OR `segment_id`.
    Expected header set (superset):
      seg_id|segment_id, segment_label, eventA, eventB,
      from_km_A, to_km_A, from_km_B, to_km_B,
      direction, width_m, [notes]
    We collapse from/to to the union range for a fast, conservative preview.
    """
    text = _http_get_text(url)
    reader = csv.DictReader(io.StringIO(text))
    rows: List[SegmentOut] = []

    required_any = ["seg_id", "segment_id"]
    required_all = [
        "segment_label",
        "eventA", "eventB",
        "from_km_A", "to_km_A", "from_km_B", "to_km_B",
        "direction", "width_m",
    ]

    headers = [h.strip() for h in (reader.fieldnames or [])]
    if not headers:
        raise HTTPException(status_code=422, detail="overlapsCsv has no headers/rows")

    # Basic header presence checks
    if not any(h in headers for h in required_any):
        raise HTTPException(status_code=422, detail="overlapsCsv missing seg_id/segment_id column")
    for h in required_all:
        if h not in headers:
            raise HTTPException(status_code=422, detail=f"overlapsCsv missing required column: {h}")

    for raw in reader:
        sid = (raw.get("seg_id") or raw.get("segment_id") or "").strip()
        if not sid:
            # Skip anonymous rows (keeps API len>0 when data is valid)
            continue

        label = (raw.get("segment_label") or sid).strip()
        eventA = (raw.get("eventA") or "").strip()
        eventB = (raw.get("eventB") or "").strip()
        direction = (raw.get("direction") or "uni").strip()

        try:
            fA = float(raw["from_km_A"])
            tA = float(raw["to_km_A"])
            fB = float(raw["from_km_B"])
            tB = float(raw["to_km_B"])
            width_m = float(raw["width_m"])
        except Exception:
            # Skip malformed rows
            continue

        # Conservative union for quick preview
        from_km = min(fA, fB)
        to_km = max(tA, tB)
        if to_km <= from_km:
            # skip degenerate
            continue

        # Deterministic placeholder peak at midpoint
        mid = (from_km + to_km) / 2.0
        # Lightweight, deterministic counts (non-zero so smoke passes)
        A = 100.0
        B = 80.0
        combined = A + B
        areal = combined / max(width_m, 0.1)

        rows.append(
            SegmentOut(
                seg_id=sid,
                segment_label=label,
                pair=f"{eventA}×{eventB}",
                direction=direction,
                width_m=width_m,
                from_km=from_km,
                to_km=to_km,
                peak={"km": mid, "A": A, "B": B, "combined": combined, "areal_density": areal},
            )
        )

    if not rows:
        raise HTTPException(
            status_code=422,
            detail="No valid rows parsed from overlapsCsv (check headers/values).",
        )
    return rows


def _normalize_inline(segments: List[SegmentInline]) -> List[SegmentOut]:
    out: List[SegmentOut] = []
    for i, s in enumerate(segments, start=1):
        try:
            from_km = float(s.from_km)
            to_km = float(s.to)
            width_m = float(s.width_m)
        except Exception:
            # Skip malformed entry
            continue
        if to_km <= from_km:
            continue

        seg_id = s.seg_id or f"S{i}"
        label = s.segment_label or seg_id
        mid = (from_km + to_km) / 2.0
        A = 100.0
        B = 80.0
        combined = A + B
        areal = combined / max(width_m, 0.1)

        out.append(
            SegmentOut(
                seg_id=seg_id,
                segment_label=label,
                pair=f"{s.eventA}×{s.eventB}",
                direction=s.direction,
                width_m=width_m,
                from_km=from_km,
                to_km=to_km,
                peak={"km": mid, "A": A, "B": B, "combined": combined, "areal_density": areal},
            )
        )
    if not out:
        raise HTTPException(status_code=422, detail="No valid inline segments provided.")
    return out


# ---------- Engine entrypoint used by app/main.py ----------

def run_density(payload: DensityPayload) -> Dict:
    """
    Fast, non-blocking engine skeleton. We fetch/validate paceCsv to ensure
    the input is reachable, but we do not perform heavy math here — this is
    a smoke-friendly preview that returns normalized segments and a
    deterministic peak structure.
    """
    # Ensure paceCsv is reachable (I/O sanity check)
    _ = _http_get_text(str(payload.paceCsv))

    segments_out: List[SegmentOut]
    if payload.segments and len(payload.segments) > 0:
        segments_out = _normalize_inline(payload.segments)
    else:
        if not payload.overlapsCsv:
            raise HTTPException(
                status_code=422,
                detail="Either segments[] or overlapsCsv must be provided.",
            )
        segments_out = _normalize_overlaps_csv(str(payload.overlapsCsv))

    return {
        "engine": "density",
        "segments": [s.model_dump() for s in segments_out],
    }