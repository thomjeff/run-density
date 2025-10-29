"""
API Routes for E2E Report Generation

🚧 INTERNAL / EXPERIMENTAL

The `/api/e2e/run` endpoint was added as a prototype to trigger report generation inside 
the Cloud Run container (e.g. when SSH isn't available). 

However, it is **NOT used in CI** due to deadlock risks under single-threaded gunicorn.

In the future, this route (or a replacement) could support:
✅ Triggering a new analysis with a custom runners.csv
✅ Allowing users to define event times or filter criteria

Until then, this module is considered *experimental* and not production-critical.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import logging
import subprocess
import os
from pathlib import Path
import json
from typing import Tuple

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


def _detect_environment() -> Tuple[bool, str]:
    """
    Detect the current environment (Cloud Run vs Local).
    
    Returns:
        Tuple of (is_cloud: bool, environment_name: str)
    """
    is_cloud = bool(os.getenv('K_SERVICE') or os.getenv('GOOGLE_CLOUD_PROJECT'))
    environment = "Cloud Run" if is_cloud else "Local"
    return is_cloud, environment


@router.post("/api/e2e/run")
async def run_e2e():
    """
    🚧 Experimental - Not used in CI
    
    Trigger E2E report generation in the current environment.
    
    Originally created to trigger `e2e.py` inside Cloud Run. 
    Causes deadlocks in single-worker deployments and has been deprecated from CI use.
    
    This endpoint:
    1. Runs the E2E pipeline locally (within Cloud Run or local server)
    2. Generates reports and artifacts
    3. Returns status and file listing
    
    Returns:
        Status of E2E run with file counts and locations
    """
    try:
        logger.info("=== Starting E2E report generation ===")
        
        # Detect environment using utility function
        is_cloud, environment = _detect_environment()
        
        logger.info(f"Environment: {environment}")
        
        # Debug: List files in /app to verify e2e.py was copied
        try:
            app_files = os.listdir("/app")
            logger.info(f"Files in /app: {sorted(app_files)[:20]}")  # First 20 files
            e2e_exists = "e2e.py" in app_files
            logger.info(f"e2e.py exists in /app: {e2e_exists}")
        except Exception as e:
            logger.warning(f"Could not list /app directory: {e}")
        
        # Run e2e.py (without --cloud flag, so it generates locally)
        # In Cloud Run, e2e.py is at /app/e2e.py (from Dockerfile COPY)
        logger.info("Running python e2e.py...")
        result = subprocess.run(
            ["python", "/app/e2e.py"],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
            cwd="/app"  # Ensure working directory is /app
        )
        
        if result.returncode != 0:
            logger.error(f"E2E run failed: {result.stderr}")
            raise HTTPException(
                status_code=500, 
                detail=f"E2E execution failed: {result.stderr[:500]}"
            )
        
        logger.info("E2E completed successfully")
        
        # Check what was generated
        reports_dir = Path("reports")
        artifacts_dir = Path("artifacts")
        
        # Find latest report directory
        latest_report_dir = None
        if reports_dir.exists():
            report_dirs = sorted([d for d in reports_dir.iterdir() if d.is_dir()], reverse=True)
            if report_dirs:
                latest_report_dir = report_dirs[0]
        
        # Find latest artifact directory
        latest_artifact_dir = None
        if artifacts_dir.exists():
            artifact_dirs = sorted([d for d in artifacts_dir.iterdir() if d.is_dir() and d.name != "ui"], reverse=True)
            if artifact_dirs:
                latest_artifact_dir = artifact_dirs[0]
        
        # Count files generated
        report_files = []
        if latest_report_dir and latest_report_dir.exists():
            report_files = [f.name for f in latest_report_dir.iterdir() if f.is_file()]
        
        artifact_files = []
        if latest_artifact_dir and latest_artifact_dir.exists():
            ui_dir = latest_artifact_dir / "ui"
            if ui_dir.exists():
                artifact_files = [f.name for f in ui_dir.iterdir() if f.is_file()]
        
        # Check for latest.json
        latest_json_exists = (artifacts_dir / "latest.json").exists()
        latest_json_content = None
        if latest_json_exists:
            try:
                latest_json_content = json.loads((artifacts_dir / "latest.json").read_text())
            except Exception as e:
                logger.warning(f"Could not read latest.json: {e}")
        
        response = {
            "status": "success",
            "environment": environment,
            "is_cloud": is_cloud,
            "stdout": result.stdout[-1000:] if result.stdout else "",  # Last 1000 chars
            "generation": {
                "latest_report_dir": str(latest_report_dir) if latest_report_dir else None,
                "report_files_count": len(report_files),
                "report_files": report_files[:10],  # First 10 files
                "latest_artifact_dir": str(latest_artifact_dir) if latest_artifact_dir else None,
                "artifact_files_count": len(artifact_files),
                "artifact_files": artifact_files,
                "latest_json_exists": latest_json_exists,
                "latest_json_content": latest_json_content
            },
            "next_steps": []
        }
        
        # Add next steps based on environment
        if is_cloud:
            response["next_steps"].append("Files generated locally in Cloud Run container (ephemeral)")
            response["next_steps"].append("Need to upload to GCS for persistence")
            response["next_steps"].append("Use /api/e2e/upload to persist to GCS")
        else:
            response["next_steps"].append("Files generated locally on filesystem")
            response["next_steps"].append("Available immediately to local APIs")
        
        logger.info(f"Generated {len(report_files)} reports, {len(artifact_files)} artifacts")
        
        return JSONResponse(content=response)
        
    except subprocess.TimeoutExpired:
        logger.error("E2E run timed out after 10 minutes")
        raise HTTPException(status_code=504, detail="E2E execution timed out")
    except Exception as e:
        logger.error(f"Error running E2E: {e}")
        raise HTTPException(status_code=500, detail=f"E2E execution error: {str(e)}")


def _upload_latest_json(latest_json: Path, upload_results: dict) -> None:
    """Upload latest.json to GCS."""
    if not latest_json.exists():
        return
    
    try:
        result = subprocess.run(
            ["gsutil", "cp", str(latest_json), "gs://run-density-reports/artifacts/latest.json"],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            upload_results["latest_json_uploaded"] = True
            logger.info("Uploaded artifacts/latest.json")
        else:
            upload_results["errors"].append(f"Failed to upload latest.json: {result.stderr}")
    except Exception as e:
        upload_results["errors"].append(f"Error uploading latest.json: {str(e)}")


def _get_run_id_from_latest_json(latest_json: Path) -> str:
    """Get run_id from latest.json, falling back to today's date."""
    run_id = None
    if latest_json.exists():
        try:
            data = json.loads(latest_json.read_text())
            run_id = data.get("run_id")
        except Exception as e:
            logger.warning(f"Could not read run_id from latest.json: {e}")
    
    if not run_id:
        logger.warning("No run_id found, using today's date")
        from datetime import datetime
        run_id = datetime.now().strftime("%Y-%m-%d")
    
    return run_id


def _upload_reports_directory(report_dir: Path, run_id: str, upload_results: dict) -> None:
    """Upload reports directory to GCS."""
    if not report_dir.exists():
        return
    
    try:
        result = subprocess.run(
            ["gsutil", "-m", "cp", "-r", f"{report_dir}/*", f"gs://run-density-reports/reports/{run_id}/"],
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode == 0:
            file_count = len(list(report_dir.iterdir()))
            upload_results["reports_uploaded"] = file_count
            logger.info(f"Uploaded {file_count} report files")
        else:
            upload_results["errors"].append(f"Failed to upload reports: {result.stderr}")
    except Exception as e:
        upload_results["errors"].append(f"Error uploading reports: {str(e)}")


def _upload_artifacts_directory(artifact_ui_dir: Path, run_id: str, upload_results: dict) -> None:
    """Upload artifacts directory to GCS."""
    if not artifact_ui_dir.exists():
        return
    
    try:
        result = subprocess.run(
            ["gsutil", "-m", "cp", "-r", f"{artifact_ui_dir}/*", f"gs://run-density-reports/artifacts/{run_id}/ui/"],
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode == 0:
            file_count = len(list(artifact_ui_dir.iterdir()))
            upload_results["artifacts_uploaded"] = file_count
            logger.info(f"Uploaded {file_count} artifact files")
        else:
            upload_results["errors"].append(f"Failed to upload artifacts: {result.stderr}")
    except Exception as e:
        upload_results["errors"].append(f"Error uploading artifacts: {str(e)}")


@router.post("/api/e2e/upload")
async def upload_e2e_results():
    """
    Upload E2E-generated reports and artifacts to GCS.
    
    This endpoint:
    1. Finds the latest generated reports and artifacts
    2. Uploads them to Google Cloud Storage
    3. Returns upload status
    
    Only works in Cloud Run environment.
    
    Returns:
        Status of GCS upload with file counts
    """
    try:
        # Check if we're in Cloud Run
        is_cloud, environment = _detect_environment()
        if not is_cloud:
            return JSONResponse(content={
                "status": "skipped",
                "reason": "Not in Cloud Run environment - files already local"
            })
        
        logger.info("=== Uploading E2E results to GCS ===")
        
        # Find latest directories
        reports_dir = Path("reports")
        artifacts_dir = Path("artifacts")
        
        upload_results = {
            "reports_uploaded": 0,
            "artifacts_uploaded": 0,
            "latest_json_uploaded": False,
            "errors": []
        }
        
        # Upload latest.json
        latest_json = artifacts_dir / "latest.json"
        _upload_latest_json(latest_json, upload_results)
        
        # Get run_id from latest.json
        run_id = _get_run_id_from_latest_json(latest_json)
        
        # Upload reports
        report_dir = reports_dir / run_id
        _upload_reports_directory(report_dir, run_id, upload_results)
        
        # Upload artifacts
        artifact_ui_dir = artifacts_dir / run_id / "ui"
        _upload_artifacts_directory(artifact_ui_dir, run_id, upload_results)
        
        response = {
            "status": "success" if not upload_results["errors"] else "partial",
            "run_id": run_id,
            "uploads": upload_results
        }
        
        logger.info(f"Upload complete: {upload_results['reports_uploaded']} reports, {upload_results['artifacts_uploaded']} artifacts")
        
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"Error uploading to GCS: {e}")
        raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")


@router.get("/api/e2e/status")
async def get_e2e_status():
    """
    Get status of E2E reports and artifacts in current environment.
    
    Returns:
        Current state of reports and artifacts (local and GCS)
    """
    try:
        # Detect environment using utility function
        is_cloud, environment = _detect_environment()
        
        reports_dir = Path("reports")
        artifacts_dir = Path("artifacts")
        
        # Local filesystem status
        local_status = {
            "reports_dir_exists": reports_dir.exists(),
            "artifacts_dir_exists": artifacts_dir.exists(),
            "latest_json_exists": (artifacts_dir / "latest.json").exists(),
            "report_dates": [],
            "artifact_dates": []
        }
        
        if reports_dir.exists():
            local_status["report_dates"] = sorted([d.name for d in reports_dir.iterdir() if d.is_dir()], reverse=True)[:5]
        
        if artifacts_dir.exists():
            local_status["artifact_dates"] = sorted([d.name for d in artifacts_dir.iterdir() if d.is_dir() and d.name != "ui"], reverse=True)[:5]
        
        # GCS status (if in cloud)
        gcs_status = None
        if is_cloud:
            try:
                # Check for latest.json in GCS
                result = subprocess.run(
                    ["gsutil", "ls", "gs://run-density-reports/artifacts/latest.json"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                gcs_latest_exists = result.returncode == 0
                
                gcs_status = {
                    "latest_json_exists": gcs_latest_exists,
                    "accessible": True
                }
            except Exception as e:
                gcs_status = {
                    "accessible": False,
                    "error": str(e)
                }
        
        response = {
            "environment": environment,
            "is_cloud": is_cloud,
            "local": local_status,
            "gcs": gcs_status
        }
        
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"Error getting E2E status: {e}")
        raise HTTPException(status_code=500, detail=f"Status check error: {str(e)}")


