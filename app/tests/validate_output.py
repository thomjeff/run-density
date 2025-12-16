"""
Output Validation Module - Issue #467 Phase 3

This module provides automated validation for run outputs, ensuring:
- All expected files are present
- Files conform to expected schemas
- APIs serve from correct run_id directories
- latest.json points to valid run

Automates the manual checks from docs/ui-testing-checklist.md at the API layer.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import logging

import yaml
import pandas as pd
import requests

# Configure logging
logging.basicConfig(
    format='%(levelname)s:%(name)s:%(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Add stderr handler for errors
error_handler = logging.StreamHandler(sys.stderr)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter('[ERROR] %(name)s: %(message)s'))
logger.addHandler(error_handler)

VALIDATOR_VERSION = "1.0.0"


def load_validation_config() -> Dict[str, Any]:
    """Load validation configuration from config/reporting.yml"""
    config_path = Path("config/reporting.yml")
    
    if not config_path.exists():
        logger.error(f"❌ Config Missing — File: {config_path}")
        raise FileNotFoundError(f"Validation config not found: {config_path}")
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config


def get_latest_run_id() -> str:
    """Get the latest run_id from runflow/latest.json"""
    latest_path = Path("runflow/latest.json")
    
    if not latest_path.exists():
        logger.error(f"❌ latest.json Missing — File: {latest_path}")
        raise FileNotFoundError("runflow/latest.json not found")
    
    try:
        latest = json.loads(latest_path.read_text())
        run_id = latest.get('run_id')
        
        if not run_id:
            logger.error(f"❌ latest.json Invalid — Missing 'run_id' field")
            raise ValueError("latest.json missing 'run_id' field")
        
        return run_id
    except json.JSONDecodeError as e:
        logger.error(f"❌ latest.json Corrupt — Error: {e}")
        raise


def validate_latest_pointer() -> Dict[str, Any]:
    """
    Verify latest.json points to the most recent valid run.
    
    Checks:
    1. latest.json exists and is valid JSON
    2. run_id in latest.json exists as directory
    3. run_id matches most recent entry in index.json
    """
    logger.info("🔍 Validating latest.json integrity...")
    
    # Read latest.json
    latest_run_id = get_latest_run_id()
    
    # Verify directory exists
    run_dir = Path(f"runflow/{latest_run_id}")
    if not run_dir.exists():
        logger.error(f"❌ Run Directory Missing — Run: {latest_run_id} — Path: {run_dir}")
        return {
            'status': 'FAIL',
            'error': f'Directory not found: {run_dir}',
            'run_id': latest_run_id
        }
    
    # Verify matches index.json (most recent entry)
    index_path = Path("runflow/index.json")
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text())
            if index and len(index) > 0:
                most_recent = index[-1]['run_id']
                
                if latest_run_id != most_recent:
                    logger.error(
                        f"❌ latest.json Mismatch — "
                        f"latest.json: {latest_run_id} — "
                        f"index.json: {most_recent}"
                    )
                    return {
                        'status': 'FAIL',
                        'error': 'latest.json out of sync with index.json',
                        'latest_json': latest_run_id,
                        'index_json': most_recent
                    }
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.warning(f"⚠️ Could not validate against index.json: {e}")
    
    logger.info(f"✅ latest.json Valid — Run: {latest_run_id}")
    return {'status': 'PASS', 'run_id': latest_run_id}


def validate_file_presence(run_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify all expected files exist in runflow/{run_id}/.
    
    Uses config/reporting.yml for expected file lists.
    Returns dict with status, missing files list.
    """
    logger.info(f"🔍 Validating file presence — Run: {run_id}")
    
    run_dir = Path(f"runflow/{run_id}")
    missing = []
    found_counts = {'reports': 0, 'bins': 0, 'maps': 0, 'heatmaps': 0, 'ui': 0}
    
    validation_config = config.get('validation', {})
    
    # Check critical files
    critical = validation_config.get('critical', {})
    for category, files in critical.items():
        if isinstance(files, list):
            for file_name in files:
                file_path = run_dir / category / file_name
                if file_path.exists():
                    found_counts[category] = found_counts.get(category, 0) + 1
                else:
                    missing.append(str(file_path))
                    logger.error(f"❌ Critical File Missing — File: {file_path} — Run: {run_id}")
    
    # Check required files
    required = validation_config.get('required', {})
    for category, files in required.items():
        if isinstance(files, list):
            for file_name in files:
                file_path = run_dir / category / file_name
                if file_path.exists():
                    found_counts[category] = found_counts.get(category, 0) + 1
                else:
                    missing.append(str(file_path))
                    logger.warning(f"⚠️ Required File Missing — File: {file_path} — Run: {run_id}")
        elif isinstance(files, dict):
            # Handle heatmaps with count
            if category == 'heatmaps':
                heatmap_dir = run_dir / 'ui' / 'heatmaps'
                if heatmap_dir.exists():
                    png_files = list(heatmap_dir.glob('*.png'))
                    found_counts['heatmaps'] = len(png_files)
                    expected_count = files.get('count', 0)
                    if len(png_files) < expected_count:
                        logger.warning(
                            f"⚠️ Heatmap Count Mismatch — "
                            f"Expected: {expected_count} — Found: {len(png_files)} — Run: {run_id}"
                        )
                else:
                    missing.append(str(heatmap_dir))
                    logger.warning(f"⚠️ Heatmaps Directory Missing — Path: {heatmap_dir} — Run: {run_id}")
    
    # Check optional files (informational only)
    optional = validation_config.get('optional', {})
    for category, files in optional.items():
        if isinstance(files, list):
            for file_name in files:
                file_path = run_dir / category / file_name
                if file_path.exists():
                    found_counts[category] = found_counts.get(category, 0) + 1
                # Don't add to missing for optional files, just count
    
    # Determine status
    if missing and any(str(m) for m in missing if 'critical' in str(m).lower()):
        status = 'FAIL'
    elif missing:
        status = 'PARTIAL'
    else:
        status = 'PASS'
    
    expected_counts = config.get('expected_counts', {})
    
    if status == 'PASS':
        logger.info(f"✅ File Presence — Status: PASS — Files: {sum(found_counts.values())} — Run: {run_id}")
    elif status == 'PARTIAL':
        logger.warning(f"⚠️ File Presence — Status: PARTIAL — Missing: {len(missing)} — Run: {run_id}")
    
    return {
        'status': status,
        'missing': missing,
        'found_counts': found_counts,
        'expected_counts': expected_counts
    }


def validate_api_consistency(run_id: str, base_url: str = 'http://localhost:8080') -> Dict[str, Any]:
    """
    Verify all APIs serve from correct runflow/{run_id}/ directories.
    
    Checks:
    1. APIs return correct run_id
    2. File paths in responses contain run_id
    3. Files at those paths are accessible
    """
    logger.info(f"🔍 Validating API consistency — Run: {run_id}")
    
    errors = []
    
    # APIs to check
    api_checks = [
        {
            'name': 'Dashboard API',
            'endpoint': '/api/dashboard/summary',
            'check_type': 'run_id_field',
            'field': 'run_id'
        },
        {
            'name': 'Reports API',
            'endpoint': '/api/reports/list',
            'check_type': 'paths_contain_run_id',
            'field': 'path'
        }
    ]
    
    apis_checked = 0
    
    for api in api_checks:
        try:
            response = requests.get(f"{base_url}{api['endpoint']}", timeout=5)
            
            if response.status_code != 200:
                errors.append(f"{api['name']}: HTTP {response.status_code}")
                logger.error(
                    f"❌ API Error — API: {api['name']} — "
                    f"Status: {response.status_code} — Run: {run_id}"
                )
                continue
            
            data = response.json()
            
            # Check run_id field
            if api['check_type'] == 'run_id_field':
                actual_run_id = data.get(api['field'])
                if actual_run_id != run_id:
                    errors.append(
                        f"{api['name']}: run_id mismatch (got {actual_run_id}, expected {run_id})"
                    )
                    logger.error(
                        f"❌ API Mismatch — API: {api['name']} — "
                        f"Expected: {run_id} — Got: {actual_run_id}"
                    )
                else:
                    apis_checked += 1
            
            # Check paths contain run_id
            elif api['check_type'] == 'paths_contain_run_id':
                if isinstance(data, list) and len(data) > 0:
                    # Filter to only report files (exclude data files which are static)
                    report_items = [item for item in data if item.get('type') == 'report']
                    paths = [item.get(api['field']) for item in report_items if api['field'] in item]
                    
                    # Check if all report paths contain the run_id
                    invalid_paths = [p for p in paths if p and run_id not in str(p)]
                    
                    if invalid_paths:
                        errors.append(f"{api['name']}: {len(invalid_paths)} paths missing run_id")
                        logger.error(
                            f"❌ API Path Mismatch — API: {api['name']} — "
                            f"Invalid paths: {invalid_paths} — Run: {run_id}"
                        )
                    else:
                        apis_checked += 1
        
        except requests.RequestException as e:
            errors.append(f"{api['name']}: {str(e)}")
            logger.error(f"❌ API Request Failed — API: {api['name']} — Error: {e} — Run: {run_id}")
        except Exception as e:
            errors.append(f"{api['name']}: {str(e)}")
            logger.error(f"❌ API Check Failed — API: {api['name']} — Error: {e} — Run: {run_id}")
    
    # Verify key files are accessible
    files_to_check = [
        f'runflow/{run_id}/ui/segment_metrics.json',
        f'runflow/{run_id}/ui/flags.json',
        f'runflow/{run_id}/reports/Density.md',
    ]
    
    for file_path in files_to_check:
        if not Path(file_path).exists():
            errors.append(f"File not accessible: {file_path}")
            logger.error(f"❌ File Not Accessible — File: {file_path} — Run: {run_id}")
    
    status = 'PASS' if len(errors) == 0 else 'FAIL'
    
    if status == 'PASS':
        logger.info(f"✅ API Consistency — Status: PASS — APIs: {apis_checked} — Run: {run_id}")
    else:
        logger.error(f"❌ API Consistency — Status: FAIL — Errors: {len(errors)} — Run: {run_id}")
    
    return {
        'status': status,
        'apis_checked': apis_checked,
        'errors': errors,
        'all_paths_valid': len(errors) == 0
    }


def validate_json_schema(file_path: Path, schema_config: Dict) -> Dict[str, Any]:
    """Validate JSON file structure against schema"""
    try:
        data = json.loads(file_path.read_text())
        
        # Check required fields
        required_fields = schema_config.get('required_fields', [])
        missing_fields = [f for f in required_fields if f not in data]
        
        if missing_fields:
            return {
                'status': 'FAIL',
                'file': str(file_path),
                'error': f"Missing fields: {missing_fields}"
            }
        
        return {'status': 'PASS', 'file': str(file_path)}
    
    except json.JSONDecodeError as e:
        return {'status': 'FAIL', 'file': str(file_path), 'error': f"Invalid JSON: {e}"}
    except Exception as e:
        return {'status': 'FAIL', 'file': str(file_path), 'error': str(e)}


def validate_parquet_schema(file_path: Path, schema_config: Dict) -> Dict[str, Any]:
    """Validate Parquet file structure and columns"""
    try:
        df = pd.read_parquet(file_path)
        
        # Check required columns
        required_cols = schema_config.get('required_columns', [])
        missing_cols = [c for c in required_cols if c not in df.columns]
        
        if missing_cols:
            return {
                'status': 'FAIL',
                'file': str(file_path),
                'error': f"Missing columns: {missing_cols}"
            }
        
        if len(df) == 0:
            return {'status': 'FAIL', 'file': str(file_path), 'error': "Empty parquet file"}
        
        return {'status': 'PASS', 'file': str(file_path), 'rows': len(df)}
    
    except Exception as e:
        return {'status': 'FAIL', 'file': str(file_path), 'error': str(e)}


def validate_csv_schema(file_path: Path, schema_config: Dict) -> Dict[str, Any]:
    """Validate CSV file structure"""
    try:
        df = pd.read_csv(file_path)
        
        # Check required columns
        required_cols = schema_config.get('required_columns', [])
        missing_cols = [c for c in required_cols if c not in df.columns]
        
        if missing_cols:
            return {
                'status': 'FAIL',
                'file': str(file_path),
                'error': f"Missing columns: {missing_cols}"
            }
        
        if len(df) == 0:
            return {'status': 'FAIL', 'file': str(file_path), 'error': "Empty CSV file"}
        
        return {'status': 'PASS', 'file': str(file_path), 'rows': len(df)}
    
    except Exception as e:
        return {'status': 'FAIL', 'file': str(file_path), 'error': str(e)}


def validate_png_file(file_path: Path) -> Dict[str, Any]:
    """Validate PNG is readable and not corrupt"""
    try:
        from PIL import Image
        img = Image.open(file_path)
        
        if img.format != 'PNG':
            return {'status': 'FAIL', 'file': str(file_path), 'error': f"Not PNG format: {img.format}"}
        
        if img.size[0] == 0 or img.size[1] == 0:
            return {'status': 'FAIL', 'file': str(file_path), 'error': "Invalid image size"}
        
        return {'status': 'PASS', 'file': str(file_path), 'size': img.size}
    
    except Exception as e:
        return {'status': 'FAIL', 'file': str(file_path), 'error': str(e)}


def validate_markdown_file(file_path: Path) -> Dict[str, Any]:
    """Validate Markdown file is non-empty"""
    try:
        content = file_path.read_text()
        
        if len(content) < 100:
            return {'status': 'FAIL', 'file': str(file_path), 'error': "File too short (<100 chars)"}
        
        return {'status': 'PASS', 'file': str(file_path), 'size': len(content)}
    
    except Exception as e:
        return {'status': 'FAIL', 'file': str(file_path), 'error': str(e)}


def validate_schemas(run_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate all file schemas according to config/reporting.yml.
    
    Returns:
        Dict with status, files_checked, errors list
    """
    logger.info(f"🔍 Validating schemas — Run: {run_id}")
    
    run_dir = Path(f"runflow/{run_id}")
    schemas = config.get('schemas', {})
    errors = []
    files_checked = 0
    
    # Validate JSON files
    json_files = {
        'segment_metrics': run_dir / 'ui' / 'segment_metrics.json',
        'flags': run_dir / 'ui' / 'flags.json',
        'flow': run_dir / 'ui' / 'flow.json',
        'captions': run_dir / 'ui' / 'captions.json',
    }
    
    for name, file_path in json_files.items():
        if file_path.exists() and name in schemas:
            result = validate_json_schema(file_path, schemas[name])
            files_checked += 1
            if result['status'] != 'PASS':
                errors.append(result)
                logger.error(
                    f"❌ Schema Error — File: {file_path.name} — "
                    f"Error: {result.get('error')} — Run: {run_id}"
                )
    
    # Validate Parquet files
    bins_parquet = run_dir / 'bins' / 'bins.parquet'
    if bins_parquet.exists() and 'bins_parquet' in schemas:
        result = validate_parquet_schema(bins_parquet, schemas['bins_parquet'])
        files_checked += 1
        if result['status'] != 'PASS':
            errors.append(result)
            logger.error(
                f"❌ Schema Error — File: bins.parquet — "
                f"Error: {result.get('error')} — Run: {run_id}"
            )
    
    # Validate CSV files
    flow_csv = run_dir / 'reports' / 'Flow.csv'
    if flow_csv.exists() and 'flow_csv' in schemas:
        result = validate_csv_schema(flow_csv, schemas['flow_csv'])
        files_checked += 1
        if result['status'] != 'PASS':
            errors.append(result)
            logger.error(
                f"❌ Schema Error — File: Flow.csv — "
                f"Error: {result.get('error')} — Run: {run_id}"
            )
    
    # Validate PNG files (sample check - just A1.png)
    a1_heatmap = run_dir / 'ui' / 'heatmaps' / 'A1.png'
    if a1_heatmap.exists():
        result = validate_png_file(a1_heatmap)
        files_checked += 1
        if result['status'] != 'PASS':
            errors.append(result)
            logger.error(
                f"❌ Schema Error — File: A1.png — "
                f"Error: {result.get('error')} — Run: {run_id}"
            )
    
    # Validate Markdown files
    for md_file in ['Density.md', 'Flow.md']:
        md_path = run_dir / 'reports' / md_file
        if md_path.exists():
            result = validate_markdown_file(md_path)
            files_checked += 1
            if result['status'] != 'PASS':
                errors.append(result)
                logger.error(
                    f"❌ Schema Error — File: {md_file} — "
                    f"Error: {result.get('error')} — Run: {run_id}"
                )
    
    status = 'PASS' if len(errors) == 0 else 'FAIL'
    
    if status == 'PASS':
        logger.info(f"✅ Schema Validation — Status: PASS — Files: {files_checked} — Run: {run_id}")
    else:
        logger.error(f"❌ Schema Validation — Status: FAIL — Errors: {len(errors)} — Run: {run_id}")
    
    return {
        'status': status,
        'files_checked': files_checked,
        'errors': errors
    }


def inject_verification_status(run_id: str, validation_results: Dict[str, Any]) -> None:
    """
    Extend metadata.json with output_verification block.
    
    Placed immediately after file_counts.
    Updates root status field based on verification.
    
    Args:
        run_id: Run ID
        validation_results: Results from validate_run()
    """
    metadata_path = Path(f'runflow/{run_id}/metadata.json')
    
    if not metadata_path.exists():
        logger.warning(f"⚠️ metadata.json not found, skipping injection — Run: {run_id}")
        return
    
    try:
        metadata = json.loads(metadata_path.read_text())
        
        # Update root status to reflect verification
        verification_status = validation_results['status']
        metadata['status'] = verification_status
        
        # Insert output_verification after file_counts
        metadata['output_verification'] = {
            'status': verification_status,
            'validated_at': validation_results['validated_at'],
            'validator_version': validation_results['validator_version'],
            'missing': validation_results.get('missing', []),
            'schema_errors': validation_results.get('schema_errors', []),
            'invalid_artifacts': validation_results.get('invalid_artifacts', []),
            'checks': validation_results.get('checks', {})
        }
        
        # Atomic write
        temp_path = metadata_path.with_suffix('.tmp')
        temp_path.write_text(json.dumps(metadata, indent=2))
        temp_path.replace(metadata_path)
        
        logger.info(f"✅ Metadata Updated — Status: {verification_status} — Run: {run_id}")
    
    except Exception as e:
        logger.error(f"❌ Metadata Injection Failed — Error: {e} — Run: {run_id}")
        raise


def update_index_status(run_id: str, status: str) -> None:
    """
    Update status field in index.json entry.
    
    Status is propagated from metadata.json root status field.
    
    Args:
        run_id: Run ID
        status: PASS | PARTIAL | FAIL
    """
    index_path = Path('runflow/index.json')
    
    if not index_path.exists():
        logger.warning(f"⚠️ index.json not found, skipping status update — Run: {run_id}")
        return
    
    try:
        index = json.loads(index_path.read_text())
        
        # Find and update entry
        updated = False
        for entry in index:
            if entry.get('run_id') == run_id:
                entry['status'] = status
                updated = True
                break
        
        if not updated:
            logger.warning(f"⚠️ Run not found in index.json — Run: {run_id}")
            return
        
        # Atomic write
        temp_path = index_path.with_suffix('.tmp')
        temp_path.write_text(json.dumps(index, indent=2))
        temp_path.replace(index_path)
        
        logger.info(f"✅ Index Updated — Status: {status} — Run: {run_id}")
    
    except Exception as e:
        logger.error(f"❌ Index Update Failed — Error: {e} — Run: {run_id}")
        raise


def validate_run(run_id: Optional[str] = None, config: Optional[Dict] = None, 
                 update_metadata: bool = True) -> Dict[str, Any]:
    """
    Validate a complete run's outputs.
    
    Args:
        run_id: Run ID to validate (defaults to latest from latest.json)
        config: Validation config (defaults to config/reporting.yml)
        update_metadata: If True, inject results into metadata.json and index.json
    
    Returns:
        Validation results with status, missing files, errors
    """
    # Load config if not provided
    if config is None:
        config = load_validation_config()
    
    # Get run_id if not provided
    if run_id is None:
        run_id = get_latest_run_id()
    
    logger.info(f"{'=' * 60}")
    logger.info(f"Output Validation")
    logger.info(f"Run ID: {run_id}")
    logger.info(f"{'=' * 60}")
    
    validation_results = {
        'status': 'PASS',
        'run_id': run_id,
        'validated_at': datetime.now(timezone.utc).isoformat(),
        'validator_version': VALIDATOR_VERSION,
        'missing': [],
        'schema_errors': [],
        'invalid_artifacts': [],
        'checks': {}
    }
    
    # 1. Validate latest.json pointer
    latest_check = validate_latest_pointer()
    validation_results['checks']['latest_json'] = latest_check
    if latest_check['status'] != 'PASS':
        validation_results['status'] = 'FAIL'
    
    # 2. Validate file presence
    file_check = validate_file_presence(run_id, config)
    validation_results['checks']['file_presence'] = file_check
    validation_results['missing'] = file_check.get('missing', [])
    
    if file_check['status'] == 'FAIL':
        validation_results['status'] = 'FAIL'
    elif file_check['status'] == 'PARTIAL' and validation_results['status'] == 'PASS':
        validation_results['status'] = 'PARTIAL'
    
    # 3. Validate API consistency
    api_check = validate_api_consistency(run_id)
    validation_results['checks']['api_consistency'] = api_check
    
    if api_check['status'] != 'PASS':
        validation_results['status'] = 'FAIL'
    
    # 4. Validate schemas (Step 3)
    schema_check = validate_schemas(run_id, config)
    validation_results['checks']['schema_validation'] = schema_check
    validation_results['schema_errors'] = schema_check.get('errors', [])
    
    if schema_check['status'] != 'PASS':
        validation_results['status'] = 'FAIL'
    
    # Summary
    logger.info(f"")
    logger.info(f"{'=' * 60}")
    logger.info(f"Validation Summary")
    logger.info(f"{'=' * 60}")
    
    if validation_results['status'] == 'PASS':
        logger.info(f"✅ Overall Status: PASS — Run: {run_id}")
    elif validation_results['status'] == 'PARTIAL':
        logger.warning(f"⚠️ Overall Status: PARTIAL — Run: {run_id}")
        logger.warning(f"   Missing: {len(validation_results['missing'])} non-critical files")
    else:
        logger.error(f"❌ Overall Status: FAIL — Run: {run_id}")
        logger.error(f"   Missing: {len(validation_results['missing'])} files")
    
    # Update metadata.json and index.json with verification results (Steps 4 & 5)
    if update_metadata:
        try:
            inject_verification_status(run_id, validation_results)
            update_index_status(run_id, validation_results['status'])
        except Exception as e:
            logger.warning(f"⚠️ Could not update metadata/index: {e}")
    
    return validation_results


def validate_all_runs(config: Optional[Dict] = None, update_metadata: bool = True) -> Dict[str, Any]:
    """
    Validate all runs in index.json.
    
    Args:
        config: Validation config (defaults to config/reporting.yml)
        update_metadata: If True, inject results into metadata.json and index.json
    
    Returns:
        Summary dictionary with total runs, passed, failed, partial counts
    """
    index_path = Path("runflow/index.json")
    
    if not index_path.exists():
        logger.error(f"❌ index.json Missing — File: {index_path}")
        raise FileNotFoundError("runflow/index.json not found")
    
    try:
        index = json.loads(index_path.read_text())
        if not isinstance(index, list) or len(index) == 0:
            logger.warning(f"⚠️ index.json Empty — No runs to validate")
            return {
                'total_runs': 0,
                'passed': 0,
                'failed': 0,
                'partial': 0,
                'results': []
            }
    except json.JSONDecodeError as e:
        logger.error(f"❌ index.json Corrupt — Error: {e}")
        raise
    
    logger.info(f"{'=' * 60}")
    logger.info(f"Validating All Runs")
    logger.info(f"Total runs in index.json: {len(index)}")
    logger.info(f"{'=' * 60}")
    
    results_summary = {
        'total_runs': len(index),
        'passed': 0,
        'failed': 0,
        'partial': 0,
        'results': []
    }
    
    # Validate each run
    for i, entry in enumerate(index, 1):
        run_id = entry.get('run_id')
        if not run_id:
            logger.warning(f"⚠️ Skipping entry {i}: missing run_id")
            continue
        
        logger.info(f"")
        logger.info(f"[{i}/{len(index)}] Validating run: {run_id}")
        logger.info(f"-" * 60)
        
        try:
            result = validate_run(run_id=run_id, config=config, update_metadata=update_metadata)
            
            # Track results
            results_summary['results'].append({
                'run_id': run_id,
                'status': result['status'],
                'missing_count': len(result.get('missing', [])),
                'schema_errors': len(result.get('schema_errors', []))
            })
            
            if result['status'] == 'PASS':
                results_summary['passed'] += 1
            elif result['status'] == 'PARTIAL':
                results_summary['partial'] += 1
            else:  # FAIL
                results_summary['failed'] += 1
        
        except Exception as e:
            logger.error(f"❌ Validation Failed — Run: {run_id} — Error: {e}")
            results_summary['failed'] += 1
            results_summary['results'].append({
                'run_id': run_id,
                'status': 'FAIL',
                'error': str(e)
            })
    
    # Summary
    logger.info(f"")
    logger.info(f"{'=' * 60}")
    logger.info(f"Validation Summary (All Runs)")
    logger.info(f"{'=' * 60}")
    logger.info(f"Total runs: {results_summary['total_runs']}")
    logger.info(f"✅ Passed: {results_summary['passed']}")
    logger.info(f"⚠️  Partial: {results_summary['partial']}")
    logger.info(f"❌ Failed: {results_summary['failed']}")
    
    if results_summary['failed'] > 0:
        logger.info(f"")
        logger.info(f"Failed runs:")
        for result in results_summary['results']:
            if result['status'] == 'FAIL':
                logger.error(f"  - {result['run_id']}: {result.get('error', 'Validation failed')}")
    
    return results_summary


def main():
    """CLI entry point for output validation"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Validate run outputs for completeness and integrity'
    )
    parser.add_argument(
        '--run-id',
        help='Specific run ID to validate (defaults to latest from latest.json)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Validate all runs in index.json'
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='Strict mode: treat required files as critical'
    )
    
    args = parser.parse_args()
    
    # Validate all runs if --all flag is set
    if args.all:
        try:
            config = load_validation_config()
            summary = validate_all_runs(config=config, update_metadata=True)
            
            # Exit code based on results
            if summary['failed'] > 0:
                sys.exit(1)  # At least one run failed
            elif args.strict and summary['partial'] > 0:
                logger.error(f"❌ Strict Mode — {summary['partial']} runs with PARTIAL status")
                sys.exit(1)
            else:
                sys.exit(0)  # All passed or partial (if not strict)
        
        except Exception as e:
            logger.error(f"❌ Validation Failed — Error: {e}")
            sys.exit(1)
    
    # Validate single run (default behavior)
    try:
        results = validate_run(run_id=args.run_id)
        
        # Exit code based on status
        if results['status'] == 'PASS':
            sys.exit(0)
        elif results['status'] == 'PARTIAL':
            # In strict mode, PARTIAL is failure
            if args.strict:
                logger.error(f"❌ Strict Mode — PARTIAL not allowed — Run: {results['run_id']}")
                sys.exit(1)
            else:
                sys.exit(0)  # PARTIAL is acceptable in default mode
        else:  # FAIL
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"❌ Validation Failed — Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

