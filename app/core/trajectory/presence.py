"""Presence queries over trajectory samples for Density bins (#862)."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

WINDOW_TOLERANCE_SEC = 30.0


def datetime_midnight_sec(dt) -> float:
    """Seconds from local midnight for a naive datetime (density dummy date)."""
    return float(dt.hour * 3600 + dt.minute * 60 + dt.second)


class TrajectoryPresence:
    """Sorted sample index: unique runners whose 5s ticks fall in a time×km window."""

    def __init__(
        self,
        t: np.ndarray,
        km: np.ndarray,
        event: np.ndarray,
        runner_id: np.ndarray,
        speed_mps: Optional[np.ndarray] = None,
    ):
        self.t = np.asarray(t, dtype=np.float64)
        self.km = np.asarray(km, dtype=np.float64)
        self.event = np.asarray(event, dtype=object)
        self.runner_id = np.asarray(runner_id, dtype=object)
        if speed_mps is None:
            self.speed_mps = np.full(len(self.t), np.nan, dtype=np.float64)
        else:
            self.speed_mps = np.asarray(speed_mps, dtype=np.float64)

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
        return cls(t[order], km[order], event[order], runner_id[order], speed[order])

    def _slice(self, t0: float, t1: float) -> Tuple[slice, np.ndarray]:
        i0 = int(np.searchsorted(self.t, t0, side="left"))
        i1 = int(np.searchsorted(self.t, t1, side="left"))
        return slice(i0, i1), np.arange(i0, i1)

    def count_unique(
        self,
        t0: float,
        t1: float,
        events: Sequence[str],
        km_intervals: Sequence[Tuple[float, float]],
    ) -> int:
        if len(self.t) == 0 or not events or not km_intervals:
            return 0
        sl, _ = self._slice(t0, t1)
        if sl.start >= sl.stop:
            return 0
        event_set = {str(e).lower() for e in events}
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
    """Populate bins adapter mapping from trajectory samples (Issue #862)."""
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
