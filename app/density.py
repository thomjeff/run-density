# app/density.py

from typing import Optional, List, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
import csv, io, requests

router = APIRouter()

# ---------- Models ----------
class SegmentIn(BaseModel):
    # seg_id is OPTIONAL for inline payloads; we will synthesize one if missing
    seg_id: Optional[str] = None
    segment_label: Optional[str] = None
    eventA: str
    eventB: str
    from_km_A: Optional[float] = None
    to_km_A:   Optional[float] = None
    from_km_B: Optional[float] = None
    to_km_B:   Optional[float] = None
    # legacy inline fields (for simple pair) – still accepted but we won’t document them
    from_: Optional[float] = None
    to:    Optional[float] = None
    direction: str
    width: Optional[float] = None
    width_m: Optional[float] = None

class DensityRequest(BaseModel):
    paceCsv: HttpUrl
    overlapsCsv: Optional[HttpUrl] = None  # if present, we ignore `segments` entirely
    startTimes: Dict[str, int]  # {"Full":420,"10K":440,"Half":460}
    stepKm: float = 0.03
    timeWindow: int = 60
    segments: Optional[List[SegmentIn]] = None

# internal normalized segment
class Segment(BaseModel):
    seg_id: str
    segment_label: str
    eventA: str
    eventB: str
    from_km_A: float
    to_km_A: float
    from_km_B: float
    to_km_B: float
    direction: str
    width_m: float

# ---------- Helpers ----------
def _csv_to_rows(url: str) -> List[dict]:
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to fetch {url}: {e}")
    # strip BOM if present
    text = r.text.lstrip("\ufeff")
    buf = io.StringIO(text)
    reader = csv.DictReader(buf)
    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=422, detail=f"{url} parsed but contained no rows")
    return rows

REQUIRED_HEADERS = [
    "seg_id","segment_label",
    "eventA","eventB",
    "from_km_A","to_km_A",
    "from_km_B","to_km_B",
    "direction","width_m",
]

def _normalize_overlaps_csv(url: str) -> List[Segment]:
    rows = _csv_to_rows(url)
    # header validation
    headers = {h.strip() for h in rows[0].keys()}
    missing = [h for h in REQUIRED_HEADERS if h not in headers]
    if missing:
        raise HTTPException(status_code=422, detail=f"overlaps.csv missing headers: {missing}")
    out: List[Segment] = []
    for raw in rows:
        try:
            seg = Segment(
                seg_id=(raw.get("seg_id") or "").strip(),
                segment_label=(raw.get("segment_label") or "").strip() or (raw.get("seg_id") or "").strip(),
                eventA=raw["eventA"].strip(),
                eventB=raw["eventB"].strip(),
                from_km_A=float(raw["from_km_A"]),
                to_km_A=float(raw["to_km_A"]),
                from_km_B=float(raw["from_km_B"]),
                to_km_B=float(raw["to_km_B"]),
                direction=raw["direction"].strip(),
                width_m=float(raw["width_m"]),
            )
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"overlaps.csv bad row for seg_id={raw.get('seg_id')}: {e}")
        if not seg.seg_id:
            raise HTTPException(status_code=422, detail="overlaps.csv has row with empty seg_id")
        out.append(seg)
    return out

def _normalize_inline_segments(items: List[SegmentIn]) -> List[Segment]:
    out: List[Segment] = []
    for s in items:
        # prefer explicit A/B km fields; fall back to simple from/to if provided
        from_km_A = s.from_km_A if s.from_km_A is not None else s.from_
        to_km_A   = s.to_km_A   if s.to_km_A   is not None else s.to
        from_km_B = s.from_km_B if s.from_km_B is not None else s.from_
        to_km_B   = s.to_km_B   if s.to_km_B   is not None else s.to

        if None in (from_km_A, to_km_A, from_km_B, to_km_B):
            raise HTTPException(status_code=422, detail="Inline segment must include km spans (from/to).")

        width_m = s.width_m if s.width_m is not None else (s.width if s.width is not None else 3.0)

        seg_id = s.seg_id or f"{s.eventA}-{s.eventB}-{from_km_A:.2f}-{to_km_A:.2f}"
        segment_label = s.segment_label or seg_id

        out.append(Segment(
            seg_id=seg_id,
            segment_label=segment_label,
            eventA=s.eventA, eventB=s.eventB,
            from_km_A=float(from_km_A), to_km_A=float(to_km_A),
            from_km_B=float(from_km_B), to_km_B=float(to_km_B),
            direction=s.direction, width_m=float(width_m),
        ))
    return out

# ---------- Route ----------
@router.post("/api/density")
def density(req: DensityRequest):
    # load overlaps from CSV or from inline
    if req.overlapsCsv:
        segments = _normalize_overlaps_csv(str(req.overlapsCsv))
    else:
        if not req.segments:
            raise HTTPException(status_code=422, detail="Either overlapsCsv or non-empty segments[] is required.")
        segments = _normalize_inline_segments(req.segments)

    # TODO: call your existing computation using:
    #  - req.paceCsv
    #  - req.startTimes
    #  - segments (normalized list of Segment)
    #
    # For now, return a tiny stub proving the normalization works
    return {
        "engine": "density",
        "segments": [
            {"seg_id": s.seg_id, "segment_label": s.segment_label, "peak": {"combined": 123}}
            for s in segments[:1]
        ]
    }