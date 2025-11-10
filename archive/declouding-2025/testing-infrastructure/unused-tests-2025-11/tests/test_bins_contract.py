import os, re, json, gzip, glob
from pathlib import Path

REQUIRED_PROPS = ["bin_id","segment_id","start_km","end_km","t_start","t_end","density","flow","los_class","bin_size_km"]

def _latest_day(reports_dir: Path) -> Path:
    days = [p for p in reports_dir.iterdir() if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name)]
    assert days, f"No YYYY-MM-DD folders under {reports_dir}"
    return sorted(days)[-1]

def test_bins_exist_and_nonzero():
    reports_dir = Path(os.getenv("REPORTS_DIR", "./reports")).resolve()
    day = _latest_day(reports_dir)
    geo = next(iter(glob.glob(str(day / "*.geojson.gz"))), None)
    parq = next(iter(glob.glob(str(day / "*.parquet"))), None)
    assert geo and parq, f"Missing artifacts in {day} (geojson={bool(geo)} parquet={bool(parq)})"

    with gzip.open(geo, "rb") as f:
        fc = json.loads(f.read().decode("utf-8"))
    feats = fc.get("features") or []
    md = fc.get("metadata") or {}
    assert len(feats) > 0, "zero features"
    assert (md.get("occupied_bins", 0) > 0) and (md.get("nonzero_density_bins", 0) > 0), "empty occupancy"

    # Parquet count must match
    try:
        import pyarrow.parquet as pq
    except ModuleNotFoundError:
        raise AssertionError("pyarrow not installed; required for this test")
    table = pq.read_table(parq)
    assert table.num_rows == len(feats), "parquet rows != geojson features"

    # Required properties present
    props = feats[0].get("properties") or {}
    missing = [k for k in REQUIRED_PROPS if k not in props]
    assert not missing, f"missing properties on first feature: {missing}"
