# Run Density

[![Code Quality](https://github.com/thomjeff/run-density/actions/workflows/code-quality.yaml/badge.svg)](https://github.com/thomjeff/run-density/actions/workflows/code-quality.yaml)
[![Combined image](https://github.com/thomjeff/run-density/actions/workflows/combined-image-verify.yaml/badge.svg)](https://github.com/thomjeff/run-density/actions/workflows/combined-image-verify.yaml)

## Overview
This service models runner density on shared course segments using a density engine and temporal flow analysis.  
It provides comprehensive reporting with Markdown and CSV outputs, and is containerized for local development.

**Current Version: v3.1.0** — Execute is a race-day workspace (Reopen · Participants · Incidents). Plan adds Progression; Build owns location edits.

**v3 product chrome:**
- **Build:** Legs · Courses · Runners · Packages (**Edit Locations** on Legs)
- **Plan:** run selector + Overview · Density · Flow · Junctions · Motion · Progression · Locations
- **Execute:** Reopen · Participants · Incidents
- Day is derived from the selected run (no Plan day dropdown)
- Overview **Exports** downloads Reports and Data Files as ZIPs; `/reports` and `/segments` redirect to Overview and Density

## Key Features
- **Density Analysis**: Spatial concentration with LOS, Peak Window, and Field Window on the Plan Density workspace (course map + Segment Analysis)
- **Temporal Flow Analysis**: Convergence and overtaking between events (numeric Segment ID order; unique overtakers / overtaken)
- **Heatmap Visualizations**: PNG heatmaps for race segments
- **Exports**: Allow-listed report and data-file ZIPs from Overview
- **RESTful API**: FastAPI with configurable analysis parameters
- **Web UI**: Create (Build + Plan) at http://localhost:8080; Execute at http://localhost:8081

## Quick Start (Local Development)

### Docker Development (Local-Only)

Two environments. **Create** is Build + Plan (author a race). **Execute** is race day. Both can run at once. They do not share a filesystem; publish a Day Plan ZIP from Create and import it in Execute.

```bash
make create          # Build + Plan on http://localhost:8080 (hot reload)
make execute         # Execute + Postgres on http://localhost:8081
make stop-create     # Create only
make stop-execute    # Execute and Postgres only
```

Execute copies code at image build time. Run `make execute` again after Execute backend or frontend changes.

**📖 Full Documentation:** See [`docs/README.md`](docs/README.md) and [`docs/dev-guides/docker-dev.md`](docs/dev-guides/docker-dev.md).

## Web UI Features

### Plan workspace
- **Overview**: Analysis inputs/outputs plus **Exports** (`Reports (.zip)` / `Data Files (.zip)`)
- **Density**: LOS-coloured course map, Segment Analysis table, selected-segment heatmap and assessment
- **Flow / Junctions / Motion / Progression / Locations**: analytical views for the selected run
- Pick a run from **Runs ▾** (opens Overview). `/dashboard` is the run catalog.

### Heatmaps
- Stored under `runflow/analysis/<run_id>/<day>/ui/visualizations/`
- Served at `/heatmaps/analysis/<run_id>/<day>/ui/visualizations/<seg_id>.png`

### Access the Web UI
- **Create (Build + Plan)**: http://localhost:8080
- **Execute (race day)**: http://localhost:8081

## Report Generation

### CLI Tools
Generate comprehensive reports using command-line tools:

> **Note**: Legacy CLI scripts have been moved to `archive/` directory. The examples below use the modern module-based approach.

**Temporal Flow Report** (Markdown + CSV):
```bash
python3 -c "
from app.temporal_flow_report import generate_temporal_flow_report
result = generate_temporal_flow_report('data/runners.csv', 'data/segments_new.csv', {'10K': 420, 'Half': 440, 'Full': 460})
print(f'Report generated: {result[\"md_file\"]}')
"
```

**Density Report** (Markdown):
```bash
python3 -c "
from app.density_report import generate_density_report
result = generate_density_report('data/runners.csv', 'data/segments_new.csv', {'10K': 420, 'Half': 440, 'Full': 460})
print(f'Report generated: {result[\"md_file\"]}')
"
```

### API Endpoints
Generate reports via REST API:

**Temporal Flow Report**:
```bash
curl -X POST "http://localhost:8080/api/temporal-flow-report" \
  -H "Content-Type: application/json" \
  -d '{
    "paceCsv": "data/your_pace_data.csv",
    "segmentsCsv": "data/segments.csv",
    "startTimes": {"Full": 420, "10K": 440, "Half": 460},
    "outputDir": "reports/analysis"
  }'
```

**Density Report**:
```bash
curl -X POST "http://localhost:8080/api/density-report" \
  -H "Content-Type: application/json" \
  -d '{
    "paceCsv": "data/your_pace_data.csv",
    "densityCsv": "data/density.csv",
    "startTimes": {"Full": 420, "10K": 440, "Half": 460},
    "outputDir": "reports/analysis"
  }'
```

---

## Makefile Commands

- `make create` – start Create (Build + Plan) on `http://localhost:8080` with hot-reload
- `make execute` – start Execute + Postgres on `http://localhost:8081`
- `make stop-create` – stop Create only
- `make stop-execute` – stop Execute and Postgres only
- `make prune-runs KEEP=n` – prune old run_ids, keeping last n
- `make ai-prompt RUN_ID=...` – generate an AI prompt for a run_id  

---

## Code Quality

PRs run **GitHub Actions** Code Quality (`.github/workflows/code-quality.yaml`) on changed `app/` Python files, and **combined-image verify** (`.github/workflows/combined-image-verify.yaml`) for Create Build / Plan. See [`docs/dev-guides/release-preservation.md`](docs/dev-guides/release-preservation.md). Settings live in `.flake8` and `pyproject.toml` (#940). `main` is not branch-protected; treat a red Code Quality run as a blocker anyway.

### Quality Checks (On Pull Requests)

1. **flake8** — `.flake8`
   - Line length **88** (same as black). `E501` is ignored; black wraps what it can
   - Max complexity: 15 (`C901`). Existing leftovers are `# noqa: C901`; new functions must stay under 15
   - Also blocks unused names (`F`), bare `except` (`B001` / `E722`), and remaining E/W style
   - Ignores black conflicts (`E203`, `W503`) and leftover `sys.path` then import (`E402`)

2. **black** — `pyproject.toml`, line length 88

3. **isort** — `pyproject.toml`, black profile, line length 88

---

## Testing

Run a new plan from the Create UI or Postman. Unit and combined-image regression run in GitHub Actions on every PR. The old Saturday/Sunday `tests/e2e.py` runner is archived under `tests/archive/` and is not a Make target.

---

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Development setup
- Testing requirements
- Branch naming and commit conventions
- Pull request process

**Quick Start for Contributors:**
```bash
git clone https://github.com/thomjeff/run-density.git
cd run-density
make create        # Start Create (Build + Plan) on :8080
make execute       # Start Execute on :8081 (optional)
```

---

## License
MIT
