from pathlib import Path
import json, subprocess, sys

def test_validate_script_runs():
    result = subprocess.run([sys.executable, "frontend/validation/scripts/validate_data.py"], capture_output=True, text=True)
    assert result.returncode in (0,2)
    report = json.loads(Path("frontend/validation/output/validation_report.json").read_text())
    assert "run_hash" in report
    assert "files" in report
    assert Path("frontend/validation/output/provenance_snippet.html").exists()

def test_bad_id_detected(tmp_path, monkeypatch):
    # copy files into tmp and break IDs
    tmp = tmp_path
    (tmp / "data").mkdir()
    (tmp / "frontend" / "validation" / "output").mkdir(parents=True)
    # copy fixture data
    for f in ("segments.geojson","segment_metrics.json","flags.json","meta.json"):
        (tmp / "data" / f).write_text(Path(f"data/{f}").read_text())

    # mutate metrics to use an unknown segment id
    mm = json.loads((tmp / "data" / "segment_metrics.json").read_text())
    mm["items"][0]["segment_id"] = "UNKNOWN"
    (tmp / "data" / "segment_metrics.json").write_text(json.dumps(mm))

    # run script from tmp CWD
    cwd = Path.cwd()
    try:
        import shutil
        # Copy __init__.py files to make proper packages
        (tmp / "frontend").mkdir(exist_ok=True)
        (tmp / "frontend" / "validation").mkdir(exist_ok=True)
        (tmp / "frontend" / "validation" / "scripts").mkdir(exist_ok=True)
        (tmp / "frontend" / "validation" / "data_contracts").mkdir(exist_ok=True)
        (tmp / "frontend" / "validation" / "templates").mkdir(exist_ok=True)
        
        # Copy __init__.py files
        shutil.copy("frontend/__init__.py", tmp / "frontend" / "__init__.py")
        shutil.copy("frontend/validation/__init__.py", tmp / "frontend" / "validation" / "__init__.py")
        shutil.copy("frontend/validation/scripts/__init__.py", tmp / "frontend" / "validation" / "scripts" / "__init__.py")
        shutil.copy("frontend/validation/data_contracts/__init__.py", tmp / "frontend" / "validation" / "data_contracts" / "__init__.py")
        
        # Copy Python files
        shutil.copy("frontend/validation/scripts/validate_data.py", tmp / "validate_data.py")
        shutil.copy("frontend/validation/scripts/compute_hash.py", tmp / "frontend" / "validation" / "scripts" / "compute_hash.py")
        shutil.copy("frontend/validation/scripts/write_provenance_badge.py", tmp / "frontend" / "validation" / "scripts" / "write_provenance_badge.py")
        shutil.copy("frontend/validation/data_contracts/schemas.py", tmp / "frontend" / "validation" / "data_contracts" / "schemas.py")
        
        # Copy template
        (tmp / "frontend" / "validation" / "templates" / "_provenance.html").write_text(Path("frontend/validation/templates/_provenance.html").read_text())
        from subprocess import run
        r = run([sys.executable, "validate_data.py"], cwd=tmp, capture_output=True, text=True)
        assert r.returncode == 2
        report = json.loads((tmp / "frontend" / "validation" / "output" / "validation_report.json").read_text())
        assert report["status"] == "Failed"
        assert any("IDs present" in e for e in report["errors"])
    finally:
        pass
