from fastapi import FastAPI, Query
from app.density import DensityPayload, run_density

app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/ready")
def ready():
    # If you have deeper checks, wire them here; this keeps the contract you’ve been using.
    return {"ok": True, "density_loaded": True, "overlap_loaded": True}

@app.post("/api/density")
def api_density(
    payload: DensityPayload,
    seg_id: str | None = Query(default=None),
    debug: bool = Query(default=False),
):
    return run_density(payload, seg_id=seg_id, debug=debug)