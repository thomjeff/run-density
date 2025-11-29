import pandas as pd

def _yn(x):
    s = str(x).strip().lower()
    if s in {"y","n"}:
        return s
    return s  # leave as-is if unexpected; tests will catch

def load_segments(path="data/segments.csv"):
    df = pd.read_csv(path)
    # normalize minimal bits required by current code
    for ev in ["full","half","10K"]:
        if ev in df.columns:
            df[ev] = df[ev].map(_yn)
    if "width_m" in df.columns:
        df["width_m"] = pd.to_numeric(df["width_m"], errors="coerce")
    return df

def load_runners(path="data/runners.csv"):
    return pd.read_csv(path)

def load_locations(path="data/locations.csv"):
    """
    Load locations.csv with validation and normalization.
    
    Issue #277: Locations report input file.
    
    Args:
        path: Path to locations.csv file
        
    Returns:
        DataFrame with normalized location data
    """
    df = pd.read_csv(path)
    
    # Normalize event flags (y/n)
    for ev in ["full", "half", "10K", "elite", "open"]:
        if ev in df.columns:
            df[ev] = df[ev].map(_yn)
    
    # Ensure numeric columns are numeric
    if "lat" in df.columns:
        df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    if "lon" in df.columns:
        df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    if "buffer" in df.columns:
        df["buffer"] = pd.to_numeric(df["buffer"], errors="coerce")
    if "interval" in df.columns:
        df["interval"] = pd.to_numeric(df["interval"], errors="coerce")
    
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
