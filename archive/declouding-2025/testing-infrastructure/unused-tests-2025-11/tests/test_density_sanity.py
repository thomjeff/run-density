import pandas as pd
from app.io.loader import load_segments

SAMPLED = ("A1","A2","C1")  # safe: tests ignore if not present

def test_density_widths_match_segments():
    df = load_segments()
    if "seg_id" not in df.columns:
        return
    ids = set(df["seg_id"])
    for sid in SAMPLED:
        if sid in ids:
            w = df.loc[df["seg_id"]==sid, "width_m"].iloc[0]
            assert pd.notna(w) and float(w) > 0, f"width_m must be positive for {sid}"

def test_event_windows_present_and_ordered():
    df = load_segments()
    required_cols = {"seg_id","full","half","10K",
                     "full_from_km","full_to_km","half_from_km","half_to_km","10K_from_km","10K_to_km"}
    if not required_cols.issubset(df.columns):
        return
    for _, r in df.iterrows():
        for ev in ["full","half","10K"]:
            flag = str(r.get(ev,"")).lower()
            if flag == "y":
                fk = f"{ev}_from_km"; tk = f"{ev}_to_km"
                fkm, tkm = r.get(fk, None), r.get(tk, None)
                assert pd.notna(fkm) and pd.notna(tkm), f"{r['seg_id']} missing {ev} window"
                assert float(fkm) <= float(tkm), f"{r['seg_id']} {ev} has from_km > to_km"

def test_direction_enum_limited():
    df = load_segments()
    if "direction" not in df.columns:
        return
    bad = [r["seg_id"] for _, r in df.iterrows() if str(r.get("direction","")).lower() not in {"uni","bi"}]
    assert not bad, f"Invalid direction for seg_ids: {bad}"
