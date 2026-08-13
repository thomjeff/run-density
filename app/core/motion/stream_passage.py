"""Motion Stream Passage: time-windowed pin enter/exit tables (#850 / #855)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from app.core.motion.occupancy import PinPlace, _filter_events, _planar_inside_mask
from app.core.motion.movement_drilldown import (
    COUNT_SEMANTICS,
    COUNT_SEMANTICS_NOTE,
    MATRIX_SEMANTICS_NOTE,
    attach_quintile_matrices,
    build_concurrent_pairs,
    build_movement_spans,
    build_runner_quintile_lookup,
    quintile_profile_for_runners,
    stream_key,
)
from app.utils.constants import (
    MOTION_QUINTILE_PARTNER_DWELL_SEC,
    MOTION_STREAM_WINDOW_SEC,
    MOTION_VISIT_KM_GAP,
)


def _sec_to_clock(sec: int) -> str:
    """Format midnight-aligned seconds as HH:MM (seconds omitted for UI density)."""
    t = max(0, int(sec))
    h = t // 3600
    m = (t % 3600) // 60
    return f"{h:02d}:{m:02d}"


def planar_crossing_events(
    samples: pd.DataFrame,
    pin: PinPlace,
    *,
    t0: Optional[int] = None,
    t1: Optional[int] = None,
    events: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    """
    Detect pin enter/exit crossings with optional elapsed_km at the sample.

    If ``t0``/``t1`` are omitted, returns all crossings over the sample span.
    Samples before ``t0`` are still used so “already inside” is known.
    """
    frame = _filter_events(samples, events)
    cols = ["runner_id", "event", "t", "kind", "elapsed_km"]
    if frame.empty:
        return pd.DataFrame(columns=cols)

    need = {"runner_id", "event", "t", "lat", "lon"}
    missing = need - set(frame.columns)
    if missing:
        raise ValueError(f"Motion samples missing columns {sorted(missing)}")

    has_km = "elapsed_km" in frame.columns
    if t1 is None:
        t_max = int(frame["t"].max()) + 1
    else:
        t_max = int(t1)
    t_min_filter = None if t0 is None else int(t0)

    work = frame[frame["t"].astype(int) < t_max].copy()
    if work.empty:
        return pd.DataFrame(columns=cols)

    work["_inside"] = _planar_inside_mask(work, pin)
    work = work.sort_values(["runner_id", "t"], kind="mergesort")

    rows: List[Dict[str, Any]] = []
    for (rid, event), grp in work.groupby(["runner_id", "event"], sort=False):
        ts = grp["t"].to_numpy(dtype=int)
        inside = grp["_inside"].to_numpy(dtype=bool)
        kms = (
            grp["elapsed_km"].to_numpy(dtype=float)
            if has_km
            else [float("nan")] * len(ts)
        )
        prev = False
        for i in range(len(ts)):
            cur = bool(inside[i])
            t = int(ts[i])
            in_range = t_min_filter is None or (
                int(t_min_filter) <= t < t_max
            )
            if cur and not prev and in_range:
                rows.append(
                    {
                        "runner_id": str(rid),
                        "event": str(event).lower(),
                        "t": t,
                        "kind": "enter",
                        "elapsed_km": float(kms[i]),
                    }
                )
            if prev and not cur and in_range:
                rows.append(
                    {
                        "runner_id": str(rid),
                        "event": str(event).lower(),
                        "t": t,
                        "kind": "exit",
                        "elapsed_km": float(kms[i]),
                    }
                )
            prev = cur

    if not rows:
        return pd.DataFrame(columns=cols)
    out = pd.DataFrame(rows, columns=cols)
    return out.sort_values(["t", "runner_id", "kind"], kind="mergesort").reset_index(
        drop=True
    )


def pair_visit_episodes(crossings: pd.DataFrame) -> pd.DataFrame:
    """
    Pair enter→exit crossings into visit episodes per (runner_id, event).

    A visit is one contiguous traversal through the location detection zone.
    Unpaired enters/exits are kept with orphan markers (excluded from summary
    passage counts unless they have an enter_km for clustering).
    """
    cols = [
        "runner_id",
        "event",
        "enter_t",
        "exit_t",
        "enter_km",
        "exit_km",
        "orphan",
    ]
    if crossings is None or crossings.empty:
        return pd.DataFrame(columns=cols)

    rows: List[Dict[str, Any]] = []
    ordered = crossings.sort_values(["runner_id", "event", "t"], kind="mergesort")
    for (rid, event), grp in ordered.groupby(["runner_id", "event"], sort=False):
        pending_enter: Optional[pd.Series] = None
        for _, r in grp.iterrows():
            kind = str(r["kind"])
            if kind == "enter":
                if pending_enter is not None:
                    rows.append(
                        {
                            "runner_id": str(rid),
                            "event": str(event).lower(),
                            "enter_t": int(pending_enter["t"]),
                            "exit_t": None,
                            "enter_km": float(pending_enter["elapsed_km"]),
                            "exit_km": None,
                            "orphan": "enter_without_exit",
                        }
                    )
                pending_enter = r
            elif kind == "exit":
                if pending_enter is None:
                    rows.append(
                        {
                            "runner_id": str(rid),
                            "event": str(event).lower(),
                            "enter_t": None,
                            "exit_t": int(r["t"]),
                            "enter_km": None,
                            "exit_km": float(r["elapsed_km"]),
                            "orphan": "exit_without_enter",
                        }
                    )
                else:
                    rows.append(
                        {
                            "runner_id": str(rid),
                            "event": str(event).lower(),
                            "enter_t": int(pending_enter["t"]),
                            "exit_t": int(r["t"]),
                            "enter_km": float(pending_enter["elapsed_km"]),
                            "exit_km": float(r["elapsed_km"]),
                            "orphan": None,
                        }
                    )
                    pending_enter = None
        if pending_enter is not None:
            rows.append(
                {
                    "runner_id": str(rid),
                    "event": str(event).lower(),
                    "enter_t": int(pending_enter["t"]),
                    "exit_t": None,
                    "enter_km": float(pending_enter["elapsed_km"]),
                    "exit_km": None,
                    "orphan": "enter_without_exit",
                }
            )

    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows, columns=cols)


def _gap_cluster_labels(
    kms: Sequence[float],
    gap_km: float,
) -> List[float]:
    """
    1D gap clustering on sorted enter km values.

    Returns the median label (2-decimal) for each input km, same order as ``kms``.
    """
    if not kms:
        return []
    indexed = sorted(enumerate(float(k) for k in kms), key=lambda x: x[1])
    clusters: List[List[Tuple[int, float]]] = []
    for idx, km in indexed:
        if not clusters or (km - clusters[-1][-1][1]) >= float(gap_km):
            clusters.append([(idx, km)])
        else:
            clusters[-1].append((idx, km))

    labels = [0.0] * len(kms)
    for cluster in clusters:
        vals = [km for _, km in cluster]
        label = round(float(pd.Series(vals).median()), 2)
        for idx, _ in cluster:
            labels[idx] = label
    return labels


def build_visit_summary(
    episodes: pd.DataFrame,
    *,
    window_sec: int = MOTION_STREAM_WINDOW_SEC,
    gap_km: float = MOTION_VISIT_KM_GAP,
    event_names: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Aggregate visit episodes into (event, visit-cluster) summary rows.

    Visit = one enter→exit episode. Clusters separate materially distinct
    course passages using ``gap_km`` on enter elapsed_km.
    """
    if episodes is None or episodes.empty:
        return []

    # Paired episodes only (complete zone traversals)
    paired = episodes[episodes["orphan"].isna()].copy()
    if paired.empty:
        return []
    paired = paired[paired["enter_km"].notna()].copy()
    if paired.empty:
        return []

    window = max(1, int(window_sec))
    rows: List[Dict[str, Any]] = []

    events = (
        list(event_names)
        if event_names
        else sorted(str(e).lower() for e in paired["event"].unique())
    )
    for ev in events:
        g = paired[paired["event"] == ev]
        if g.empty:
            continue
        labels = _gap_cluster_labels(g["enter_km"].tolist(), gap_km)
        g = g.copy()
        g["visit_km"] = labels
        for visit_km, cg in g.groupby("visit_km", sort=True):
            enter_ts = cg["enter_t"].dropna().astype(int)
            exit_ts = cg["exit_t"].dropna().astype(int)
            first_t = int(enter_ts.min()) if len(enter_ts) else None
            last_t = int(enter_ts.max()) if len(enter_ts) else None
            first_bin = (first_t // window) * window if first_t is not None else None
            last_bin = (last_t // window) * window if last_t is not None else None
            dwell = (
                (cg["exit_t"] - cg["enter_t"])
                if cg["exit_t"].notna().all() and cg["enter_t"].notna().all()
                else pd.Series(dtype=float)
            )
            rows.append(
                {
                    "event": str(ev),
                    "visit_km": float(visit_km),
                    "passages": int(len(cg)),
                    "unique_runners": int(cg["runner_id"].nunique()),
                    "first_enter_t": first_t,
                    "last_enter_t": last_t,
                    "first_window": (
                        f"{_sec_to_clock(first_bin)}–{_sec_to_clock(first_bin + window)}"
                        if first_bin is not None
                        else None
                    ),
                    "last_window": (
                        f"{_sec_to_clock(last_bin)}–{_sec_to_clock(last_bin + window)}"
                        if last_bin is not None
                        else None
                    ),
                    "median_dwell_sec": (
                        int(round(float(dwell.median()))) if len(dwell) else None
                    ),
                    "median_exit_km": (
                        round(float(cg["exit_km"].median()), 2)
                        if cg["exit_km"].notna().any()
                        else None
                    ),
                }
            )

    rows.sort(key=lambda r: (r["event"], r["visit_km"]))
    return rows


def build_stream_passage_table(
    samples: pd.DataFrame,
    pin: PinPlace,
    *,
    window_sec: int = MOTION_STREAM_WINDOW_SEC,
    t0: Optional[int] = None,
    t1: Optional[int] = None,
    events: Optional[Sequence[str]] = None,
    visit_km_gap: float = MOTION_VISIT_KM_GAP,
    runners_df: Optional[pd.DataFrame] = None,
    authored_movements: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Build a midnight-aligned enter/exit time-window table for a GPS pin.

    Each row is one ``[bin_start, bin_start + window_sec)`` interval with
    per-event enter/exit counts. Context lists enter counts by visit cluster
    (``event enter_km:count``) so co-present streams stay visible.

    Also returns ``visit_summary`` and movement drill-down fields (#856):
    concurrent visit pairs per window, day-level movement spans, optional
    authored movement labels, and per-visit pace quintile profiles.
    """
    window = int(window_sec)
    if window <= 0:
        raise ValueError("window_sec must be positive")

    authored = list(authored_movements or [])
    quintile_lookup = build_runner_quintile_lookup(runners_df)

    crossings = planar_crossing_events(
        samples, pin, t0=t0, t1=t1, events=events
    )
    enters = crossings[crossings["kind"] == "enter"].copy()
    exits = crossings[crossings["kind"] == "exit"].copy()
    episodes = pair_visit_episodes(crossings)

    event_names = sorted(
        {
            str(e).lower()
            for e in (
                list(enters["event"].unique()) if not enters.empty else []
            )
            + (list(exits["event"].unique()) if not exits.empty else [])
        }
    )
    if events:
        wanted = {str(e).strip().lower() for e in events if str(e).strip()}
        if wanted:
            event_names = [e for e in event_names if e in wanted] or event_names

    empty_payload = {
        "mode": "stream_passage",
        "place": {
            "place_id": pin.place_id,
            "label": pin.label,
            "lat": pin.lat,
            "lon": pin.lon,
            "radius_m": pin.radius_m,
        },
        "window_sec": window,
        "t0": t0,
        "t1": t1,
        "events": event_names,
        "visit_km_gap": float(visit_km_gap),
        "count_semantics": COUNT_SEMANTICS,
        "count_semantics_note": COUNT_SEMANTICS_NOTE,
        "matrix_semantics_note": MATRIX_SEMANTICS_NOTE,
        "authored_movements": authored,
        "rows": [],
        "visit_summary": [],
        "movement_spans": [],
        "totals": {
            "enters_by_event": {},
            "exits_by_event": {},
            "passages_by_event": {},
            "enter_elapsed_km_by_event": {},
            "unique_runners_total": 0,
            "passages_total": 0,
        },
    }

    if enters.empty and exits.empty:
        return empty_payload

    def _bin_start(t: int) -> int:
        return (int(t) // window) * window

    if not enters.empty:
        enters["bin_t0"] = enters["t"].astype(int).map(_bin_start)
        # Stable visit labels (same clustering as Visit Summary) so window
        # context can show parallel vs cross streams instead of one median.
        visit_labels = pd.Series(index=enters.index, dtype=float)
        for ev, g in enters.groupby("event", sort=False):
            if g["elapsed_km"].notna().any():
                visit_labels.loc[g.index] = _gap_cluster_labels(
                    g["elapsed_km"].tolist(), visit_km_gap
                )
            else:
                visit_labels.loc[g.index] = float("nan")
        enters["visit_km"] = visit_labels
    if not exits.empty:
        exits["bin_t0"] = exits["t"].astype(int).map(_bin_start)

    bin_starts = sorted(
        set(enters["bin_t0"].tolist() if not enters.empty else [])
        | set(exits["bin_t0"].tolist() if not exits.empty else [])
    )

    rows: List[Dict[str, Any]] = []
    for bin_t0 in bin_starts:
        bin_t1 = bin_t0 + window
        e_bin = (
            enters[enters["bin_t0"] == bin_t0]
            if not enters.empty
            else enters
        )
        x_bin = exits[exits["bin_t0"] == bin_t0] if not exits.empty else exits

        enters_by_event: Dict[str, int] = {}
        exits_by_event: Dict[str, int] = {}
        enter_km_by_event: Dict[str, Optional[float]] = {}
        enters_by_visit: List[Dict[str, Any]] = []
        quintile_profiles: List[Dict[str, Any]] = []
        visit_enters: Dict[str, List[Dict[str, Any]]] = {}
        for ev in event_names:
            e_ev = e_bin[e_bin["event"] == ev] if not e_bin.empty else e_bin
            x_ev = x_bin[x_bin["event"] == ev] if not x_bin.empty else x_bin
            enters_by_event[ev] = int(e_ev["runner_id"].nunique()) if len(e_ev) else 0
            exits_by_event[ev] = int(x_ev["runner_id"].nunique()) if len(x_ev) else 0
            if len(e_ev) and e_ev["elapsed_km"].notna().any():
                enter_km_by_event[ev] = round(
                    float(e_ev["elapsed_km"].median()), 2
                )
            else:
                enter_km_by_event[ev] = None

            if len(e_ev) and "visit_km" in e_ev.columns and e_ev["visit_km"].notna().any():
                for visit_km, vg in e_ev.groupby("visit_km", sort=True):
                    if pd.isna(visit_km):
                        continue
                    n = int(vg["runner_id"].nunique())
                    if n <= 0:
                        continue
                    rids = sorted(vg["runner_id"].astype(str).unique().tolist())
                    enters_by_visit.append(
                        {
                            "event": str(ev),
                            "visit_km": float(visit_km),
                            "enters": n,
                        }
                    )
                    sk = stream_key(str(ev), float(visit_km))
                    # One enter row per unique runner (earliest enter in window).
                    first_by_rid = (
                        vg.sort_values("t", kind="mergesort")
                        .drop_duplicates(subset=["runner_id"], keep="first")
                    )
                    visit_rows: List[Dict[str, Any]] = []
                    for _, er in first_by_rid.iterrows():
                        rid = str(er["runner_id"])
                        entry: Dict[str, Any] = {
                            "runner_id": rid,
                            "t": int(er["t"]),
                        }
                        if quintile_lookup:
                            q = quintile_lookup.get((str(ev).lower(), rid))
                            if q is not None:
                                entry["quintile"] = int(q)
                        visit_rows.append(entry)
                    visit_enters[sk] = visit_rows
                    if quintile_lookup:
                        quintile_profiles.append(
                            {
                                "event": str(ev),
                                "visit_km": float(visit_km),
                                "profile": quintile_profile_for_runners(
                                    rids, ev, quintile_lookup
                                ),
                            }
                        )

        concurrent_pairs = attach_quintile_matrices(
            build_concurrent_pairs(
                enters_by_visit, authored_movements=authored
            ),
            visit_enters,
            dwell_sec=float(MOTION_QUINTILE_PARTNER_DWELL_SEC),
        )

        # Prefer visit-cluster context so co-present streams stay visible
        # (e.g. 10k@6.27 cross with full@22.7 vs parallel with full@20.61).
        if enters_by_visit:
            context_bits = [
                f"{v['event']} {v['visit_km']:.2f}:{v['enters']}"
                for v in sorted(
                    enters_by_visit,
                    key=lambda x: (x["event"], x["visit_km"]),
                )
            ]
        else:
            context_bits = [
                f"{ev} {enter_km_by_event[ev]:.2f} km"
                for ev in event_names
                if enter_km_by_event.get(ev) is not None
                and enters_by_event.get(ev, 0) > 0
            ]
        rows.append(
            {
                "t0": int(bin_t0),
                "t1": int(bin_t1),
                "label": f"{_sec_to_clock(bin_t0)}–{_sec_to_clock(bin_t1)}",
                "enters_by_event": enters_by_event,
                "exits_by_event": exits_by_event,
                "enter_elapsed_km_by_event": enter_km_by_event,
                "enters_by_visit": enters_by_visit,
                "concurrent_pairs": concurrent_pairs,
                "quintile_profiles": quintile_profiles,
                "enter_total": int(sum(enters_by_event.values())),
                "exit_total": int(sum(exits_by_event.values())),
                "counts_display": " / ".join(
                    str(enters_by_event.get(ev, 0)) for ev in event_names
                ),
                "context": " · ".join(context_bits),
            }
        )

    # Overall totals: unique runners vs passages (enter crossings)
    totals_enter: Dict[str, int] = {}
    totals_exit: Dict[str, int] = {}
    totals_passages: Dict[str, int] = {}
    totals_km: Dict[str, Optional[float]] = {}
    for ev in event_names:
        e_ev = enters[enters["event"] == ev] if not enters.empty else enters
        x_ev = exits[exits["event"] == ev] if not exits.empty else exits
        totals_enter[ev] = int(e_ev["runner_id"].nunique()) if len(e_ev) else 0
        totals_exit[ev] = int(x_ev["runner_id"].nunique()) if len(x_ev) else 0
        totals_passages[ev] = int(len(e_ev)) if len(e_ev) else 0
        if len(e_ev) and e_ev["elapsed_km"].notna().any():
            totals_km[ev] = round(float(e_ev["elapsed_km"].median()), 2)
        else:
            totals_km[ev] = None

    visit_summary = build_visit_summary(
        episodes,
        window_sec=window,
        gap_km=visit_km_gap,
        event_names=event_names,
    )
    movement_spans = build_movement_spans(
        rows,
        window_sec=window,
        authored_movements=authored,
    )

    span_t0 = int(bin_starts[0]) if bin_starts else t0
    span_t1 = int(bin_starts[-1] + window) if bin_starts else t1

    unique_total = int(
        enters["runner_id"].nunique() if not enters.empty else 0
    )
    passages_total = int(len(enters)) if not enters.empty else 0

    return {
        "mode": "stream_passage",
        "place": {
            "place_id": pin.place_id,
            "label": pin.label,
            "lat": pin.lat,
            "lon": pin.lon,
            "radius_m": pin.radius_m,
        },
        "window_sec": window,
        "t0": span_t0,
        "t1": span_t1,
        "events": event_names,
        "legend": " / ".join(event_names) if event_names else "",
        "visit_km_gap": float(visit_km_gap),
        "count_semantics": COUNT_SEMANTICS,
        "count_semantics_note": COUNT_SEMANTICS_NOTE,
        "matrix_semantics_note": MATRIX_SEMANTICS_NOTE,
        "authored_movements": authored,
        "rows": rows,
        "visit_summary": visit_summary,
        "movement_spans": movement_spans,
        "totals": {
            "enters_by_event": totals_enter,
            "exits_by_event": totals_exit,
            "passages_by_event": totals_passages,
            "enter_elapsed_km_by_event": totals_km,
            "unique_runners_total": unique_total,
            "passages_total": passages_total,
        },
    }
