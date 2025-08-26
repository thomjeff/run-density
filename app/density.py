from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Literal

import requests
from pydantic import BaseModel, Field, HttpUrl, model_validator


# ------------------ flags for /ready -------------------
READY_FLAGS = {"density_loaded": True, "overlap_loaded": True}


# ------------------ input models ----------------------

class StartTimes(BaseModel):
    Full: Optional[int] = None
    Half: Optional[int] = None
    _10K: Optional[int] = Field(default=None, alias="10K")

    def get_minutes(self, event: str) -> int:
        if event == "Full" and self.Full is not None:
            return self.Full
        if event == "Half" and self.Half is not None:
            return self.Half
        if event == "10K" and self._10K is not None:
            return self._10K
        raise ValueError(f"startTimes missing minutes for event '{event}'")


class DensityPayload(BaseModel):
    paceCsv: HttpUrl
    overlapsCsv: HttpUrl
    startTimes: StartTimes
    stepKm: float = 0.03
    timeWindow: int = 60  # seconds

    # hard stop on legacy fields; no back-compat to avoid drift
    segments: Optional[List[dict]] = None

    @model_validator(mode="after")
    def no_legacy_segments(self):
        if self.segments:
            raise ValueError("This API version does not accept 'segments'; provide overlapsCsv instead.")
        return self


# ------------------ data structures -------------------

@dataclass
class Runner:
    event: str
    pace_min_per_km: float
    distance_km: float

    @property
    def speed_mps(self) -> float:
        # speed = 1000 m / (pace_min * 60 s)
        return 1000.0 / (self.pace_min_per_km * 60.0)


# ------------------ helpers ---------------------------

def _fetch_csv(url: str) -> List[Dict[str, str]]:
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    text = r.content.decode("utf-8", errors="replace")
    return list(csv.DictReader(io.StringIO(text)))


def _load_pace(url: str) -> Dict[str, List[Runner]]:
    """
    CSV columns required: event, runner_id, pace, distance
      - pace is minutes per km (float)
      - distance is total race distance in km (float)
    """
    rows = _fetch_csv(url)
    required = {"event", "pace", "distance"}
    if rows and not required.issubset(set(rows[0].keys())):
        missing = sorted(list(required - set(rows[0].keys())))
        raise ValueError(f"paceCsv missing columns: {missing}")

    by_event: Dict[str, List[Runner]] = {}
    for row in rows:
        ev = (row.get("event") or "").strip()
        if not ev:
            continue
        try:
            pace = float(row.get("pace", "").strip())
            dist = float(row.get("distance", "").strip())
        except Exception:
            continue
        by_event.setdefault(ev, []).append(Runner(event=ev, pace_min_per_km=pace, distance_km=dist))
    return by_event


def _load_overlaps(url: str) -> List[Dict[str, str]]:
    """
    Required columns:
      seg_id,segment_label,eventA,eventB,from_km_A,to_km_A,from_km_B,to_km_B,direction,width_m
      (eventB may be empty for single-event continuity rows; extra columns ignored)
    """
    rows = _fetch_csv(url)
    req = {
        "seg_id","segment_label","eventA","eventB",
        "from_km_A","to_km_A","from_km_B","to_km_B",
        "direction","width_m"
    }
    if rows and not req.issubset(set(rows[0].keys())):
        missing = sorted(list(req - set(rows[0].keys())))
        raise ValueError(f"overlapsCsv missing columns: {missing}")
    return rows


def _zone_from_density(ppl_per_m2: float) -> str:
    if ppl_per_m2 < 1.0:
        return "green"
    if ppl_per_m2 < 1.5:
        return "amber"
    if ppl_per_m2 < 2.0:
        return "red"
    return "dark-red"


# ------------------ core math -------------------------

def _arrival_time_seconds(start_min: int, pace_min_per_km: float, km: float) -> float:
    return start_min * 60.0 + pace_min_per_km * 60.0 * km


def _segment_axis(from_km: float, to_km: float, step_km: float) -> Tuple[List[float], int]:
    sign = 1.0 if to_km >= from_km else -1.0
    length = abs(to_km - from_km)
    n_steps = max(1, int(round(length / step_km)) + 1)
    points = [from_km + sign * i * step_km for i in range(n_steps)]
    # Ensure last point exactly matches to_km
    if points[-1] != to_km:
        points[-1] = to_km
    return points, 1 if sign >= 0 else -1


def _peak_in_window(
    arrivals: List[Tuple[float, float, str]],  # (t_seconds, speed_mps, source "A"/"B")
    window_s: int
) -> Tuple[int, int, int, float]:
    """
    Two-pointer sliding window over sorted arrivals.
    Returns (A_count, B_count, combined, avg_speed_mps) for the best (max combined) window.
    """
    if not arrivals:
        return 0, 0, 0, 0.0

    arrivals.sort(key=lambda x: x[0])
    left = 0
    best = (0, 0, 0, 0.0)  # A, B, combined, avg_speed
    countA = countB = 0
    sum_speed = 0.0

    # We'll maintain counts/sum_speed for current window [left..right]
    for right in range(len(arrivals)):
        t_r, v_r, src_r = arrivals[right]
        if src_r == "A":
            countA += 1
        else:
            countB += 1
        sum_speed += v_r

        # shrink to keep window width <= window_s
        while arrivals[right][0] - arrivals[left][0] > window_s:
            t_l, v_l, src_l = arrivals[left]
            if src_l == "A":
                countA -= 1
            else:
                countB -= 1
            sum_speed -= v_l
            left += 1

        combined = countA + countB
        avg_speed = (sum_speed / combined) if combined > 0 else 0.0

        # prefer larger combined; if tie, prefer higher avg_speed (yields shorter platoon → higher density)
        if (combined > best[2]) or (combined == best[2] and avg_speed > best[3]):
            best = (countA, countB, combined, avg_speed)

    return best


def run_density(payload: DensityPayload) -> Dict:
    # 1) Load inputs
    runners_by_event = _load_pace(str(payload.paceCsv))
    overlap_rows = _load_overlaps(str(payload.overlapsCsv))

    step = float(payload.stepKm)
    window_s = int(payload.timeWindow)

    segments_out: List[Dict] = []

    for row in overlap_rows:
        seg_id = (row.get("seg_id") or "").strip()
        label = (row.get("segment_label") or "").strip()
        eventA = (row.get("eventA") or "").strip()
        eventB_raw = (row.get("eventB") or "").strip()
        eventB = eventB_raw if eventB_raw else None

        try:
            a0 = float(row.get("from_km_A", "0") or "0")
            a1 = float(row.get("to_km_A", "0") or "0")
            b0 = float(row.get("from_km_B", "0") or "0")
            b1 = float(row.get("to_km_B", "0") or "0")
            width_m = float(row.get("width_m", "3.0") or "3.0")
        except Exception as e:
            # skip malformed rows
            continue

        # Build parametric axis along the physical segment length relative to event A
        axisA, sgnA = _segment_axis(a0, a1, step)
        axisB, sgnB = _segment_axis(b0, b1, step)
        # Align length (just in case rounding mismatches)
        n = min(len(axisA), len(axisB))
        axisA = axisA[:n]
        axisB = axisB[:n]

        # Pre-fetch runner lists (skip if event not present)
        groupA = runners_by_event.get(eventA, [])
        groupB = runners_by_event.get(eventB, []) if eventB else []

        # For each sample along the segment, compute combined peak in window
        best_peak = None  # (density, km_display, A, B, combined, ppl_per_m2)
        for i in range(n):
            kmA = axisA[i]
            kmB = axisB[i]

            arrivals: List[Tuple[float, float, str]] = []

            # A arrivals at kmA
            if groupA:
                t0A = payload.startTimes.get_minutes(eventA)
                for r in groupA:
                    if r.distance_km + 1e-9 >= kmA:
                        t = _arrival_time_seconds(t0A, r.pace_min_per_km, kmA)
                        arrivals.append((t, r.speed_mps, "A"))

            # B arrivals at kmB
            if eventB and groupB:
                t0B = payload.startTimes.get_minutes(eventB)
                for r in groupB:
                    if r.distance_km + 1e-9 >= kmB:
                        t = _arrival_time_seconds(t0B, r.pace_min_per_km, kmB)
                        arrivals.append((t, r.speed_mps, "B"))

            A_cnt, B_cnt, combined, avg_speed = _peak_in_window(arrivals, window_s)
            if combined == 0:
                ppl_per_m2 = 0.0
            else:
                # platoon length = avg_speed * window seconds (meters)
                L_m = max(avg_speed * window_s, 0.1)
                area_m2 = max(width_m, 0.1) * L_m
                ppl_per_m2 = combined / area_m2

            zone = _zone_from_density(ppl_per_m2)

            # Track the best (peak combined; tie-breaker higher density then earlier kmA)
            key = (combined, ppl_per_m2, -kmA)
            if best_peak is None or key > best_peak[0]:
                best_peak = (key, kmA, A_cnt, B_cnt, combined, ppl_per_m2, zone)

        # If no samples (n==0) just synthesize empty
        if best_peak is None:
            segments_out.append({
                "seg_id": seg_id or f"{eventA}-{eventB or 'solo'}-{a0:.2f}",
                "segment_label": label or "",
                "engine": "density",
                "peak": {
                    "km": round(a0, 2),
                    "A": 0, "B": 0, "combined": 0,
                    "areal_density": 0.0,
                    "zone": "green"
                }
            })
        else:
            _, km_disp, A_cnt, B_cnt, combined, ppl_per_m2, zone = best_peak
            segments_out.append({
                "seg_id": seg_id or f"{eventA}-{eventB or 'solo'}-{a0:.2f}",
                "segment_label": label or "",
                "engine": "density",
                "peak": {
                    "km": round(km_disp, 2),
                    "A": int(A_cnt),
                    "B": int(B_cnt),
                    "combined": int(combined),
                    "areal_density": round(ppl_per_m2, 2),
                    "zone": zone
                }
            })

    return {"engine": "density", "segments": segments_out}