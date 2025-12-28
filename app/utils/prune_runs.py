"""
Utility to prune old run_ids from runflow directory.

Issue #541: Keep only the last N runs, removing older run folders and updating index.json.
Preserves latest.json to ensure it always points to the most recent run.

Usage:
    python -m app.utils.prune_runs --keep 10 --dry-run
    python -m app.utils.prune_runs --keep 10 --confirm
"""

import json
import shutil
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple
import logging

from app.utils.run_id import get_runflow_root

logger = logging.getLogger(__name__)


def load_index() -> Tuple[List[Dict[str, Any]], Path]:
    """
    Load index.json and return entries plus file path.
    
    Returns:
        Tuple of (entries list, index.json path)
    """
    runflow_root = get_runflow_root()
    index_path = runflow_root / "index.json"
    
    if not index_path.exists():
        raise FileNotFoundError(f"index.json not found at {index_path}")
    
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            entries = json.load(f)
        
        if not isinstance(entries, list):
            raise ValueError("index.json is not a JSON array")
        
        return entries, index_path
    except json.JSONDecodeError as e:
        raise ValueError(f"index.json is corrupted: {e}")


def load_latest() -> Tuple[str, Path]:
    """
    Load latest.json and return run_id plus file path.
    
    Returns:
        Tuple of (run_id, latest.json path)
    """
    runflow_root = get_runflow_root()
    latest_path = runflow_root / "latest.json"
    
    if not latest_path.exists():
        raise FileNotFoundError(f"latest.json not found at {latest_path}")
    
    try:
        with open(latest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        run_id = data.get("run_id")
        if not run_id:
            raise ValueError("latest.json missing 'run_id' field")
        
        return run_id, latest_path
    except json.JSONDecodeError as e:
        raise ValueError(f"latest.json is corrupted: {e}")


def find_all_run_folders() -> List[str]:
    """
    Find all run_id folders in the filesystem (including orphaned ones).
    
    Returns:
        List of run_id folder names (26-character alphanumeric)
    """
    runflow_root = get_runflow_root()
    run_folders = []
    
    if not runflow_root.exists():
        return []
    
    for item in runflow_root.iterdir():
        if item.is_dir():
            name = item.name
            # Check if it looks like a run_id (26 char alphanumeric)
            if len(name) == 26 and name.replace('_', '').isalnum():
                run_folders.append(name)
    
    return run_folders


def identify_runs_to_delete(keep_n: int) -> Tuple[List[str], List[str], List[str]]:
    """
    Identify which runs to delete and which to keep.
    
    Also identifies orphaned folders (exist in filesystem but not in index.json).
    
    Args:
        keep_n: Number of runs to keep (last N)
        
    Returns:
        Tuple of (runs_to_delete_from_index, runs_to_keep, orphaned_folders)
    """
    entries, _ = load_index()
    all_folders = find_all_run_folders()
    
    # Get run_ids from index.json
    index_run_ids = {e.get("run_id") for e in entries if e.get("run_id")}
    
    # Find orphaned folders (exist in filesystem but not in index.json)
    orphaned_folders = [f for f in all_folders if f not in index_run_ids]
    
    if keep_n >= len(entries):
        # Keep all runs in index, but still delete orphaned folders
        runs_to_keep = [e.get("run_id") for e in entries]
        runs_to_delete_from_index = []
        return runs_to_delete_from_index, runs_to_keep, orphaned_folders
    
    # Keep last N entries (newest)
    runs_to_keep = [e.get("run_id") for e in entries[-keep_n:]]
    runs_to_delete_from_index = [e.get("run_id") for e in entries[:-keep_n]]
    
    return runs_to_delete_from_index, runs_to_keep, orphaned_folders


def validate_latest_preserved(runs_to_delete: List[str], latest_run_id: str) -> bool:
    """
    Validate that latest.json run_id is not in the deletion list.
    
    Args:
        runs_to_delete: List of run_ids to be deleted
        latest_run_id: Run ID from latest.json
        
    Returns:
        True if latest is preserved, False otherwise
    """
    if latest_run_id in runs_to_delete:
        return False
    return True


def delete_run_folders(run_ids: List[str], dry_run: bool = False) -> List[str]:
    """
    Delete run folder directories.
    
    Args:
        run_ids: List of run_ids to delete
        dry_run: If True, only log what would be deleted
        
    Returns:
        List of run_ids that were successfully deleted (or would be in dry-run)
    """
    runflow_root = get_runflow_root()
    deleted = []
    
    for run_id in run_ids:
        run_path = runflow_root / run_id
        
        if not run_path.exists():
            logger.warning(f"Run folder does not exist: {run_path} (skipping)")
            continue
        
        if dry_run:
            logger.info(f"[DRY-RUN] Would delete: {run_path}")
            deleted.append(run_id)
        else:
            try:
                shutil.rmtree(run_path)
                logger.info(f"Deleted run folder: {run_path}")
                deleted.append(run_id)
            except Exception as e:
                logger.error(f"Failed to delete {run_path}: {e}")
    
    return deleted


def update_index_json(kept_runs: List[str], dry_run: bool = False) -> bool:
    """
    Update index.json to only include kept runs (atomic write).
    
    Uses temp file + rename pattern from app/utils/metadata.py for atomic writes.
    
    Args:
        kept_runs: List of run_ids to keep
        dry_run: If True, only log what would be updated
        
    Returns:
        True if successful, False otherwise
    """
    entries, index_path = load_index()
    
    # Filter entries to only include kept runs
    kept_entries = [e for e in entries if e.get("run_id") in kept_runs]
    
    if len(kept_entries) != len(kept_runs):
        logger.warning(f"Some kept run_ids not found in index.json: {kept_runs}")
    
    if dry_run:
        logger.info(f"[DRY-RUN] Would update index.json: {len(entries)} -> {len(kept_entries)} entries")
        return True
    
    # Atomic write: write to temp file, then rename
    temp_path = index_path.with_suffix('.json.tmp')
    
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(kept_entries, f, indent=2, ensure_ascii=False)
        
        # Atomic rename
        temp_path.replace(index_path)
        logger.info(f"Updated index.json: {len(entries)} -> {len(kept_entries)} entries")
        return True
    except Exception as e:
        logger.error(f"Failed to update index.json: {e}")
        # Clean up temp file if it exists
        if temp_path.exists():
            try:
                temp_path.unlink()
            except:
                pass
        return False


def prune_runs(keep_n: int, dry_run: bool = False, confirm: bool = False) -> bool:
    """
    Main function to prune old runs.
    
    Args:
        keep_n: Number of runs to keep (last N)
        dry_run: If True, only preview changes without making them
        confirm: If True, skip confirmation prompt (for automation)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Load current state
        entries, _ = load_index()
        latest_run_id, _ = load_latest()
        
        total_runs = len(entries)
        all_folders = find_all_run_folders()
        logger.info(f"Current state: {total_runs} runs in index.json, {len(all_folders)} run folders in filesystem")
        logger.info(f"Latest run_id: {latest_run_id}")
        
        # Identify runs to delete (from index) and orphaned folders
        runs_to_delete_from_index, runs_to_keep, orphaned_folders = identify_runs_to_delete(keep_n)
        
        # Check if pruning is needed
        if not runs_to_delete_from_index and not orphaned_folders:
            logger.info(f"No pruning needed: {len(runs_to_keep)} runs in index.json, {len(all_folders)} folders in filesystem")
            if len(all_folders) == len(runs_to_keep):
                logger.info("✅ All folders are tracked in index.json. No action needed.")
            return True
        
        # Combine all folders to delete
        all_runs_to_delete = runs_to_delete_from_index + orphaned_folders
        
        logger.info(f"Will keep {len(runs_to_keep)} runs (last {keep_n})")
        logger.info(f"Will delete {len(runs_to_delete_from_index)} runs from index.json")
        if orphaned_folders:
            logger.info(f"Will delete {len(orphaned_folders)} orphaned folders (not in index.json)")
        logger.info(f"Total folders to delete: {len(all_runs_to_delete)}")
        
        # Validate latest.json is preserved
        if not validate_latest_preserved(runs_to_delete_from_index, latest_run_id):
            logger.error(f"ERROR: latest.json run_id ({latest_run_id}) would be deleted!")
            logger.error("Aborting to preserve latest.json run_id.")
            return False
        
        # Also check orphaned folders
        if latest_run_id in orphaned_folders:
            logger.warning(f"WARNING: latest.json run_id ({latest_run_id}) is orphaned (not in index.json)")
            logger.warning("This should not happen. Removing from orphaned list to preserve it.")
            orphaned_folders.remove(latest_run_id)
            all_runs_to_delete = runs_to_delete_from_index + orphaned_folders
        
        # Show what will be deleted
        if runs_to_delete_from_index:
            logger.info("Runs to be deleted (from index.json):")
            for run_id in runs_to_delete_from_index[:10]:  # Show first 10
                logger.info(f"  - {run_id}")
            if len(runs_to_delete_from_index) > 10:
                logger.info(f"  ... and {len(runs_to_delete_from_index) - 10} more")
        
        if orphaned_folders:
            logger.info("Orphaned folders to be deleted (not in index.json):")
            for run_id in orphaned_folders[:10]:  # Show first 10
                logger.info(f"  - {run_id}")
            if len(orphaned_folders) > 10:
                logger.info(f"  ... and {len(orphaned_folders) - 10} more")
        
        # Confirmation prompt (unless dry-run or confirm flag)
        if not dry_run and not confirm:
            response = input(f"\nDelete {len(all_runs_to_delete)} run folders ({len(runs_to_delete_from_index)} from index + {len(orphaned_folders)} orphaned)? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                logger.info("Aborted by user")
                return False
        
        # Delete run folders (both from index and orphaned)
        deleted_folders = delete_run_folders(all_runs_to_delete, dry_run=dry_run)
        
        if not dry_run and len(deleted_folders) != len(runs_to_delete):
            logger.warning(f"Only deleted {len(deleted_folders)} of {len(runs_to_delete)} run folders")
        
        # Update index.json
        success = update_index_json(runs_to_keep, dry_run=dry_run)
        
        if success:
            if dry_run:
                logger.info("[DRY-RUN] Pruning preview complete. Use --confirm to apply changes.")
            else:
                logger.info(f"✅ Successfully pruned runs: kept {len(runs_to_keep)}, deleted {len(deleted_folders)} folders")
                # Verify final state
                remaining_folders = find_all_run_folders()
                if len(remaining_folders) != len(runs_to_keep):
                    logger.warning(f"⚠️  Warning: Expected {len(runs_to_keep)} folders, but {len(remaining_folders)} folders remain")
                    logger.warning("This may indicate some folders couldn't be deleted or new folders were created.")
                else:
                    logger.info(f"✅ Verified: Exactly {len(runs_to_keep)} run folders remain")
        else:
            logger.error("Failed to update index.json")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Pruning failed: {e}", exc_info=True)
        return False


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Prune old run_ids from runflow directory, keeping only the last N runs"
    )
    parser.add_argument(
        '--keep',
        type=int,
        required=True,
        help='Number of runs to keep (last N)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without making them'
    )
    parser.add_argument(
        '--confirm',
        action='store_true',
        help='Skip confirmation prompt (for automation)'
    )
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if args.keep < 1:
        logger.error("--keep must be >= 1")
        sys.exit(1)
    
    success = prune_runs(
        keep_n=args.keep,
        dry_run=args.dry_run,
        confirm=args.confirm
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

