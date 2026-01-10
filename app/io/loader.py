import pandas as pd

def _yn(x):
    s = str(x).strip().lower()
    if s in {"y","n"}:
        return s
    return s  # leave as-is if unexpected; tests will catch

def load_segments(path: str):
    df = pd.read_csv(path)
    # normalize minimal bits required by current code
    # Issue #553 Phase 4.2: Normalize known event columns, plus dynamically discover others
    known_events = ["full","half","10K","elite","open"]
    for ev in known_events:
        if ev in df.columns:
            df[ev] = df[ev].map(_yn)
    
    # Dynamic discovery: normalize any other columns that look like event flags
    # (columns that match event name pattern and aren't already normalized)
    for col in df.columns:
        if col.lower() in ["full", "half", "10k", "elite", "open"] and col not in known_events:
            df[col] = df[col].map(_yn)
    
    if "width_m" in df.columns:
        df["width_m"] = pd.to_numeric(df["width_m"], errors="coerce")
    return df

def load_runners(path: str):
    return pd.read_csv(path)

def load_runners_by_event(runners_path: str):
    """
    Load runners for a specific event from event-specific CSV file.
    
    Phase 1 (Issue #495): Helper function for v2 event-specific runner loading.
    Normalizes event name to lowercase for consistent file naming.
    
    Args:
        runners_path: Path to event-specific runners CSV file
        
    Returns:
        DataFrame with runner data for the specified event
        
    Raises:
        FileNotFoundError: If runner file doesn't exist
    """
    from pathlib import Path
    
    runners_path = Path(runners_path)

    if not runners_path.exists():
        raise FileNotFoundError(
            f"Runner file not found at {runners_path}"
        )
    
    return pd.read_csv(runners_path)

def load_locations(path: str):
    """
    Load locations.csv with validation and normalization.
    
    Issue #277: Locations report input file.
    
    Args:
        path: Path to locations.csv file
        
    Returns:
        DataFrame with normalized location data
        
    Raises:
        FileNotFoundError: If locations.csv file does not exist
    """
    from pathlib import Path
    
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(
            f"locations.csv not found at {file_path.absolute()}. "
            f"Issue #277 requires locations.csv in the data/ directory. "
            f"Please ensure the file exists with columns: loc_id, loc_label, loc_type, lat, lon, seg_id, zone, full, half, 10K, elite, open, buffer, interval, notes"
        )
    
    df = pd.read_csv(path)
    
    # Normalize event flags (y/n)
    # Issue #553 Phase 4.2: Normalize known event columns, plus dynamically discover others
    known_events = ["full", "half", "10K", "elite", "open"]
    for ev in known_events:
        if ev in df.columns:
            df[ev] = df[ev].map(_yn)
    
    # Dynamic discovery: normalize any other columns that look like event flags
    for col in df.columns:
        if col.lower() in ["full", "half", "10k", "elite", "open"] and col not in known_events:
            df[col] = df[col].map(_yn)
    
    # Ensure numeric columns are numeric
    if "lat" in df.columns:
        df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    if "lon" in df.columns:
        df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    if "buffer" in df.columns:
        df["buffer"] = pd.to_numeric(df["buffer"], errors="coerce")
    if "interval" in df.columns:
        df["interval"] = pd.to_numeric(df["interval"], errors="coerce")
    
    # Issue #589: Normalize all *_count fields to numeric
    # Dynamically detect all columns ending with "_count"
    count_columns = [col for col in df.columns if col.endswith("_count")]
    for col in count_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        # Fill NaN with 0 (validation will catch invalid values, but this prevents errors during processing)
        df[col] = df[col].fillna(0)
    
    # Issue #589: Normalize loc_direction (optional field, empty string if missing)
    if "loc_direction" in df.columns:
        df["loc_direction"] = df["loc_direction"].fillna("").astype(str)
    else:
        df["loc_direction"] = ""  # Add column with empty strings if missing
    
    # Parse seg_id field (comma-separated) - Issue #277: CSV uses "seg_id" column
    if "seg_id" in df.columns:
        df["seg_id"] = df["seg_id"].fillna("").astype(str)
        # Handle quoted values like "A1,G1" by removing quotes and splitting
        df["segments_list"] = df["seg_id"].apply(
            lambda x: [s.strip().strip('"') for s in str(x).replace('"', '').split(",") if s.strip()] if x else []
        )
    elif "segments" in df.columns:
        # Fallback to "segments" if present
        df["segments"] = df["segments"].fillna("").astype(str)
        df["segments_list"] = df["segments"].apply(
            lambda x: [s.strip() for s in str(x).split(",") if s.strip()] if x else []
        )
    
    return df
