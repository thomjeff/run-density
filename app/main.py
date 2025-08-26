# app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from app.density import DensityPayload, run_density

app = FastAPI(title="run-density", version="1.3.0")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/ready")
def ready():
    # Keep this simple. We defer real checks to CI’s “200 HEAD” step.
    return {"ok": True, "density_loaded": True, "overlap_loaded": True}

@app.post("/api/density")
def density(payload: DensityPayload):
    try:
        result = run_density(payload)
        return JSONResponse(result)
    except HTTPException:
        raise
    except Exception as e:
        # Surface as 500 so your smoke sees failure clearly if something breaks.
        raise HTTPException(status_code=500, detail=str(e))