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
