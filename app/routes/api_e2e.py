"""
API Routes for E2E Report Generation

Provides endpoint to trigger E2E report generation within the current environment.
Useful for Cloud Run to generate reports and upload to GCS.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import logging
import subprocess
import os
from pathlib import Path
import json

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.post("/api/e2e/run")
async def run_e2e():
    """
    Trigger E2E report generation in the current environment.
    
    This endpoint:
    1. Runs the E2E pipeline locally (within Cloud Run or local server)
    2. Generates reports and artifacts
    3. Returns status and file listing
    
    Returns:
        Status of E2E run with file counts and locations
    """
    try:
        logger.info("=== Starting E2E report generation ===")
        
        # Detect environment
        is_cloud = bool(os.getenv('K_SERVICE') or os.getenv('GOOGLE_CLOUD_PROJECT'))
        environment = "Cloud Run" if is_cloud else "Local"
        
        logger.info(f"Environment: {environment}")
        
        # Run e2e.py (without --cloud flag, so it generates locally)
        logger.info("Running python e2e.py...")
        result = subprocess.run(
            ["python", "e2e.py"],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
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
        is_cloud = bool(os.getenv('K_SERVICE') or os.getenv('GOOGLE_CLOUD_PROJECT'))
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
        if latest_json.exists():
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
        
        # Get run_id from latest.json
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
        
        # Upload reports
        report_dir = reports_dir / run_id
        if report_dir.exists():
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
        
        # Upload artifacts
        artifact_ui_dir = artifacts_dir / run_id / "ui"
        if artifact_ui_dir.exists():
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
        is_cloud = bool(os.getenv('K_SERVICE') or os.getenv('GOOGLE_CLOUD_PROJECT'))
        environment = "Cloud Run" if is_cloud else "Local"
        
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

