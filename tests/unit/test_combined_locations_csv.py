"""Issue #749: run-level combined Locations.csv."""

import pandas as pd

from app.core.v2.reports import write_combined_locations_csv


def test_write_combined_locations_csv_none_when_no_day_reports(tmp_path):
    run_dir = tmp_path / "rid"
    run_dir.mkdir()
    assert write_combined_locations_csv(run_dir) is None


def test_write_combined_orders_by_day_then_loc_id(tmp_path):
    run_dir = tmp_path / "runid"
    # Intentionally create sun before sat to prove order comes from DAY_ORDER, not disk
    for day, loc_ids in [("sun", [10, 5]), ("sat", [3, 1])]:
        d = run_dir / day / "reports"
        d.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(
            {
                "loc_id": loc_ids,
                "loc_label": [f"L{i}" for i in loc_ids],
                "loc_type": ["course"] * len(loc_ids),
            }
        )
        df.to_csv(d / "Locations.csv", index=False)

    out = write_combined_locations_csv(run_dir)
    assert out is not None
    assert out == run_dir / "Locations.csv"
    comb = pd.read_csv(out)
    assert list(comb["day"]) == ["sat", "sat", "sun", "sun"]
    assert list(comb["loc_id"]) == [1, 3, 5, 10]
    # day column immediately after loc_label
    assert list(comb.columns[:3]) == ["loc_id", "loc_label", "day"]


def test_normalization_inserts_day_from_path(tmp_path):
    run_dir = tmp_path / "runid"
    d = run_dir / "fri" / "reports"
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "loc_id": [1],
            "loc_label": ["A"],
            "loc_type": ["course"],
        }
    ).to_csv(d / "Locations.csv", index=False)

    out = write_combined_locations_csv(run_dir)
    comb = pd.read_csv(out)
    assert comb["day"].tolist() == ["fri"]
