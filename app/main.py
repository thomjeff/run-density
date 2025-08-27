from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from app.density import DensityPayload, run_density

app = FastAPI(title="Run Density API", version="1.3.2")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/ready")
def ready():
    return {"ok": True, "density_loaded": True, "overlap_loaded": True}

@app.post("/api/density")
def api_density(payload: DensityPayload,
                seg_id: str = Query(default=None),
                debug: bool = Query(default=False)):
    try:
        return run_density(payload, seg_id_filter=seg_id, debug=debug)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})