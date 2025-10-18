from pathlib import Path
import hashlib, json

CANON = {"ensure_ascii": False, "sort_keys": True, "separators": (",", ":")}

def _canonical_bytes(path: str) -> bytes:
    p = Path(path)
    if p.suffix.lower() in {".json", ".geojson"}:
        obj = json.loads(p.read_text())
        return json.dumps(obj, **CANON).encode("utf-8")
    return p.read_bytes()

def compute_run_hash(paths: list[str]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):  # stable order
        h.update(_canonical_bytes(p))
    return h.hexdigest()
