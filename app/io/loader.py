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
    Load passes.csv / locations.csv with validation and normalization.

    2027 identity: ``pass_id`` (timed instance), ``loc_id`` (human Location),
    ``pass_key`` (opaque unifier). Legacy files that used ``loc_id`` as the
    instance id are upgraded in-memory.
    """
    from pathlib import Path

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(
            f"locations/passes file not found at {file_path.absolute()}. "
            f"Expected passes.csv (or legacy locations.csv) with pass_id/loc_id columns."
        )

    df = pd.read_csv(path)
    df = normalize_passes_input_dataframe(df)

    # One-pager flag: canonical column name is ``onepage`` (y/n).

    # Normalize event flags (y/n)
    known_events = ["full", "half", "10K", "elite", "open"]
    for ev in known_events:
        if ev in df.columns:
            df[ev] = df[ev].map(_yn)

    for col in df.columns:
        if col.lower() in ["full", "half", "10k", "elite", "open"] and col not in known_events:
            df[col] = df[col].map(_yn)

    if "lat" in df.columns:
        df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    if "lon" in df.columns:
        df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    if "buffer" in df.columns:
        df["buffer"] = pd.to_numeric(df["buffer"], errors="coerce")
    if "interval" in df.columns:
        df["interval"] = pd.to_numeric(df["interval"], errors="coerce")

    count_columns = [col for col in df.columns if col.endswith("_count")]
    for col in count_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[col] = df[col].fillna(0)

    if "loc_direction" in df.columns:
        df["loc_direction"] = df["loc_direction"].fillna("").astype(str)
    else:
        df["loc_direction"] = ""

    if "seg_id" in df.columns:
        df["seg_id"] = df["seg_id"].fillna("").astype(str)
        df["segments_list"] = df["seg_id"].apply(
            lambda x: [s.strip().strip('"') for s in str(x).replace('"', '').split(",") if s.strip()] if x else []
        )
    elif "segments" in df.columns:
        df["segments"] = df["segments"].fillna("").astype(str)
        df["segments_list"] = df["segments"].apply(
            lambda x: [s.strip() for s in str(x).split(",") if s.strip()] if x else []
        )

    return df


def normalize_passes_input_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Upgrade legacy location CSV columns to pass_id / loc_id / pass_key."""
    out = df.copy()

    if "pass_key" not in out.columns and "location_key" in out.columns:
        out["pass_key"] = out["location_key"]

    if "proxy_pass_id" not in out.columns and "proxy_loc_id" in out.columns:
        out["proxy_pass_id"] = out["proxy_loc_id"]
    if "proxy_loc_id" not in out.columns and "proxy_pass_id" in out.columns:
        out["proxy_loc_id"] = out["proxy_pass_id"]

    legacy_instance = "pass_id" not in out.columns and "loc_id" in out.columns
    if legacy_instance:
        out["pass_id"] = out["loc_id"]

    needs_human_loc = (
        "loc_id" not in out.columns
        or legacy_instance
        or out["loc_id"].isna().all()
    )
    if needs_human_loc:
        records = out.to_dict(orient="records")
        from app.core.locations.identity import stamp_pass_identity

        for rec in records:
            pid = rec.get("pass_id")
            if pid is not None and pid == pid:  # not NaN
                rec["id"] = pid
                rec["pass_id"] = pid
            if legacy_instance:
                rec.pop("loc_id", None)
        stamp_pass_identity(records)
        stamped = pd.DataFrame(records)
        for col in ("pass_id", "loc_id", "pass_key", "id", "location_key"):
            if col in stamped.columns:
                out[col] = stamped[col].values

    if "pass_key" in out.columns and "location_key" not in out.columns:
        out["location_key"] = out["pass_key"]
    if "proxy_pass_id" in out.columns and "proxy_loc_id" not in out.columns:
        out["proxy_loc_id"] = out["proxy_pass_id"]

    return out
