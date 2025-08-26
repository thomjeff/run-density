from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.density import DensityPayload, run_density, READY_FLAGS

app = FastAPI(title="run-density", version="v1.3.0")

# CORS (relax as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

@app.get("/health")
def health():
    return {"ok": True, "ts": __import__("time").time()}

@app.get("/ready")
def ready():
    return {
        "ok": True,
        "density_loaded": READY_FLAGS.get("density_loaded", False),
        "overlap_loaded": READY_FLAGS.get("overlap_loaded", False),
    }

@app.post("/api/density")
def api_density(payload: DensityPayload):
    """
    Requires:
      - paceCsv (event,runner_id,pace,distance)
      - overlapsCsv (seg_id,segment_label,eventA,eventB,from_km_A,to_km_A,from_km_B,to_km_B,direction,width_m)
      - startTimes minutes offsets, e.g. {"Full":420,"10K":440,"Half":460}
      - stepKm, timeWindow (seconds)
    Returns: { engine: "density", segments: [ {seg_id, segment_label, peak: {...}} ] }
    """
    try:
        return run_density(payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"density/run failed: {e}")