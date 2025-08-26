#!/usr/bin/env python3
import argparse
import csv
import math
import os
from typing import List, Tuple, Dict, Optional

try:
    import gpxpy
    import gpxpy.gpx
except Exception as e:
    raise SystemExit("This script requires gpxpy. Activate your venv and run: pip install gpxpy")


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2*R*math.asin(math.sqrt(a))


def load_track(path: str) -> Tuple[List[Tuple[float,float]], List[float]]:
    with open(path, 'r', encoding='utf-8') as f:
        gpx = gpxpy.parse(f)
    pts: List[Tuple[float,float]] = []
    for track in gpx.tracks:
        for seg in track.segments:
            for p in seg.points:
                pts.append((p.latitude, p.longitude))
    if not pts:
        raise ValueError(f"No points found in {path}")
    # cumulative distance in meters
    dists = [0.0]
    for i in range(1, len(pts)):
        dists.append(dists[-1] + haversine(pts[i-1][0], pts[i-1][1], pts[i][0], pts[i][1]))
    return pts, dists


def resample_along(pts: List[Tuple[float,float]], dists: List[float], step_m: float) -> Tuple[List[Tuple[float,float]], List[float]]:
    total = dists[-1]
    if total == 0:
        return [pts[0]], [0.0]
    targets = [i*step_m for i in range(int(total // step_m) + 1)]
    out_pts = []
    out_s = []
    j = 1
    for s in targets:
        while j < len(dists) and dists[j] < s:
            j += 1
        if j == len(dists):
            out_pts.append(pts[-1])
            out_s.append(dists[-1])
        else:
            s0, s1 = dists[j-1], dists[j]
            if s1 == s0:
                t = 0.0
            else:
                t = (s - s0) / (s1 - s0)
            lat = pts[j-1][0] + t * (pts[j][0] - pts[j-1][0])
            lon = pts[j-1][1] + t * (pts[j][1] - pts[j-1][1])
            out_pts.append((lat, lon))
            out_s.append(s)
    return out_pts, out_s


def nearest_dist_and_s(ref_pt: Tuple[float,float], pts: List[Tuple[float,float]], dists: List[float]) -> Tuple[float,float]:
    # Linear scan; with 5–10 m steps this is fine.
    best_d = 1e18
    best_s = 0.0
    for i, q in enumerate(pts):
        d = haversine(ref_pt[0], ref_pt[1], q[0], q[1])
        if d < best_d:
            best_d = d
            best_s = dists[i]
    return best_d, best_s


def spans_from_mask(mask: List[bool], svals: List[float], bridge_m: float) -> List[Tuple[float,float]]:
    # Turn True/False mask over svals into merged [start,end] spans in meters.
    spans = []
    i = 0
    n = len(mask)
    while i < n:
        if not mask[i]:
            i += 1
            continue
        start = svals[i]
        j = i + 1
        while j < n and mask[j]:
            j += 1
        end = svals[j-1]
        spans.append([start, end])
        i = j
    # Bridge gaps shorter than bridge_m
    if bridge_m > 0 and len(spans) > 1:
        merged = [spans[0]]
        for s,e in spans[1:]:
            if s - merged[-1][1] <= bridge_m:
                merged[-1][1] = e
            else:
                merged.append([s,e])
        spans = merged
    return [(a,b) for a,b in spans if b > a]
    

def round_km_val(x_m: float, round_km: float) -> float:
    if round_km <= 0:
        return x_m / 1000.0
    step_m = round_km * 1000.0
    return round((x_m / step_m)) * round_km


def write_csv(out_path: str, rows: List[Dict[str,object]]):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fieldnames = ["kind","segment","eventA","eventB",
                  "from_km_A","to_km_A","from_km_B","to_km_B",
                  "direction","width_m","notes"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k,"") for k in fieldnames})
    print(f"✅ Wrote {len(rows)} overlaps to {out_path}")


def main():
    ap = argparse.ArgumentParser(description="Detect pairwise and triple overlaps from three GPX routes.")
    ap.add_argument("--full", required=True)
    ap.add_argument("--half", required=True)
    ap.add_argument("--tenk", required=True)
    ap.add_argument("--tolerance-m", type=float, default=1.0)
    ap.add_argument("--step-m", type=float, default=5.0, help="sampling step in meters (default 5)")
    ap.add_argument("--bridge-m", type=float, default=0.0, help="merge gaps shorter than this many meters (default 0)")
    ap.add_argument("--round-km", type=float, default=0.001, help="round output km to this step (default 0.001km)")
    ap.add_argument("--out", required=True, help="output CSV path")
    args = ap.parse_args()

    files = {"Full": args.full, "Half": args.half, "10K": args.tenk}
    tracks = {}
    samples = {}
    for name, path in files.items():
        pts, dists = load_track(path)
        spts, ss = resample_along(pts, dists, args.step_m)
        tracks[name] = (pts, dists)
        samples[name] = (spts, ss)

    def pairwise_rows(A: str, B: str) -> List[Dict[str,object]]:
        # Sample along A; find nearest on B and mark within tolerance.
        Apts, As = samples[A]
        Bpts, Bs = samples[B]  # only to use their indices for nearest lookup
        mask = []
        proj_s_on_B = []
        for p, s in zip(Apts, As):
            d, sb = nearest_dist_and_s(p, Bpts, Bs)
            mask.append(d <= args.tolerance_m)
            proj_s_on_B.append(sb)
        spans = spans_from_mask(mask, As, args.bridge_m)
        rows = []
        for a0, a1 in spans:
            # find indices covering this span
            i0 = max(0, min(range(len(As)), key=lambda i: abs(As[i]-a0)))
            i1 = max(0, min(range(len(As)), key=lambda i: abs(As[i]-a1)))
            if i1 < i0: i0, i1 = i1, i0
            b0 = proj_s_on_B[i0]
            b1 = proj_s_on_B[i1]
            rows.append({
                "kind":"pair",
                "segment":"",
                "eventA":A, "eventB":B,
                "from_km_A": round_km_val(a0, args.round_km),
                "to_km_A":   round_km_val(a1, args.round_km),
                "from_km_B": round_km_val(b0, args.round_km),
                "to_km_B":   round_km_val(b1, args.round_km),
                "direction":"", "width_m":"",
                "notes":""
            })
        return rows

    all_rows: List[Dict[str,object]] = []
    pairs = [("Full","Half"), ("Full","10K"), ("Half","10K")]
    pair_rows: Dict[Tuple[str,str], List[Dict[str,object]]] = {}
    for A,B in pairs:
        r = pairwise_rows(A,B)
        pair_rows[(A,B)] = r
        all_rows.extend(r)

    # Triple detection: use Half as reference; mark points where nearest to Full and 10K are both within tolerance.
    ref = "Half" if "Half" in samples else list(samples.keys())[0]
    Hpts, Hs = samples[ref]
    Fpts, Fs = samples["Full"]
    Kpts, Ks = samples["10K"]

    mask_triple = []
    projF = []
    projK = []
    for p in Hpts:
        dF, sF = nearest_dist_and_s(p, Fpts, Fs)
        dK, sK = nearest_dist_and_s(p, Kpts, Ks)
        ok = (dF <= args.tolerance_m) and (dK <= args.tolerance_m)
        mask_triple.append(ok)
        projF.append(sF); projK.append(sK)

    triple_spans = spans_from_mask(mask_triple, Hs, args.bridge_m)
    for h0, h1 in triple_spans:
        i0 = max(0, min(range(len(Hs)), key=lambda i: abs(Hs[i]-h0)))
        i1 = max(0, min(range(len(Hs)), key=lambda i: abs(Hs[i]-h1)))
        if i1 < i0: i0, i1 = i1, i0
        f0, f1 = projF[i0], projF[i1]
        k0, k1 = projK[i0], projK[i1]
        all_rows.append({
            "kind":"triple",
            "segment":"",
            "eventA":"Full", "eventB":"Half",
            "from_km_A": round_km_val(f0, args.round_km),
            "to_km_A":   round_km_val(f1, args.round_km),
            "from_km_B": round_km_val(h0, args.round_km),
            "to_km_B":   round_km_val(h1, args.round_km),
            "direction":"", "width_m":"",
            "notes":"also overlaps 10K in same geographic corridor"
        })
        all_rows.append({
            "kind":"triple",
            "segment":"",
            "eventA":"Full", "eventB":"10K",
            "from_km_A": round_km_val(f0, args.round_km),
            "to_km_A":   round_km_val(f1, args.round_km),
            "from_km_B": round_km_val(k0, args.round_km),
            "to_km_B":   round_km_val(k1, args.round_km),
            "direction":"", "width_m":"",
            "notes":"also overlaps Half in same geographic corridor"
        })
        all_rows.append({
            "kind":"triple",
            "segment":"",
            "eventA":"Half", "eventB":"10K",
            "from_km_A": round_km_val(h0, args.round_km),
            "to_km_A":   round_km_val(h1, args.round_km),
            "from_km_B": round_km_val(k0, args.round_km),
            "to_km_B":   round_km_val(k1, args.round_km),
            "direction":"", "width_m":"",
            "notes":"also overlaps Full in same geographic corridor"
        })

    # Start-corridor auto-detect: find earliest triple span beginning near 0.0; if none,
    # check first 300m for proximity and emit a best-effort triple from 0 to first break.
    has_near_zero_triple = any(a <= 5.0 for (_, a) in [(s, s) for s,_ in triple_spans])
    if not has_near_zero_triple:
        limit_m = 300.0
        mask0 = []
        for p, s in zip(Hpts, Hs):
            if s > limit_m:
                mask0.append(False)
                continue
            dF, _ = nearest_dist_and_s(p, Fpts, Fs)
            dK, _ = nearest_dist_and_s(p, Kpts, Ks)
            mask0.append((dF <= args.tolerance_m) and (dK <= args.tolerance_m))
        spans0 = spans_from_mask(mask0, Hs, args.bridge_m)
        if spans0:
            h0, h1 = spans0[0]
            i0 = max(0, min(range(len(Hs)), key=lambda i: abs(Hs[i]-h0)))
            i1 = max(0, min(range(len(Hs)), key=lambda i: abs(Hs[i]-h1)))
            f0 = projF[i0]; f1 = projF[i1]
            k0 = projK[i0]; k1 = projK[i1]
            for (A,B,(a0,a1),(b0,b1),note) in [
                ("Full","Half",(f0,f1),(h0,h1),"start triple-corridor"),
                ("Full","10K",(f0,f1),(k0,k1),"start triple-corridor"),
                ("Half","10K",(h0,h1),(k0,k1),"start triple-corridor"),
            ]:
                all_rows.append({
                    "kind":"triple",
                    "segment":"",
                    "eventA":A, "eventB":B,
                    "from_km_A": round_km_val(a0, args.round_km),
                    "to_km_A":   round_km_val(a1, args.round_km),
                    "from_km_B": round_km_val(b0, args.round_km),
                    "to_km_B":   round_km_val(b1, args.round_km),
                    "direction":"", "width_m":"",
                    "notes":note
                })

    write_csv(args.out, all_rows)


if __name__ == "__main__":
    main()
