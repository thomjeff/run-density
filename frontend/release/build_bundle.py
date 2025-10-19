"""
Runflow Release Bundler

Creates deployment bundle with manifest for all front-end artifacts.

Author: AI Assistant (Cursor)
Issue: #274 - Phase 5: Validation & Deployment
Architecture Guidance: ChatGPT
"""

from pathlib import Path
import json
import hashlib
import zipfile
from datetime import datetime

OUT = Path("release")

# Core HTML artifacts
ARTIFACTS = [
    "frontend/map/output/map.html",
    "frontend/dashboard/output/dashboard.html",
    "frontend/reports/output/density.html",
]

# Asset directories
ASSETS = [
    "frontend/reports/output/mini_maps",
    "frontend/reports/output/sparklines"
]

MANIFEST = OUT / "manifest.json"


def file_hash(path: str) -> str:
    """
    Compute SHA256 hash of a file.
    
    Args:
        path: File path
        
    Returns:
        str: SHA256 hash (lowercase hex)
    """
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def main():
    """
    Build release bundle with manifest.
    
    Creates:
    1. manifest.json with hashes and metadata
    2. runflow-<hash>.zip with all artifacts
    
    Outputs:
        release/manifest.json
        release/runflow-<hash>.zip
    """
    print("[Release Bundle] Building deployment bundle...")
    
    OUT.mkdir(parents=True, exist_ok=True)
    
    manifest = {
        "artifacts": {},
        "assets": {},
        "meta": {},
        "build_timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    # Hash core artifacts
    print("[Release Bundle] Hashing artifacts...")
    for f in ARTIFACTS:
        p = Path(f)
        if not p.exists():
            print(f"[Release Bundle] ⚠️  Missing {f}")
            continue
        manifest["artifacts"][f] = {
            "sha256": file_hash(f),
            "size": p.stat().st_size
        }
        print(f"[Release Bundle]    ✅ {f} ({p.stat().st_size} bytes)")
    
    # Hash asset directories
    print("[Release Bundle] Hashing assets...")
    for folder in ASSETS:
        p = Path(folder)
        if not p.exists():
            print(f"[Release Bundle] ℹ️  Skipping {folder} (not found)")
            continue
        
        manifest["assets"][folder] = {}
        for child in p.rglob("*.*"):
            manifest["assets"][folder][str(child)] = file_hash(child)
        
        asset_count = len(manifest["assets"][folder])
        print(f"[Release Bundle]    ✅ {folder} ({asset_count} files)")
    
    # Load meta.json for provenance
    print("[Release Bundle] Loading provenance metadata...")
    meta_path = Path("data/meta.json")
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        manifest["meta"] = {
            "run_hash": meta.get("run_hash"),
            "dataset_version": meta.get("dataset_version"),
            "rulebook_hash": meta.get("rulebook_hash"),
            "environment": meta.get("environment"),
            "run_timestamp": meta.get("run_timestamp")
        }
        print(f"[Release Bundle]    ✅ Loaded meta.json")
        print(f"[Release Bundle]       run_hash: {manifest['meta']['run_hash'][:16] if manifest['meta']['run_hash'] else 'None'}...")
        print(f"[Release Bundle]       environment: {manifest['meta']['environment']}")
    else:
        print(f"[Release Bundle] ⚠️  meta.json not found")
    
    # Write manifest
    MANIFEST.write_text(json.dumps(manifest, indent=2))
    print(f"[Release Bundle] ✅ Wrote {MANIFEST}")
    
    # Create ZIP bundle
    run_id = manifest["meta"]["run_hash"][:8] if manifest["meta"].get("run_hash") else "unknown"
    zip_path = OUT / f"runflow-{run_id}.zip"
    
    print(f"[Release Bundle] Creating ZIP bundle...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        # Add manifest
        z.write(MANIFEST, arcname="manifest.json")
        
        # Add artifacts
        for f in ARTIFACTS:
            if Path(f).exists():
                z.write(f, arcname=Path(f).name)
        
        # Add assets
        for folder in ASSETS:
            p = Path(folder)
            if p.exists():
                for child in p.rglob("*.*"):
                    arcname = str(child.relative_to("frontend/reports/output"))
                    z.write(child, arcname=arcname)
    
    zip_size = zip_path.stat().st_size
    print(f"[Release Bundle] ✅ Created {zip_path} ({zip_size:,} bytes)")
    print(f"[Release Bundle] 🎉 Bundle complete!")
    
    # Summary
    artifact_count = len(manifest["artifacts"])
    asset_folder_count = len(manifest["assets"])
    print(f"\n📦 Bundle Summary:")
    print(f"   Artifacts: {artifact_count}")
    print(f"   Asset folders: {asset_folder_count}")
    print(f"   Run ID: {run_id}")
    print(f"   ZIP: {zip_path}")


if __name__ == "__main__":
    main()

