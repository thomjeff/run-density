import os, requests

BASE = os.environ.get("BASE_URL")

def test_report_contract():
    assert BASE, "BASE_URL must be set for contract test"

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

    r = requests.post(f"{BASE}/api/report", json=payload)
    r.raise_for_status()
    body = r.json()
    assert "report" in body and isinstance(body["report"], str)

    text = body["report"]
    for needle in [
        "Checking 10K vs Half from 0.00km–2.74km",
        "Start: 10K 07:20:00, Half 07:40:00",
        "Runners: 10K: 618, Half: 368",
        "Overlap Segment: 2.55km–2.74km",
        "First overlap: 07:48:15 at 2.55km",
        "Peak: 400 (260 from 10K, 140 from Half)"
    ]:
        assert needle in text, f"missing: {needle}"