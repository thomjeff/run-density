import os, json, requests, jsonschema

BASE = os.environ.get("BASE_URL", "http://localhost:8080")

DENSITY_SCHEMA = json.load(open(os.path.join(os.path.dirname(__file__), "../schemas/density_response.schema.json")))
OVERLAP_SCHEMA = json.load(open(os.path.join(os.path.dirname(__file__), "../schemas/overlap_response.schema.json")))

def test_health_ready():
    r = requests.get(f"{BASE}/health"); r.raise_for_status()
    assert r.json().get("ok") is True
    r = requests.get(f"{BASE}/ready"); r.raise_for_status()
    j = r.json()
    assert j.get("ok") is True and j.get("density_loaded") and j.get("overlap_loaded")

def test_density_contract():
    payload = {
        "paceCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv",
        "startTimes":{"10K":440,"Half":460},
        "segments":[
            "10K,Half,0.00,2.74,3.0,uni",
            "10K,,2.74,5.80,1.5,bi",
            {"eventA":"10K","eventB":"Half","from":5.81,"to":8.10,"width":3.0,"direction":"uni"}
        ],
        "stepKm":0.03,
        "timeWindow":60
    }
    r = requests.post(f"{BASE}/api/density", json=payload); r.raise_for_status()
    j = r.json()
    jsonschema.validate(j, DENSITY_SCHEMA)
    assert j["ok"] is True and j["engine"] == "density"

def test_overlap_contract():
    payload = {
        "paceCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv",
        "startTimes":{"10K":440,"Half":460},
        "eventA":"10K","eventB":"Half",
        "from":0.00,"to":2.74,
        "stepKm":0.03,"timeWindow":60
    }
    r = requests.post(f"{BASE}/api/overlap", json=payload); r.raise_for_status()
    j = r.json()
    jsonschema.validate(j, OVERLAP_SCHEMA)
    assert j["ok"] is True and j["engine"] == "overlap"
