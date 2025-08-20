import requests
import pytest

BASE_URL = ""  # fill with deployed URL or override via env

@pytest.mark.skipif(BASE_URL == "", reason="No BASE_URL configured")
def test_report_contract():
    payload = {
        "eventA":"10K","eventB":"Half",
        "from":0.00,"to":2.74,
        "segment_name":"A",
        "segment_label":"Start to Friel",
        "direction":"uni","width_m":3.0,
        "startTimes":{"10K":1200,"Half":2400},
        "startTimesClock":{"10K":"07:20:00","Half":"07:40:00"},
        "runnersA":618,"runnersB":368,
        "overlap_from_km":2.55,"overlap_to_km":2.74,
        "first_overlap_clock":"07:48:15",
        "first_overlap_km":2.55,
        "first_overlap_bibA":"1617","first_overlap_bibB":"1681",
        "peak":{"km":1.80,"A":260,"B":140,"combined":400,"areal_density":2.20}
    }
    resp = requests.post(f"{BASE_URL}/api/report", json=payload)
    data = resp.json()
    assert "report" in data
    report = data["report"]
    assert "Checking 10K vs Half" in report
    assert "Runners:" in report
