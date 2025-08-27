from fastapi import FastAPI, Query
from app.density import DensityPayload, run_density

app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/ready")
def ready():
    return {"ok": True, "density_loaded": True, "overlap_loaded": True}

@app.post("/api/density")
def api_density(payload: DensityPayload, seg_id: str = Query(None), debug: bool = Query(False)):
    return run_density(payload, seg_id_filter=seg_id, debug=debug)