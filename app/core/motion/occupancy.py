"""Place occupancy queries over motion samples (#850 Child B / #854)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pandas as pd

from app.utils.constants import MOTION_DEFAULT_PLACE_BUFFER_M


@dataclass(frozen=True)
class PlaceStream:
    """One course stream at a place (segment + reference crossing)."""

    seg_id: str
    center_seg_km: float


@dataclass(frozen=True)
class PlaceSpec:
    """Course-aware place: one or more streams + along-path zone buffer."""

    streams: Tuple[PlaceStream, ...]
    buffer_m: float = MOTION_DEFAULT_PLACE_BUFFER_M
    label: Optional[str] = None
    place_id: Optional[str] = None

    @property
    def buffer_km(self) -> float:
        return max(0.0, float(self.buffer_m)) / 1000.0


def estimate_center_seg_km(
    samples: pd.DataFrame,
    *,
    seg_id: str,
    lat: float,
    lon: float,
    nearest_n: int = 40,
) -> Optional[float]:
    """
    Estimate segment-local center km from motion samples nearest the pin.

    Uses samples already mapped onto ``seg_id`` so the center stays on the
    compiled course stream (not a planar disk across counterflow).
    """
    if samples is None or samples.empty:
        return None
    need = {"seg_id", "seg_km", "lat", "lon"}
    if need - set(samples.columns):
        return None
    sub = samples[samples["seg_id"].astype(str) == str(seg_id)]
    if sub.empty:
        return None
    d2 = (sub["lat"].astype(float) - float(lat)) ** 2 + (
        sub["lon"].astype(float) - float(lon)
    ) ** 2
    n = min(int(nearest_n), int(len(sub)))
    idx = d2.nsmallest(n).index
    return float(sub.loc[idx, "seg_km"].median())


def _zone_mask(samples: pd.DataFrame, place: PlaceSpec) -> pd.Series:
    if samples.empty or not place.streams:
        return pd.Series(False, index=samples.index)
    buf = place.buffer_km
    parts: List[pd.Series] = []
    seg = samples["seg_id"].astype(str)
    seg_km = samples["seg_km"].astype(float)
    for stream in place.streams:
        parts.append(
            (seg == str(stream.seg_id))
            & ((seg_km - float(stream.center_seg_km)).abs() <= buf)
        )
    out = parts[0]
    for part in parts[1:]:
        out = out | part
    return out


def _filter_events(
    samples: pd.DataFrame,
    events: Optional[Sequence[str]],
) -> pd.DataFrame:
    if not events:
        return samples
    wanted = {str(e).strip().lower() for e in events if str(e).strip()}
    if not wanted:
        return samples
    return samples[samples["event"].astype(str).str.lower().isin(wanted)]


def _by_event_counts(runner_event: pd.DataFrame) -> Dict[str, int]:
    if runner_event.empty:
        return {}
    counts = (
        runner_event.drop_duplicates("runner_id")["event"]
        .astype(str)
        .str.lower()
        .value_counts()
        .sort_index()
    )
    return {str(k): int(v) for k, v in counts.items()}


def instantaneous_occupancy(
    samples: pd.DataFrame,
    place: PlaceSpec,
    *,
    t: int,
    events: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Runners inside the place zone at exact clock ``t``."""
    frame = _filter_events(samples, events)
    if frame.empty:
        return {
            "metric": "instantaneous",
            "t": int(t),
            "total": 0,
            "by_event": {},
            "runner_ids": [],
        }
    at_t = frame[frame["t"].astype(int) == int(t)]
    in_zone = at_t.loc[_zone_mask(at_t, place)]
    uniques = in_zone.drop_duplicates("runner_id")
    return {
        "metric": "instantaneous",
        "t": int(t),
        "total": int(len(uniques)),
        "by_event": _by_event_counts(uniques[["runner_id", "event"]]),
        "runner_ids": sorted(uniques["runner_id"].astype(str).tolist()),
    }


def window_uniques(
    samples: pd.DataFrame,
    place: PlaceSpec,
    *,
    t0: int,
    t1: int,
    events: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Distinct runners intersecting the place zone in ``[t0, t1)``."""
    if int(t1) <= int(t0):
        raise ValueError("t1 must be greater than t0 (half-open window)")
    frame = _filter_events(samples, events)
    if frame.empty:
        return {
            "metric": "window_uniques",
            "t0": int(t0),
            "t1": int(t1),
            "total": 0,
            "by_event": {},
            "runner_ids": [],
        }
    window = frame[
        (frame["t"].astype(int) >= int(t0)) & (frame["t"].astype(int) < int(t1))
    ]
    in_zone = window.loc[_zone_mask(window, place)]
    uniques = in_zone.drop_duplicates("runner_id")
    return {
        "metric": "window_uniques",
        "t0": int(t0),
        "t1": int(t1),
        "total": int(len(uniques)),
        "by_event": _by_event_counts(uniques[["runner_id", "event"]]),
        "runner_ids": sorted(uniques["runner_id"].astype(str).tolist()),
    }


def _passage_times_for_stream(
    samples: pd.DataFrame,
    stream: PlaceStream,
) -> List[Tuple[str, str, int]]:
    """
    Detect reference crossings on one stream.

    A passage is a zero-crossing (or land-on-center) of
    ``seg_km - center_seg_km`` between consecutive samples of the same runner
    on ``seg_id``. Passage time is the later sample's ``t``.
    """
    sub = samples[samples["seg_id"].astype(str) == str(stream.seg_id)].copy()
    if sub.empty:
        return []
    sub = sub.sort_values(["runner_id", "t"], kind="mergesort")
    center = float(stream.center_seg_km)
    out: List[Tuple[str, str, int]] = []
    for (rid, event), grp in sub.groupby(["runner_id", "event"], sort=False):
        km = grp["seg_km"].to_numpy(dtype=float)
        ts = grp["t"].to_numpy(dtype=int)
        if len(km) < 2:
            if len(km) == 1 and abs(km[0] - center) < 1e-9:
                out.append((str(rid), str(event).lower(), int(ts[0])))
            continue
        prev = km[0] - center
        for i in range(1, len(km)):
            cur = km[i] - center
            # Arrive at / cross the reference; do not double-count leaving center.
            crossed = (prev * cur < 0.0) or (
                abs(cur) < 1e-12 and abs(prev) >= 1e-12
            )
            if crossed:
                out.append((str(rid), str(event).lower(), int(ts[i])))
            prev = cur
    return out


def throughput_passages(
    samples: pd.DataFrame,
    place: PlaceSpec,
    *,
    t0: int,
    t1: int,
    events: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Count reference-line passages in ``[t0, t1)``.

    Distinct from zone occupancy: uses the stream centerline crossing, not
    merely entering the along-path buffer.
    """
    if int(t1) <= int(t0):
        raise ValueError("t1 must be greater than t0 (half-open window)")
    frame = _filter_events(samples, events)
    passages: List[Dict[str, Any]] = []
    unique_runners = set()
    runner_event: Dict[str, str] = {}
    for stream in place.streams:
        for rid, event, t in _passage_times_for_stream(frame, stream):
            if int(t0) <= int(t) < int(t1):
                passages.append(
                    {
                        "runner_id": rid,
                        "event": event,
                        "t": int(t),
                        "seg_id": stream.seg_id,
                        "center_seg_km": stream.center_seg_km,
                    }
                )
                unique_runners.add(rid)
                runner_event.setdefault(rid, event)
    by_event: Dict[str, int] = {}
    for event in runner_event.values():
        by_event[event] = by_event.get(event, 0) + 1
    passages.sort(key=lambda p: (p["t"], p["runner_id"], p["seg_id"]))
    return {
        "metric": "throughput",
        "t0": int(t0),
        "t1": int(t1),
        "passages": int(len(passages)),
        "unique_runners": int(len(unique_runners)),
        "by_event": {k: by_event[k] for k in sorted(by_event)},
        "passage_rows": passages,
    }


def query_occupancy(
    samples: pd.DataFrame,
    place: PlaceSpec,
    *,
    metrics: Sequence[str],
    t: Optional[int] = None,
    t0: Optional[int] = None,
    t1: Optional[int] = None,
    events: Optional[Sequence[str]] = None,
    include_runner_ids: bool = False,
    include_passage_rows: bool = False,
) -> Dict[str, Any]:
    """Run one or more occupancy metrics for a place."""
    wanted = [str(m).strip().lower() for m in metrics if str(m).strip()]
    if not wanted:
        wanted = ["instantaneous", "window_uniques", "throughput"]

    result: Dict[str, Any] = {
        "mode": "course",
        "place": {
            "place_id": place.place_id,
            "label": place.label,
            "buffer_m": place.buffer_m,
            "streams": [
                {"seg_id": s.seg_id, "center_seg_km": s.center_seg_km}
                for s in place.streams
            ],
        },
        "metrics": {},
    }

    if "instantaneous" in wanted:
        if t is None:
            raise ValueError("instantaneous requires t")
        payload = instantaneous_occupancy(
            samples, place, t=int(t), events=events
        )
        if not include_runner_ids:
            payload = {k: v for k, v in payload.items() if k != "runner_ids"}
        result["metrics"]["instantaneous"] = payload

    need_window = "window_uniques" in wanted or "throughput" in wanted
    if need_window and (t0 is None or t1 is None):
        raise ValueError("window metrics require t0 and t1")

    if "window_uniques" in wanted:
        payload = window_uniques(
            samples, place, t0=int(t0), t1=int(t1), events=events
        )
        if not include_runner_ids:
            payload = {k: v for k, v in payload.items() if k != "runner_ids"}
        result["metrics"]["window_uniques"] = payload

    if "throughput" in wanted:
        payload = throughput_passages(
            samples, place, t0=int(t0), t1=int(t1), events=events
        )
        if not include_passage_rows:
            payload = {
                k: v for k, v in payload.items() if k != "passage_rows"
            }
        result["metrics"]["throughput"] = payload

    return result


def build_places_from_passes(
    passes_df: pd.DataFrame,
    samples: pd.DataFrame,
    *,
    default_buffer_m: float = MOTION_DEFAULT_PLACE_BUFFER_M,
) -> List[Dict[str, Any]]:
    """
    Build pass-level stream rows (internal / advanced).

    Prefer :func:`build_location_places_from_passes` for user-facing catalogs.
    """
    if passes_df is None or passes_df.empty:
        return []
    required = {"pass_id", "seg_id", "lat", "lon"}
    missing = required - set(passes_df.columns)
    if missing:
        raise ValueError(f"passes.csv missing columns {sorted(missing)}")

    places: List[Dict[str, Any]] = []
    for _, row in passes_df.iterrows():
        seg_id = str(row["seg_id"]).strip()
        if not seg_id or seg_id.lower() == "nan":
            continue
        lat = float(row["lat"])
        lon = float(row["lon"])
        center = estimate_center_seg_km(
            samples, seg_id=seg_id, lat=lat, lon=lon
        )
        if center is None:
            continue
        buffer_m = float(default_buffer_m)
        package_buffer_m = None
        if "buffer" in passes_df.columns and pd.notna(row.get("buffer")):
            try:
                package_buffer_m = float(row["buffer"])
            except (TypeError, ValueError):
                package_buffer_m = None
        label = None
        if "loc_label" in passes_df.columns and pd.notna(row.get("loc_label")):
            label = str(row["loc_label"])
        loc_id = None
        if "loc_id" in passes_df.columns and pd.notna(row.get("loc_id")):
            loc_id = str(row["loc_id"])
        places.append(
            {
                "pass_id": str(row["pass_id"]),
                "loc_id": loc_id,
                "label": label,
                "seg_id": seg_id,
                "center_seg_km": center,
                "buffer_m": buffer_m,
                "package_buffer_m": package_buffer_m,
                "lat": lat,
                "lon": lon,
            }
        )
    places.sort(key=lambda p: (p.get("label") or "", p["pass_id"]))
    return places


def build_location_places_from_passes(
    passes_df: pd.DataFrame,
    samples: pd.DataFrame,
    *,
    default_buffer_m: float = MOTION_DEFAULT_PLACE_BUFFER_M,
) -> List[Dict[str, Any]]:
    """
    User-facing place catalog: one row per ``loc_id``.

    Passes are authoring detail (multiple course streams at one geography).
    Each location aggregates every mappable pass/stream under that ``loc_id``.
    """
    pass_rows = build_places_from_passes(
        passes_df, samples, default_buffer_m=default_buffer_m
    )
    by_loc: Dict[str, Dict[str, Any]] = {}
    for row in pass_rows:
        loc_id = row.get("loc_id")
        if not loc_id:
            # Orphan pass without loc_id: still expose as synthetic loc.
            loc_id = f"pass:{row['pass_id']}"
        bucket = by_loc.get(loc_id)
        stream = {
            "pass_id": row["pass_id"],
            "seg_id": row["seg_id"],
            "center_seg_km": row["center_seg_km"],
        }
        if bucket is None:
            by_loc[loc_id] = {
                "loc_id": str(loc_id),
                "label": row.get("label"),
                "lat": row.get("lat"),
                "lon": row.get("lon"),
                "buffer_m": row.get("buffer_m", default_buffer_m),
                "package_buffer_m": row.get("package_buffer_m"),
                "streams": [stream],
                "seg_ids": [row["seg_id"]],
            }
        else:
            bucket["streams"].append(stream)
            if row["seg_id"] not in bucket["seg_ids"]:
                bucket["seg_ids"].append(row["seg_id"])
            if not bucket.get("label") and row.get("label"):
                bucket["label"] = row["label"]

    places = list(by_loc.values())
    places.sort(
        key=lambda p: (
            (p.get("label") or "").lower(),
            str(p.get("loc_id") or ""),
        )
    )
    return places


def place_spec_from_location(
    location: Mapping[str, Any],
    *,
    buffer_m: Optional[float] = None,
) -> PlaceSpec:
    """Build a multi-stream ``PlaceSpec`` from a loc_id catalog row."""
    streams = tuple(
        PlaceStream(
            seg_id=str(s["seg_id"]),
            center_seg_km=float(s["center_seg_km"]),
        )
        for s in (location.get("streams") or [])
    )
    if not streams:
        raise ValueError("location has no mappable streams")
    return PlaceSpec(
        streams=streams,
        buffer_m=float(
            buffer_m
            if buffer_m is not None
            else location.get("buffer_m", MOTION_DEFAULT_PLACE_BUFFER_M)
        ),
        label=location.get("label"),
        place_id=str(location.get("loc_id")),
    )


# ---------------------------------------------------------------------------
# Planar GPS pin mode (user-facing default for loc_id)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PinPlace:
    """Geographic pin: lat/lon + radius in metres (independent of segments)."""

    lat: float
    lon: float
    radius_m: float = MOTION_DEFAULT_PLACE_BUFFER_M
    label: Optional[str] = None
    place_id: Optional[str] = None


def build_location_pins_from_passes(
    passes_df: pd.DataFrame,
    *,
    default_radius_m: float = MOTION_DEFAULT_PLACE_BUFFER_M,
) -> List[Dict[str, Any]]:
    """
    Fast loc_id catalog for planar queries (lat/lon only; no motion join).
    """
    if passes_df is None or passes_df.empty:
        return []
    required = {"loc_id", "lat", "lon"}
    missing = required - set(passes_df.columns)
    if missing:
        raise ValueError(f"passes.csv missing columns {sorted(missing)}")

    pins: Dict[str, Dict[str, Any]] = {}
    for _, row in passes_df.iterrows():
        if pd.isna(row.get("loc_id")):
            continue
        loc_id = str(row["loc_id"])
        try:
            lat = float(row["lat"])
            lon = float(row["lon"])
        except (TypeError, ValueError):
            continue
        label = None
        if "loc_label" in passes_df.columns and pd.notna(row.get("loc_label")):
            label = str(row["loc_label"])
        if loc_id not in pins:
            pins[loc_id] = {
                "loc_id": loc_id,
                "label": label,
                "lat": lat,
                "lon": lon,
                "radius_m": float(default_radius_m),
                "buffer_m": float(default_radius_m),
            }
        elif not pins[loc_id].get("label") and label:
            pins[loc_id]["label"] = label

    out = list(pins.values())
    out.sort(
        key=lambda p: (
            (p.get("label") or "").lower(),
            str(p.get("loc_id") or ""),
        )
    )
    return out


def pin_place_from_location(
    location: Mapping[str, Any],
    *,
    radius_m: Optional[float] = None,
) -> PinPlace:
    if location.get("lat") is None or location.get("lon") is None:
        raise ValueError("location missing lat/lon for planar pin mode")
    return PinPlace(
        lat=float(location["lat"]),
        lon=float(location["lon"]),
        radius_m=float(
            radius_m
            if radius_m is not None
            else location.get("radius_m")
            or location.get("buffer_m")
            or MOTION_DEFAULT_PLACE_BUFFER_M
        ),
        label=location.get("label"),
        place_id=str(location.get("loc_id")),
    )


def _haversine_m_vec(
    lat1: float,
    lon1: float,
    lat2: pd.Series,
    lon2: pd.Series,
) -> pd.Series:
    """Vectorized haversine distance in metres."""
    import numpy as np

    rlat1 = np.radians(lat1)
    rlon1 = np.radians(lon1)
    rlat2 = np.radians(lat2.to_numpy(dtype=float))
    rlon2 = np.radians(lon2.to_numpy(dtype=float))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = (
        np.sin(dlat / 2.0) ** 2
        + np.cos(rlat1) * np.cos(rlat2) * np.sin(dlon / 2.0) ** 2
    )
    return pd.Series(2 * 6371000.0 * np.arcsin(np.sqrt(a)), index=lat2.index)


def _planar_inside_mask(samples: pd.DataFrame, pin: PinPlace) -> pd.Series:
    if samples.empty:
        return pd.Series(False, index=samples.index)
    # Cheap bbox pad (~20%) then exact haversine.
    pad_deg = (float(pin.radius_m) * 1.2) / 111320.0
    rough = (
        (samples["lat"].astype(float) - float(pin.lat)).abs() <= pad_deg
    ) & (
        (samples["lon"].astype(float) - float(pin.lon)).abs() <= pad_deg * 1.5
    )
    if not bool(rough.any()):
        return pd.Series(False, index=samples.index)
    dist = pd.Series(float("inf"), index=samples.index, dtype=float)
    sub = samples.loc[rough]
    dist.loc[rough] = _haversine_m_vec(
        float(pin.lat), float(pin.lon), sub["lat"], sub["lon"]
    )
    return dist <= float(pin.radius_m)


def planar_instantaneous(
    samples: pd.DataFrame,
    pin: PinPlace,
    *,
    t: int,
    events: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    frame = _filter_events(samples, events)
    at_t = frame[frame["t"].astype(int) == int(t)]
    inside = at_t.loc[_planar_inside_mask(at_t, pin)]
    uniques = inside.drop_duplicates("runner_id")
    return {
        "metric": "instantaneous",
        "t": int(t),
        "total": int(len(uniques)),
        "by_event": _by_event_counts(uniques[["runner_id", "event"]]),
        "runner_ids": sorted(uniques["runner_id"].astype(str).tolist()),
    }


def planar_window_uniques(
    samples: pd.DataFrame,
    pin: PinPlace,
    *,
    t0: int,
    t1: int,
    events: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    if int(t1) <= int(t0):
        raise ValueError("t1 must be greater than t0 (half-open window)")
    frame = _filter_events(samples, events)
    window = frame[
        (frame["t"].astype(int) >= int(t0)) & (frame["t"].astype(int) < int(t1))
    ]
    inside = window.loc[_planar_inside_mask(window, pin)]
    uniques = inside.drop_duplicates("runner_id")
    return {
        "metric": "window_uniques",
        "t0": int(t0),
        "t1": int(t1),
        "total": int(len(uniques)),
        "by_event": _by_event_counts(uniques[["runner_id", "event"]]),
        "runner_ids": sorted(uniques["runner_id"].astype(str).tolist()),
    }


def planar_throughput(
    samples: pd.DataFrame,
    pin: PinPlace,
    *,
    t0: int,
    t1: int,
    events: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Count enter/exit events of the GPS disk in ``[t0, t1)``.

    An enter is outside→inside between consecutive samples of a runner.
    Headline ``unique_runners`` = distinct runners with ≥1 enter in the window.
    """
    if int(t1) <= int(t0):
        raise ValueError("t1 must be greater than t0 (half-open window)")
    frame = _filter_events(samples, events)
    empty = {
        "metric": "throughput",
        "t0": int(t0),
        "t1": int(t1),
        "entries": 0,
        "exits": 0,
        "passages": 0,
        "unique_runners": 0,
        "by_event": {},
        "passage_rows": [],
    }
    if frame.empty:
        return empty

    # Need samples before t0 so we know if a runner was already inside.
    work = frame[frame["t"].astype(int) < int(t1)].copy()
    work["_inside"] = _planar_inside_mask(work, pin)
    work = work.sort_values(["runner_id", "t"], kind="mergesort")

    entries: List[Dict[str, Any]] = []
    exits: List[Dict[str, Any]] = []
    for (rid, event), grp in work.groupby(["runner_id", "event"], sort=False):
        ts = grp["t"].to_numpy(dtype=int)
        inside = grp["_inside"].to_numpy(dtype=bool)
        prev = False
        for i in range(len(ts)):
            cur = bool(inside[i])
            t = int(ts[i])
            if cur and not prev and int(t0) <= t < int(t1):
                entries.append(
                    {
                        "runner_id": str(rid),
                        "event": str(event).lower(),
                        "t": t,
                        "kind": "enter",
                    }
                )
            if prev and not cur and int(t0) <= t < int(t1):
                exits.append(
                    {
                        "runner_id": str(rid),
                        "event": str(event).lower(),
                        "t": t,
                        "kind": "exit",
                    }
                )
            prev = cur

    unique_runners = {e["runner_id"] for e in entries}
    runner_event: Dict[str, str] = {}
    for e in entries:
        runner_event.setdefault(e["runner_id"], e["event"])
    by_event: Dict[str, int] = {}
    for event in runner_event.values():
        by_event[event] = by_event.get(event, 0) + 1

    passage_rows = sorted(
        entries + exits, key=lambda r: (r["t"], r["runner_id"], r["kind"])
    )
    return {
        "metric": "throughput",
        "t0": int(t0),
        "t1": int(t1),
        "entries": int(len(entries)),
        "exits": int(len(exits)),
        "passages": int(len(entries)),
        "unique_runners": int(len(unique_runners)),
        "by_event": {k: by_event[k] for k in sorted(by_event)},
        "passage_rows": passage_rows,
    }


def query_planar_occupancy(
    samples: pd.DataFrame,
    pin: PinPlace,
    *,
    metrics: Sequence[str],
    t: Optional[int] = None,
    t0: Optional[int] = None,
    t1: Optional[int] = None,
    events: Optional[Sequence[str]] = None,
    include_runner_ids: bool = False,
    include_passage_rows: bool = False,
) -> Dict[str, Any]:
    """Planar GPS-disk occupancy for a location pin."""
    wanted = [str(m).strip().lower() for m in metrics if str(m).strip()]
    if not wanted:
        wanted = ["instantaneous", "window_uniques", "throughput"]

    result: Dict[str, Any] = {
        "mode": "planar",
        "place": {
            "place_id": pin.place_id,
            "label": pin.label,
            "lat": pin.lat,
            "lon": pin.lon,
            "radius_m": pin.radius_m,
            "buffer_m": pin.radius_m,
        },
        "metrics": {},
    }

    if "instantaneous" in wanted:
        if t is None:
            raise ValueError("instantaneous requires t")
        payload = planar_instantaneous(samples, pin, t=int(t), events=events)
        if not include_runner_ids:
            payload = {k: v for k, v in payload.items() if k != "runner_ids"}
        result["metrics"]["instantaneous"] = payload

    need_window = "window_uniques" in wanted or "throughput" in wanted
    if need_window and (t0 is None or t1 is None):
        raise ValueError("window metrics require t0 and t1")

    if "window_uniques" in wanted:
        payload = planar_window_uniques(
            samples, pin, t0=int(t0), t1=int(t1), events=events
        )
        if not include_runner_ids:
            payload = {k: v for k, v in payload.items() if k != "runner_ids"}
        result["metrics"]["window_uniques"] = payload

    if "throughput" in wanted:
        payload = planar_throughput(
            samples, pin, t0=int(t0), t1=int(t1), events=events
        )
        if not include_passage_rows:
            payload = {
                k: v for k, v in payload.items() if k != "passage_rows"
            }
        result["metrics"]["throughput"] = payload

    return result
