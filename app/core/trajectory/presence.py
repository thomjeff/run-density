"""Presence queries over the trajectory clock for Density bins (#862 / #869)."""

from __future__ import annotations

from typing import Dict, Iterable, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

WINDOW_TOLERANCE_SEC = 30.0


def datetime_midnight_sec(dt) -> float:
    """Seconds from local midnight for a naive datetime (density dummy date)."""
    return float(dt.hour * 3600 + dt.minute * 60 + dt.second)


def guns_from_start_times(start_times: Optional[Dict]) -> Dict[str, float]:
    """Event gun times as seconds from local midnight.

    Density passes datetimes; bins mapping passes minutes after midnight.
    """
    out: Dict[str, float] = {}
    for key, value in (start_times or {}).items():
        name = str(key).lower()
        if hasattr(value, "hour"):
            out[name] = datetime_midnight_sec(value)
        else:
            # Minutes after midnight (bins mapping / Event.start_time).
            out[name] = float(value) * 60.0
    return out


class TrajectoryPresence:
    """Unique runners whose constant-pace km path overlaps a time×km window.

    Prefer ``from_snapshot`` (#869): closed-form ``km(t)`` on ~N runners, same
    formula as the 5s sample grid. ``from_samples`` remains for tests.
    """

    def __init__(
        self,
        t: np.ndarray,
        km: np.ndarray,
        event: np.ndarray,
        runner_id: np.ndarray,
        speed_mps: Optional[np.ndarray] = None,
        *,
        start_sec: Optional[np.ndarray] = None,
        pace_sec: Optional[np.ndarray] = None,
        finish_t: Optional[np.ndarray] = None,
        finish_km: Optional[np.ndarray] = None,
        clock: str = "samples",
    ):
        self.clock = clock
        self.t = np.asarray(t, dtype=np.float64)
        self.km = np.asarray(km, dtype=np.float64)
        self.event = np.asarray(event, dtype=object)
        self.runner_id = np.asarray(runner_id, dtype=object)
        if speed_mps is None:
            self.speed_mps = np.full(len(self.event), np.nan, dtype=np.float64)
        else:
            self.speed_mps = np.asarray(speed_mps, dtype=np.float64)
        self.start_sec = None if start_sec is None else np.asarray(start_sec, dtype=np.float64)
        self.pace_sec = None if pace_sec is None else np.asarray(pace_sec, dtype=np.float64)
        self.finish_t = None if finish_t is None else np.asarray(finish_t, dtype=np.float64)
        self.finish_km = None if finish_km is None else np.asarray(finish_km, dtype=np.float64)

    @classmethod
    def from_samples(
        cls,
        samples: pd.DataFrame,
        snapshot: Optional[pd.DataFrame] = None,
    ) -> "TrajectoryPresence":
        if samples is None or samples.empty:
            return cls(
                np.array([], dtype=np.float64),
                np.array([], dtype=np.float64),
                np.array([], dtype=object),
                np.array([], dtype=object),
            )
        t = samples["t"].to_numpy(dtype=np.float64)
        km = samples["elapsed_km"].to_numpy(dtype=np.float64)
        event = samples["event"].astype(str).str.lower().to_numpy()
        runner_id = samples["runner_id"].astype(str).to_numpy()
        speed = np.full(len(t), np.nan, dtype=np.float64)
        if snapshot is not None and not snapshot.empty and "pace" in snapshot.columns:
            snap = snapshot.copy()
            snap["runner_id"] = snap["runner_id"].astype(str)
            pace_map = dict(zip(snap["runner_id"].astype(str), snap["pace"].astype(float)))
            pace_sec = np.array([float(pace_map.get(r, np.nan)) * 60.0 for r in runner_id])
            with np.errstate(divide="ignore", invalid="ignore"):
                speed = np.where(pace_sec > 0, 1000.0 / pace_sec, np.nan)
        order = np.argsort(t, kind="mergesort")
        return cls(t[order], km[order], event[order], runner_id[order], speed[order], clock="samples")

    @classmethod
    def from_snapshot(
        cls,
        snapshot: pd.DataFrame,
        start_times: Union[Dict, None],
    ) -> "TrajectoryPresence":
        """Closed-form clock: ``km = (t - gun - offset) / (pace_min_per_km * 60)``."""
        empty = cls(
            np.array([], dtype=np.float64),
            np.array([], dtype=np.float64),
            np.array([], dtype=object),
            np.array([], dtype=object),
            clock="snapshot",
        )
        if snapshot is None or snapshot.empty:
            return empty
        guns = guns_from_start_times(start_times)
        if not guns:
            return empty
        snap = snapshot.copy()
        snap["event"] = snap["event"].astype(str).str.lower()
        snap["runner_id"] = snap["runner_id"].astype(str)
        if "start_offset" not in snap.columns:
            snap["start_offset"] = 0.0
        if "distance" not in snap.columns:
            snap["distance"] = np.nan
        gun = np.array([guns.get(str(e), np.nan) for e in snap["event"]], dtype=np.float64)
        offset = pd.to_numeric(snap["start_offset"], errors="coerce").to_numpy(dtype=np.float64)
        offset = np.nan_to_num(offset, nan=0.0)
        pace_min = pd.to_numeric(snap["pace"], errors="coerce").to_numpy(dtype=np.float64)
        pace_sec = pace_min * 60.0
        start_sec = gun + offset
        finish_km = pd.to_numeric(snap["distance"], errors="coerce").to_numpy(dtype=np.float64)
        finish_km = np.where(np.isfinite(finish_km) & (finish_km > 0), finish_km, 1.0e6)
        with np.errstate(invalid="ignore"):
            finish_t = start_sec + pace_sec * finish_km
            speed = np.where(pace_sec > 0, 1000.0 / pace_sec, np.nan)
        ok = np.isfinite(start_sec) & np.isfinite(pace_sec) & (pace_sec > 0)
        event = snap["event"].to_numpy()[ok]
        runner_id = snap["runner_id"].to_numpy()[ok]
        return cls(
            np.array([], dtype=np.float64),
            np.array([], dtype=np.float64),
            event,
            runner_id,
            speed[ok],
            start_sec=start_sec[ok],
            pace_sec=pace_sec[ok],
            finish_t=finish_t[ok],
            finish_km=finish_km[ok],
            clock="snapshot",
        )

    def _slice(self, t0: float, t1: float) -> Tuple[slice, np.ndarray]:
        i0 = int(np.searchsorted(self.t, t0, side="left"))
        i1 = int(np.searchsorted(self.t, t1, side="left"))
        return slice(i0, i1), np.arange(i0, i1)

    def _snapshot_span(self, t0: float, t1: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Km occupied on-course during half-open ``[t0, t1)``."""
        start = self.start_sec
        pace = self.pace_sec
        finish_t = self.finish_t
        finish_km = self.finish_km
        valid_lo = np.maximum(float(t0), start)
        valid_hi = np.minimum(float(t1), finish_t)
        on = (
            (valid_lo < valid_hi)
            & np.isfinite(valid_lo)
            & np.isfinite(valid_hi)
            & (pace > 0)
        )
        with np.errstate(divide="ignore", invalid="ignore"):
            km_lo = (valid_lo - start) / pace
            km_hi = (valid_hi - start) / pace
        km_lo = np.clip(km_lo, 0.0, finish_km)
        km_hi = np.clip(km_hi, 0.0, finish_km)
        return on, km_lo, km_hi

    def count_unique(
        self,
        t0: float,
        t1: float,
        events: Sequence[str],
        km_intervals: Sequence[Tuple[float, float]],
    ) -> int:
        if not events or not km_intervals:
            return 0
        event_set = {str(e).lower() for e in events}
        if self.clock == "snapshot" and self.start_sec is not None:
            if len(self.event) == 0:
                return 0
            on, km_lo, km_hi = self._snapshot_span(t0, t1)
            ev_ok = np.array([str(e) in event_set for e in self.event], dtype=bool)
            km_ok = np.zeros(len(self.event), dtype=bool)
            for start, end in km_intervals:
                km_ok |= (km_lo <= float(end)) & (km_hi >= float(start))
            mask = on & ev_ok & km_ok
            if not np.any(mask):
                return 0
            return int(np.unique(self.runner_id[mask]).size)
        if len(self.t) == 0:
            return 0
        sl, _ = self._slice(t0, t1)
        if sl.start >= sl.stop:
            return 0
        ev = self.event[sl]
        km = self.km[sl]
        rid = self.runner_id[sl]
        mask = np.array([str(e) in event_set for e in ev], dtype=bool)
        km_ok = np.zeros(len(km), dtype=bool)
        for start, end in km_intervals:
            km_ok |= (km >= float(start)) & (km <= float(end))
        mask &= km_ok
        if not np.any(mask):
            return 0
        return int(np.unique(rid[mask]).size)

    def positions_in_window(
        self,
        t_mid_sec: float,
        from_km: float,
        to_km: float,
        event: str,
        tolerance_sec: float = WINDOW_TOLERANCE_SEC,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """One (pos_m, speed_mps) per runner nearest ``t_mid`` on this event×segment."""
        if self.clock == "snapshot" and self.start_sec is not None:
            return self._positions_from_snapshot(
                t_mid_sec, from_km, to_km, event, tolerance_sec
            )
        t0 = float(t_mid_sec) - float(tolerance_sec)
        t1 = float(t_mid_sec) + float(tolerance_sec)
        sl, idx = self._slice(t0, t1)
        if sl.start >= sl.stop:
            return np.array([], dtype=np.float64), np.array([], dtype=np.float64)
        event_l = str(event).lower()
        ev = self.event[sl]
        km = self.km[sl]
        rid = self.runner_id[sl]
        t = self.t[sl]
        speed = self.speed_mps[sl]
        mask = (ev == event_l) & (km >= float(from_km)) & (km <= float(to_km))
        if not np.any(mask):
            return np.array([], dtype=np.float64), np.array([], dtype=np.float64)
        dt = np.abs(t[mask] - float(t_mid_sec))
        rids = rid[mask]
        kms = km[mask]
        spd = speed[mask]
        best: Dict[str, Tuple[float, float, float]] = {}
        for i, runner in enumerate(rids):
            key = str(runner)
            prev = best.get(key)
            if prev is None or dt[i] < prev[0]:
                best[key] = (float(dt[i]), float(kms[i]), float(spd[i]))
        pos_m = np.array([(v[1] - float(from_km)) * 1000.0 for v in best.values()], dtype=np.float64)
        speeds = np.array([v[2] for v in best.values()], dtype=np.float64)
        return pos_m, speeds

    def _positions_from_snapshot(
        self,
        t_mid_sec: float,
        from_km: float,
        to_km: float,
        event: str,
        tolerance_sec: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        if len(self.event) == 0:
            return np.array([], dtype=np.float64), np.array([], dtype=np.float64)
        event_l = str(event).lower()
        t0 = float(t_mid_sec) - float(tolerance_sec)
        t1 = float(t_mid_sec) + float(tolerance_sec)
        enter = self.start_sec + self.pace_sec * float(from_km)
        leave = self.start_sec + self.pace_sec * float(to_km)
        enter = np.maximum(enter, self.start_sec)
        leave = np.minimum(leave, self.finish_t)
        overlap = (enter <= t1) & (leave >= t0) & (leave >= enter)
        ev_ok = np.array([str(e) == event_l for e in self.event], dtype=bool)
        mask = overlap & ev_ok & (self.pace_sec > 0)
        if not np.any(mask):
            return np.array([], dtype=np.float64), np.array([], dtype=np.float64)
        with np.errstate(divide="ignore", invalid="ignore"):
            km_mid = (float(t_mid_sec) - self.start_sec[mask]) / self.pace_sec[mask]
        km_pos = np.clip(km_mid, float(from_km), float(to_km))
        pos_m = (km_pos - float(from_km)) * 1000.0
        speeds = self.speed_mps[mask]
        return np.asarray(pos_m, dtype=np.float64), np.asarray(speeds, dtype=np.float64)


def fill_mapping_from_samples(
    presence: TrajectoryPresence,
    *,
    segments_dict: Dict,
    time_windows: list,
    start_times: Dict[str, float],
    event_names: Iterable[str],
    segment_ranges: Dict,
    segments_config: pd.DataFrame,
    mapping: Dict,
) -> Dict:
    """Populate bins adapter mapping from the trajectory clock (Issue #862 / #869)."""
    if not time_windows:
        return mapping
    window_seconds = 120
    if len(time_windows) >= 2:
        (t0, t1, _) = time_windows[0]
        (t2, t3, _) = time_windows[1]
        window_seconds = int((t2 - t0).total_seconds())
    earliest_start_min = min(start_times.values())
    for event in event_names:
        event_lower = str(event).lower()
        event_min = start_times.get(event_lower) or start_times.get(event)
        if event_min is None:
            continue
        event_start_sec = float(event_min) * 60.0
        start_idx = int(((float(event_min) - earliest_start_min) * 60) // window_seconds)
        event_column = event_lower
        for global_w_idx in range(start_idx, len(time_windows)):
            (t_start, t_end, _) = time_windows[global_w_idx]
            t_mid = t_start + (t_end - t_start) / 2
            t_mid_sec = t_mid.hour * 3600 + t_mid.minute * 60 + t_mid.second
            if t_mid_sec < (event_start_sec - window_seconds):
                continue
            for seg_id in segments_dict.keys():
                if seg_id not in segment_ranges:
                    continue
                seg_row = segments_config[segments_config["seg_id"] == seg_id]
                if len(seg_row) == 0:
                    continue
                flag = str(seg_row.iloc[0].get(event_column, "n")).lower()
                if flag not in {"y", "yes", "true", "1"}:
                    continue
                km_range = segment_ranges[seg_id].get(event_lower) or segment_ranges[seg_id].get(event)
                if km_range is None:
                    continue
                from_km, to_km = km_range
                if pd.isna(from_km) or pd.isna(to_km):
                    continue
                pos_m, speeds = presence.positions_in_window(
                    t_mid_sec, float(from_km), float(to_km), event_lower
                )
                if len(pos_m) == 0:
                    continue
                if seg_id not in mapping:
                    mapping[seg_id] = {}
                if global_w_idx in mapping[seg_id]:
                    mapping[seg_id][global_w_idx]["pos_m"] = np.concatenate(
                        [mapping[seg_id][global_w_idx]["pos_m"], pos_m]
                    )
                    mapping[seg_id][global_w_idx]["speed_mps"] = np.concatenate(
                        [mapping[seg_id][global_w_idx]["speed_mps"], speeds]
                    )
                else:
                    mapping[seg_id][global_w_idx] = {
                        "pos_m": pos_m,
                        "speed_mps": speeds,
                    }
    return mapping
