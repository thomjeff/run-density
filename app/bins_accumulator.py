# app/bins_accumulator.py
# Minimal, drop-in patch to produce real bin occupancy with vectorized accumulation.
# Dependencies: numpy (standard), typing (standard), datetime (standard)

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Iterable, Optional, Any
from datetime import datetime, timezone, timedelta
import math
import numpy as np
from app import rulebook

# -----------------------------
# Types and small configuration
# -----------------------------

@dataclass(frozen=True)
class SegmentInfo:
    segment_id: str
    length_m: float
    width_m: float                          # mean usable width for density (meters)
    coords: Optional[Any] = None            # whatever your Geo builder expects

@dataclass
class BinFeature:
    # Minimal property set needed downstream. Add extras as required.
    segment_id: str
    bin_index: int
    start_km: float
    end_km: float
    t_start: datetime
    t_end: datetime
    density: float                          # p / m^2
    rate: float                             # p / s (throughput rate) - renamed from 'flow' to avoid confusion with Flow analysis
    los_class: Optional[str]                # set by rulebook flagging (SSOT)
    bin_size_km: float

@dataclass
class BinBuildResult:
    features: List[BinFeature]
    metadata: Dict[str, Any]

# -----------------------------------
# Validation
# -----------------------------------

def _validate_positive_finite(value: float, name: str) -> None:
    if value is None or not np.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be positive and finite (got {value}).")

# ----------------------------------------------------
# Vectorized accumulation: one segment, one time window
# ----------------------------------------------------

def accumulate_window_for_segment(
    pos_m: np.ndarray,            # runner longitudinal position along segment [m]
    speed_mps: np.ndarray,        # runner speed [m/s] for the window
    seg: SegmentInfo,
    bin_len_m: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Vectorized per-window accumulation for a single segment.
    Returns:
        counts: int32 [nbins]
        sum_speed: float64 [nbins]
    """
    _validate_positive_finite(seg.length_m, "segment.length_m")
    _validate_positive_finite(seg.width_m, "segment.width_m")
    _validate_positive_finite(bin_len_m, "bin_len_m")

    nbins = int(math.ceil(seg.length_m / bin_len_m))
    if nbins <= 0:
        raise ValueError(f"Computed nbins={nbins} for segment {seg.segment_id}; check bin_len_m/length_m.")

    # Clamp / filter positions to [0, length_m)
    # (Optional) If your model can produce small negatives / slight overshoot, clip them:
    pos_m = np.clip(pos_m, 0.0, max(seg.length_m - 1e-6, 0.0))

    bin_idx = (pos_m // bin_len_m).astype(np.int32)
    # Safety: if pos == length_m (after clip), push into last bin
    bin_idx = np.minimum(bin_idx, nbins - 1)

    counts = np.zeros(nbins, dtype=np.int32)
    sum_speed = np.zeros(nbins, dtype=np.float64)

    # Vectorized scatter-add
    np.add.at(counts, bin_idx, 1)
    np.add.at(sum_speed, bin_idx, speed_mps)

    return counts, sum_speed

# -------------------------------------------------
# Build features for all segments & time windows
# -------------------------------------------------

def build_bin_features(
    *,
    segments: Dict[str, SegmentInfo],
    # time_windows: iterable of (t_start_datetime, t_end_datetime, window_index)
    time_windows: Iterable[Tuple[datetime, datetime, int]],
    # runners_by_segment_and_window:
    # dict[segment_id][window_index] = dict with 'pos_m' (np.ndarray), 'speed_mps' (np.ndarray)
    runners_by_segment_and_window: Dict[str, Dict[int, Dict[str, np.ndarray]]],
    bin_size_km: float,
    los_bands_by_segment: Optional[Dict[str, rulebook.LosBands]] = None,
    los_bands: Optional[rulebook.LosBands] = None,
    logger: Optional[Any] = None,
) -> BinBuildResult:
    """
    Produces BinFeature list + metadata with vectorized accumulation.

    Assumptions:
    - You already mapped runners to segments per time window and provided arrays
      of equal length per window: pos_m[i], speed_mps[i] for runner i.
    - Density is computed as p/m^2 within the bin area (bin_len_m * width_m).
    - Flow (p/s) is density * width_m * mean_speed_mps (absolute per bin/window).
    - LOS bands must be provided from app.rulebook (no local defaults).
    """
    # Issue #640: LOS bands must be provided from rulebook (SSOT)
    if los_bands_by_segment is None and los_bands is None:
        raise ValueError("LOS bands are required; provide los_bands_by_segment or los_bands from app.rulebook.")
    bin_len_m = bin_size_km * 1000.0
    _validate_positive_finite(bin_len_m, "bin_len_m")

    all_features: List[BinFeature] = []

    occupied_bins_total = 0
    nonzero_density_bins_total = 0
    total_bins_estimate = 0

    for seg_id, seg in segments.items():
        _validate_positive_finite(seg.width_m, f"segment[{seg_id}].width_m")
        _validate_positive_finite(seg.length_m, f"segment[{seg_id}].length_m")

        nbins = int(math.ceil(seg.length_m / bin_len_m))
        total_bins_estimate += nbins  # rough tally per window; refined below

        seg_windows = runners_by_segment_and_window.get(seg_id, {})

        for (t_start, t_end, w_idx) in time_windows:
            rw = seg_windows.get(w_idx)
            if rw is None:
                # No runners mapped to this segment/window; still emit zero features? Up to you.
                # Here we emit zeros so the time slider is continuous.
                counts = np.zeros(nbins, dtype=np.int32)
                sum_speed = np.zeros(nbins, dtype=np.float64)
            else:
                pos_m = rw.get("pos_m")
                speed_mps = rw.get("speed_mps")
                if pos_m is None or speed_mps is None or len(pos_m) == 0:
                    counts = np.zeros(nbins, dtype=np.int32)
                    sum_speed = np.zeros(nbins, dtype=np.float64)
                else:
                    # Vectorized accumulation
                    counts, sum_speed = accumulate_window_for_segment(pos_m, speed_mps, seg, bin_len_m)

            # Compute densities & flows vectorized
            area_m2 = bin_len_m * seg.width_m
            # Avoid divide-by-zero, though validated above
            inv_area = 1.0 / area_m2

            density = counts.astype(np.float64) * inv_area  # p/m^2
            mean_speed = np.divide(
                sum_speed,
                np.maximum(counts, 1),  # prevent div by zero
                where=(counts > 0),
                out=np.zeros_like(sum_speed),
            )
            rate = density * seg.width_m * mean_speed  # p/s (throughput rate)

            # Counters
            occupied_bins = int(np.count_nonzero(counts))
            nonzero_density_bins = int(np.count_nonzero(density))
            occupied_bins_total += occupied_bins
            nonzero_density_bins_total += nonzero_density_bins

            if los_bands_by_segment is not None:
                bands = los_bands_by_segment.get(seg_id)
                if bands is None:
                    raise ValueError(f"Missing LOS bands for segment {seg_id}.")
            else:
                bands = los_bands
            if bands is None:
                raise ValueError(f"Missing LOS bands for segment {seg_id}.")

            # Build features (tight loop over nbins is OK; vectors are already computed)
            # If you prefer, you can filter to occupied bins only to shrink payload.
            for b in range(nbins):
                start_m = b * bin_len_m
                end_m = min((b + 1) * bin_len_m, seg.length_m)
                d = float(density[b])
                r = float(rate[b])
                # Issue #640: Classify LOS using rulebook bands (SSOT)
                los = rulebook.classify_los(d, bands)
                bf = BinFeature(
                    segment_id=seg_id,
                    bin_index=b,
                    start_km=start_m / 1000.0,
                    end_km=end_m / 1000.0,
                    t_start=t_start,
                    t_end=t_end,
                    density=d,
                    rate=r,
                    los_class=los,
                    bin_size_km=bin_size_km,
                )
                all_features.append(bf)

    metadata = {
        "bin_size_km": bin_size_km,
        "occupied_bins": occupied_bins_total,
        "nonzero_density_bins": nonzero_density_bins_total,
        "total_features": len(all_features),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "1.0.0",
    }

    # ERROR if nothing is populated
    if (occupied_bins_total == 0 or nonzero_density_bins_total == 0) and logger:
        logger.error(
            "Bin accumulation produced zero occupancy: occupied_bins=%d, nonzero_density_bins=%d. "
            "Check runner mapping, width_m, bin_len_m, and time windowing.",
            occupied_bins_total,
            nonzero_density_bins_total,
        )

    return BinBuildResult(features=all_features, metadata=metadata)

# -------------------------------------------------
# Convenience: build time windows (fixed stride)
# -------------------------------------------------

def make_time_windows(
    *,
    t0: datetime,
    duration_s: int,
    dt_seconds: int,
) -> List[Tuple[datetime, datetime, int]]:
    """Produce [(t_start, t_end, window_index), ...] in UTC."""
    assert dt_seconds > 0 and duration_s >= 0
    out: List[Tuple[datetime, datetime, int]] = []
    n = int(math.ceil(duration_s / dt_seconds)) if duration_s else 0
    for i in range(n):
        ts = t0 + timedelta(seconds=i * dt_seconds)
        te = ts + timedelta(seconds=dt_seconds)
        out.append((ts, te, i))
    return out

# -------------------------------------------------
# Serialization helpers (optional)
# -------------------------------------------------

def to_geojson_features(features: List[BinFeature]) -> List[Dict[str, Any]]:
    """Convert to minimal GeoJSON Feature dicts (geometry building is left to existing code)."""
    out = []
    for f in features:
        props = {
            "bin_id": f"{f.segment_id}:{f.start_km:.3f}-{f.end_km:.3f}",
            "segment_id": f.segment_id,
            "start_km": f.start_km,
            "end_km": f.end_km,
            "t_start": f.t_start.isoformat().replace("+00:00", "Z"),
            "t_end": f.t_end.isoformat().replace("+00:00", "Z"),
            "density": f.density,
            "rate": f.rate,
            "los_class": f.los_class,
            "bin_size_km": f.bin_size_km,
        }
        out.append({
            "type": "Feature",
            "geometry": None,  # your existing geometry builder should fill this using SegmentInfo.coords + bin range
            "properties": props,
        })
    return out
