# Issue 628 - Flow UI

The issue text is present at codex/issue 628/issue628.md and matches what you provided, including the references to /codex/7iHmDgGFMZdpjLmZRVgYWY and the sample CSV for F1a zone 8.{line_range_start=1 line_range_end=76 path=codex/issue 628/issue628.md git_url="https://github.com/thomjeff/run-density/blob/main/codex/issue 628/issue628.md#L1-L76"}

## 1) How captions.json is generated today (Density heatmaps)
**Generation pipeline**
Captions for density are generated in app/core/artifacts/heatmaps.py:
- It loads bins, computes peak density/time/km range, splits time into “waves,” compares wave intensity/spread, finds clearance time, then builds a summary string via build_caption_summary().
- The rules that shape this logic (wave gap minutes, clearance thresholds, similarity/spread thresholds) are read from config/density_rulebook.yml under globals.captioning.

**Where the captions land**
In the runflow v2 pipeline, captions.json is moved into day-scoped UI artifacts at:
```javascript
runflow/<run_id>/<day>/ui/visualizations/captions.json
```
This relocation happens in app/core/v2/ui_artifacts.py.

**Example of structure**
The captions.json in your Sunday artifacts uses the summary/peak/waves structure (same as the generator output).


## 2) Where Flow UI data comes from today
**Current Flow UI**
The Flow UI (frontend/templates/pages/flow.html) renders a single segment-level table and does not show zone-level rows or captions today.

**Flow API source**
/api/flow/segments reads from Flow.csv (runflow day-scoped reports) and returns segment-level aggregates only — no per-zone data is in this endpoint today.

**Key hint already in Flow.csv**
_Issue #629 might have removed this_ The Flow.csv header already contains worst_zone_index, which you can reuse for the “Worst Zone” summary column without new analysis — it is already in the report output.


## 3) Zone-level data already exists (what to use for drilldown + captions)
The zone-level metrics you want to show are already exported in the fz file.
Your sample sun_fz_202601071257.csv includes the exact fields listed in the issue:
- zone_index, cp_km, event_a, event_b
- overtaking_a, overtaking_b, overtaken_a, overtaken_b
- copresence_a, copresence_b
- optional: unique_encounters, participants_involved, multi_category_runners

You can see all of those fields in the header and the F1a zone 8 row in the sample file you provided.{line_range_start=1 line_range_end=10 path=codex/issue 628/sun_fz_202601071257.csv git_url="https://github.com/thomjeff/run-density/blob/main/codex/issue 628/sun_fz_202601071257.csv#L1-L10"}


## 4) Narrative Caption Generator (Flow Zones) — design alignment with Density

**Why density captions are the best template**
The density generator already:
- standardizes a text template
- uses rulebook-configured thresholds
- outputs consistent JSON for UI consumption

That flow can be mirrored for zone captions, but driven by the fz rows instead of bins. The density caption generator code is here (with the summary builder and wave logic):

**Suggested caption logic for flow zones (based on your example)**
From the sun_fz_202601071257.csv row for F1a, zone 8:
- copresence_a + copresence_b can drive a “co-presence intensity” statement.
- overtaking_a/overtaking_b can be used for ratio wording.
- overtaken_a/overtaken_b supports the “bidirectional overtaking” phrase.

This data already exists in the sun_fz_202601071257.csv row for zone 8, so you can compute the exact narrative you want from those numbers.{line_range_start=1 line_range_end=10 path=codex/issue 628/sun_fz_202601071257.csv git_url="https://github.com/thomjeff/run-density/blob/main/codex/issue 628/sun_fz_202601071257.csv#L1-L10"}

**Where to store it**
Mirroring density, you could generate a zone_captions.json under:

```javascript
runflow/<run_id>/<day>/ui/visualizations/
```
This mirrors how captions.json is already stored for density captions.

```python
 8. Generate heatmaps and captions
logger.info("8️⃣  Generating heatmaps and captions...")
try:
    if heatmap_reports and heatmap_reports.exists():
        export_heatmaps_and_captions(run_id, heatmap_reports, None)
        
        # Move heatmaps and captions to day-scoped UI directory
        # Check multiple possible source locations
        import shutil
        runflow_root = get_runflow_root()
        
        # Heatmaps can be in multiple locations:
        # 1. runflow/{run_id}/heatmaps/ (run level - most common)
        # 2. runflow/{run_id}/ui/heatmaps/ (ui subdirectory)
        # 3. artifacts/{run_id}/ui/heatmaps/ (legacy)
        heatmaps_source = None
        for possible_path in [
            runflow_root / run_id / "heatmaps",  # Run level (most common)
            runflow_root / run_id / "ui" / "heatmaps",  # UI subdirectory
            Path("/app/artifacts") / run_id / "ui" / "heatmaps"  # Legacy
        ]:
            if possible_path.exists():
                heatmaps_source = possible_path
                break
        
        # Captions can be in:
        # 1. runflow/{run_id}/ui/captions.json (most common)
        # 2. artifacts/{run_id}/ui/captions.json (legacy)
        captions_source = None
        for possible_path in [
            runflow_root / run_id / "ui" / "captions.json",  # UI subdirectory
            Path("/app/artifacts") / run_id / "ui" / "captions.json"  # Legacy
        ]:
            if possible_path.exists():
                captions_source = possible_path
                break
        
        # Issue #574: Move heatmaps to visualizations/ subdirectory
        if heatmaps_source and heatmaps_source.exists():
            heatmaps_dest = visualizations_dir  # visualizations/ subdirectory
            heatmaps_dest.mkdir(parents=True, exist_ok=True)

            heatmaps_moved = 0
            for png_file in heatmaps_source.glob("*.png"):
                # Extract segment_id from filename (e.g., "A1.png" -> "A1")
                seg_id = png_file.stem
                if str(seg_id) in day_segment_ids:
                    dest_file = heatmaps_dest / png_file.name
                    shutil.move(str(png_file), str(dest_file))
                    heatmaps_moved += 1

            # Clean up source directory if empty after move
            try:
                if heatmaps_source.exists() and not any(heatmaps_source.iterdir()):
                    heatmaps_source.rmdir()
            except Exception as cleanup_err:
                logger.debug(f"   ⚠️  Could not remove source heatmaps dir: {cleanup_err}")

            logger.info(
                f"   ✅ Heatmaps filtered and moved: {heatmaps_moved} PNGs "
                f"for day {day.value} ({len(day_segment_ids)} segments) (in visualizations/)"
            )
        else:
            logger.warning(f"   ⚠️  Heatmaps not found at expected locations")
        
        # Issue #574: Move captions.json to visualizations/ subdirectory
        if captions_source and captions_source.exists():
            captions_dest = visualizations_dir / "captions.json"
            if captions_dest.exists():
                captions_dest.unlink()
            shutil.move(str(captions_source), str(captions_dest))
            logger.info(f"   ✅ Captions moved to {captions_dest} (in visualizations/)")

            ```
## 5) UI drilldown & “Worst Zone” column — where to wire it

**Flow UI file**
The flow UI is currently a single table with segment-level rows only. This will need to be expanded to support an accordion-like drilldown row for zones (just like density).

```python
% extends "base.html" %}

{% block title %}Flow Analysis{% endblock %}

{% block content %}
<div class="page-header">
    <h2>Temporal Flow Analysis</h2>
    {% if meta %}
    {% endif %}
</div>

<!-- Flow Metrics Table -->
<div class="card">
    <h3 style="margin-bottom: 1rem;">Segment Flow Metrics</h3>
    <p style="margin-bottom: 1rem; color: #7f8c8d; font-size: 0.875rem;">
        Values are sums across all event pairs per segment from temporal flow analysis.
    </p>
    <div style="overflow-x: auto;">
        <table id="flow-table">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>NAME</th>
                    <th>EVENT</th>
                    <th>FLOW TYPE</th>
                    <th class="sortable" data-sort="overtaking">OVERTAKING <span class="sort-indicator"></span></th>
                    <th>PCT</th>
                    <th class="sortable" data-sort="copresence">CO-PRESENCE <span class="sort-indicator"></span></th>
                </tr>
            </thead>
            <tbody id="flow-tbody">
                <tr>
                    <td colspan="7" class="placeholder">Loading flow data...</td>
                </tr>
            </tbody>
        </table>
    </div>
</div>

<!-- Flow Reference -->
<div class="card">
    <h3 style="margin-bottom: 1rem;">Flow Reference</h3>
    <p style="margin-bottom: 1rem; color: #666; font-size: 0.9rem;">
        Definitions for key metrics in the temporal flow analysis.
    </p>
    <table>
        <thead>
            <tr>
                <th>Column</th>
                <th>Description</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><strong>Event A / Event B</strong></td>
                <td>The two event cohorts being compared (e.g., Full vs Half Marathon). Each pair shows interactions between participants from these events along a segment.</td>
            </tr>
            <tr>
                <td><strong>Flow Type</strong></td>
                <td>Indicates the interaction pattern between the two events:<br>
                • <em>Overtake</em>: Participants in one event pass another.<br>
                • <em>Parallel</em>: Both events move in the same direction concurrently.<br>
                • <em>Counterflow</em>: Participants move in opposite directions on the same path.</td>
            </tr>
            <tr>
                <td><strong>Overtaking A / Overtaking B</strong></td>
                <td>The number of overtake events detected where runners in Event A (or B) passed participants from the paired event within that segment.</td>
            </tr>
            <tr>
                <td><strong>Pct A / Pct B</strong></td>
                <td>The percentage of participants from Event A (or B) involved in overtaking interactions relative to their total count on that segment.</td>
            </tr>
            <tr>
                <td><strong>Co-presence A / Co-presence B</strong></td>
                <td>The number of times participants from Event A and Event B occupied the same segment simultaneously (a measure of concurrent use or congestion).</td>
            </tr>
        </tbody>
    </table>
</div>

{% endblock %}

{% block extra_scripts %}
<script>
    let flowData = {};
    let currentSort = { column: null, direction: 'asc' }; // 'asc' or 'desc' (Issue #596: Fix - moved outside DOMContentLoaded)
    
    // Load flow data on page load
    document.addEventListener('DOMContentLoaded', function() {
        initializeSorting();
        loadFlowData();
    });
    
    function loadFlowData() {
        // Get run_id and day from URL or global state
        const params = new URLSearchParams(window.location.search);
        const dayParam = params.get('day');
        const runParam = params.get('run_id');
        
        const day = (dayParam || (window.runflowDay && window.runflowDay.selected) || '').toLowerCase().trim();
        const run_id = (runParam || (window.runflowDay && window.runflowDay.run_id) || '').trim();
        
        if (!day || !run_id) {
            console.error('❌ Refusing to fetch flow data without day+run_id', {
                href: window.location.href,
                dayParam, runParam,
                runflowDay: window.runflowDay
            });
            showFlowError();
            return;
        }
        
        const apiUrl = `/api/flow/segments?run_id=${encodeURIComponent(run_id)}&day=${encodeURIComponent(day)}`;
        console.log('Loading flow data via API...', { apiUrl, day, run_id });
        
        fetch(apiUrl, { cache: 'no-store' })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`API returned ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                // Handle new response format with selected_day/available_days
                const flow = data.flow || data;
                flowData = flow;
                renderFlowTable(flow);
            })
            .catch(error => {
                console.error('Error loading flow data:', error);
                showFlowError();
            });
    }
    
    function renderFlowTable(flow) {
        const tbody = document.getElementById('flow-tbody');
        tbody.innerHTML = '';
        
        const segments = Object.values(flow);
        
        if (!segments || segments.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="placeholder">No flow data available</td></tr>';
            return;
        }
        
        // Apply sorting if column is selected
        let sortedSegments = segments;
        if (currentSort.column) {
            sortedSegments = sortSegments(segments, currentSort.column, currentSort.direction);
        } else {
            // Default sort by id
            sortedSegments = [...segments].sort((a, b) => a.id.localeCompare(b.id));
        }
        
        sortedSegments.forEach(segment => {
            const row = document.createElement('tr');
            
            // Handle null/missing values with fallback to "—"
            const eventA = segment.event_a || "—";
            const eventB = segment.event_b || "—";
            const overtakingA = segment.overtaking_a !== null && segment.overtaking_a !== undefined ? segment.overtaking_a.toFixed(0) : "—";
            const overtakingB = segment.overtaking_b !== null && segment.overtaking_b !== undefined ? segment.overtaking_b.toFixed(0) : "—";
            const pctA = segment.pct_a !== null && segment.pct_a !== undefined ? segment.pct_a.toFixed(1) + "%" : "—";
            const pctB = segment.pct_b !== null && segment.pct_b !== undefined ? segment.pct_b.toFixed(1) + "%" : "—";
            const copresenceA = segment.copresence_a !== null && segment.copresence_a !== undefined ? segment.copresence_a.toFixed(0) : "—";
            const copresenceB = segment.copresence_b !== null && segment.copresence_b !== undefined ? segment.copresence_b.toFixed(0) : "—";
            
            row.innerHTML = `
                <td>${segment.id}</td>
                <td>${segment.name}</td>
                <td class="event-pair">${eventA} / ${eventB}</td>
                <td>${segment.flow_type || 'overtake'}</td>
                <td class="numeric-pair">${overtakingA} / ${overtakingB}</td>
frontend/templates/pages/flow.html
```

**API change needed**
/api/flow/segments currently reads only Flow.csv and returns flat rows. You will need either:
1. New endpoint for zone details (reading fz files), or
2. Extend /api/flow/segments to include zones for each segment.

Current API is here for reference.

```python
# Create router
router = APIRouter()

# Issue #466 Step 2: Removed legacy storage singleton (not needed)


@router.get("/api/flow/segments")
async def get_flow_segments(
    run_id: Optional[str] = Query(None, description="Run ID (defaults to latest)"),
    day: Optional[str] = Query(None, description="Day code (fri|sat|sun|mon)")
):
    """
    Get flow analysis data for all segments from Flow CSV.
    
    Args:
        run_id: Optional run ID (defaults to latest)
        day: Optional day code (fri|sat|sun|mon) for day-scoped data
    
    Returns:
        Array of flow records with event pairs.
        Each row represents a segment-event_a-event_b combination.
    """
    try:
        # Issue #460 Phase 5: Get latest run_id from runflow/latest.json
        import pandas as pd
        from app.utils.run_id import get_latest_run_id, resolve_selected_day
        from app.storage import create_runflow_storage
        
        # Resolve run_id and day
        if not run_id:
            run_id = get_latest_run_id()
        selected_day, available_days = resolve_selected_day(run_id, day)
        storage = create_runflow_storage(run_id)
        
        # Load Flow CSV from day-scoped path
        try:
            # Flow.csv is at: runflow/<run_id>/<day>/reports/Flow.csv
            csv_content = storage.read_text(f"{selected_day}/reports/Flow.csv")
            
            if not csv_content:
                logger.error("Failed to read Flow CSV: file is empty")
                return JSONResponse(content=[])
            
            # Parse CSV content
            from io import StringIO
            df = pd.read_csv(StringIO(csv_content))
        
        except Exception as e:
            logger.error(f"Failed to load Flow CSV: {e}")
            return JSONResponse(content=[])
        
        # Convert to the format expected by the frontend
        flow_records = []
        for _, row in df.iterrows():
            # Skip empty rows
            if pd.isna(row['seg_id']):
                continue
                
            flow_record = {
                "id": str(row['seg_id']),
                "name": str(row['segment_label']),
                "event_a": str(row['event_a']),
                "event_b": str(row['event_b']),
                "flow_type": str(row['flow_type']),
                "overtaking_a": float(row['overtaking_a']) if pd.notna(row['overtaking_a']) else 0.0,
                "pct_a": float(row['pct_a']) if pd.notna(row['pct_a']) else 0.0,
                "overtaking_b": float(row['overtaking_b']) if pd.notna(row['overtaking_b']) else 0.0,
                "pct_b": float(row['pct_b']) if pd.notna(row['pct_b']) else 0.0,
                "copresence_a": float(row['copresence_a']) if pd.notna(row['copresence_a']) else 0.0,
                "copresence_b": float(row['copresence_b']) if pd.notna(row['copresence_b']) else 0.0
            }
            flow_records.append(flow_record)
        
        logger.info(f"Loaded {len(flow_records)} flow records for day {selected_day}")
        
        response = JSONResponse(content={
            "selected_day": selected_day,
            "available_days": available_days,
            "flow": flow_records
        })
        response.headers["Cache-Control"] = "public, max-age=60"
        return response
        
    except ValueError as e:
        # Convert ValueError from resolve_selected_day to HTTPException
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
    	```

## 6) Future visualization ideas for zone_index (heatmap-like)
Given the columns in sun_fz_202601071257.csv, you can build a zone heatmap-style visualization with:
- X-axis: zone_index
- Color intensity:
   - copresence_a + copresence_b, or
   - overtaking_a + overtaking_b, or
   - unique_encounters

All those metrics are present per zone in the sample file (and align with your “high co-presence / high overtaking” filters).{line_range_start=1 line_range_end=10 path=codex/issue 628/sun_fz_202601071257.csv git_url="https://github.com/thomjeff/run-density/blob/main/codex/issue 628/sun_fz_202601071257.csv#L1-L10"}

This would provide a segment-level “zone intensity strip” similar to density’s heatmap without needing new analytics — purely visualization of existing zone metrics.

## Commands run (for transparency)
- ls codex
- ls "codex/issue 628"
- cat "codex/issue 628/issue628.md"
- ls "codex/7iHmDgGFMZdpjLmZRVgYWY/sun/ui"
- ls "codex/7iHmDgGFMZdpjLmZRVgYWY/sun/ui/visualizations"
- python - <<'PY' ... (loaded captions.json & printed structure)
- find codex/7iHmDgGFMZdpjLmZRVgYWY -name "Flow.csv" -print
- python - <<'PY' ... (inspected Flow.csv columns)
- find codex/7iHmDgGFMZdpjLmZRVgYWY -name "*_fz.parquet" -print
- python - <<'PY' ... (inspected sun_fz.parquet columns)
- python - <<'PY' ... (inspected sun_fz_202601071257.csv)
- nl -ba ... (for line references in Flow.csv / fz CSV / captions.json)

If you want, I can produce a follow‑up research note that maps the precise “caption JSON format” for flow zones (fields, naming, and example output structure) to make the UI integration straightforward.