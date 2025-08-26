# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.density import DensityPayload, run_density

app = FastAPI(title="run-density", version="1.3.0")

# CORS: allow all (safe for internal / testing use; tighten if exposing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/ready")
async def ready():
    # In real systems you’d check caches or preloaded resources here
    return {"ok": True, "density_loaded": True, "overlap_loaded": True}


@app.post("/api/density")
async def api_density(payload: DensityPayload):
    """
    POST with body matching DensityPayload.
    - Either supply 'segments' inline OR 'overlapsCsv'.
    - 'paceCsv' is always required.
    """
    result = run_density(payload)
    return result