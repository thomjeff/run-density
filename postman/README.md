# Postman Test Collections for Runflow API

**Version:** v2.0.2+  
**Last Updated:** 2025-01-26  
**Purpose:** Manage Postman test cases in GitHub for the Runflow v2 API

---

## Overview

This directory contains Postman collections and environments for testing the Runflow v2 API. Collections are stored as JSON files in GitHub and can be imported into Postman using the import feature.

**Key Benefits:**
- ✅ Version-controlled test cases in GitHub
- ✅ Team collaboration via pull requests
- ✅ Easy import into Postman workspace
- ✅ CI/CD integration with Newman (Postman CLI)
- ✅ Multiple test scenarios matching E2E test suite

---

## Directory Structure

```
postman/
├── README.md                    # This file
├── collections/
│   ├── Runflow-v2-API.postman_collection.json    # Main collection (all test cases)
│   ├── Runflow-v2-Scenarios.postman_collection.json  # Scenario-based tests
│   └── Runflow-v2-StartTime-Manipulation.postman_collection.json  # Start-time manipulation tests
└── environments/
    ├── Local.postman_environment.json            # Local development (localhost:8080)
    ├── Docker.postman_environment.json          # Docker Compose (app:8080)
    └── Cloud.postman_environment.json           # Cloud Run (production URL)
```

---

## Quick Start

### 1. Import Collection into Postman

**Option A: Import from GitHub (Recommended)**
1. Open Postman
2. Click **Import** button
3. Select **Code Repository** → **GitHub**
4. Authenticate with GitHub
5. Navigate to `run-density` repository
6. Select `postman/collections/Runflow-v2-API.postman_collection.json`
7. Click **Import**

**Option B: Import from Local File**
1. Open Postman
2. Click **Import** button
3. Select **File** → **Upload Files**
4. Navigate to `postman/collections/Runflow-v2-API.postman_collection.json`
5. Click **Import**

### 2. Import Environment

1. In Postman, click **Import** again
2. Select `postman/environments/Local.postman_environment.json`
3. Click **Import**
4. Select the imported environment from the environment dropdown (top right)

### 3. Run Tests

1. Select the **Runflow v2 API** collection
2. Click **Run** button
3. Select which requests to run
4. Click **Run Runflow v2 API**

---

## Test Collections

### Main Collection: `Runflow-v2-API.postman_collection.json`

Contains all test cases organized by category:

**Health & Status:**
- `GET /health` - Health check
- `GET /debug` - Debug ping (for coverage testing)

**Analysis Endpoints:**
- `POST /runflow/v2/analyze` - Main analysis endpoint

**Test Scenarios:**
- **Saturday Only** - Elite + Open events
- **Sunday Only** - Full + 10k + Half events
- **Sat+Sun Combined** - All events across both days
- **Mixed Day** - Cross-day isolation validation
- **Error Cases** - Validation error scenarios

**Each test includes:**
- Pre-request scripts (variable setup)
- Test scripts (assertions)
- Response validation
- Run ID extraction for follow-up requests
- `enableAudit: "y"` - All analyze requests enable audit generation (Issue #607)

### Scenario Collection: `Runflow-v2-Scenarios.postman_collection.json`

Focused scenario-based tests for specific use cases:
- Baseline race configuration
- Scenario: Move 10k to Saturday
- Scenario: Adjust start times
- Error handling scenarios

### Start Time Manipulation Collection: `Runflow-v2-StartTime-Manipulation.postman_collection.json`

**Purpose:** Validate system behavior changes when start_time parameters are manipulated, with clear expectations for flow, density, and co-presence impacts.

**Test Cases:**
1. **WIDEN Start-Time Gaps (Reduce Overlap)**
   - Full: 360 (6:00 AM), 10K: 420 (7:00 AM), Half: 540 (9:00 AM)
   - Expected: Reduced co-presence, spread-out peak density timestamps
   
2. **COMPRESS Start-Time Gaps (Force Overlap)**
   - Full: 420 (7:00 AM), 10K: 425 (7:05 AM), Half: 430 (7:10 AM)
   - Expected: Increased co-presence, higher overtake counts, closer peak timestamps
   
3. **UNIFORM Start Times (Maximum Co-located Flow)**
   - All events: 420 (7:00 AM)
   - Expected: Superimposed density spikes, maximum concurrency in first 30-60 minutes

**Note:** All test cases include `enableAudit: "y"` to generate audit Parquet files for detailed flow analysis (Issue #607).

**Validation:**
Each test case includes console output with validation instructions. After analysis completes, check:
- `runflow/{run_id}/sun/reports/Flow.csv` - Co-presence and overtake counts
- `runflow/{run_id}/sun/reports/Density.md` - Peak density timestamps
- `runflow/{run_id}/sun/audit/audit_sun.parquet` - Detailed audit data (Issue #607)
- Compare results across all three test cases to verify system responds differently to start time changes

---

## Environments

### Local Environment (`Local.postman_environment.json`)

For local development:
```json
{
  "base_url": "http://localhost:8080",
  "data_dir": "/data"
}
```

**Usage:** When running `make dev` locally

### Docker Environment (`Docker.postman_environment.json`)

For Docker Compose network:
```json
{
  "base_url": "http://app:8080",
  "data_dir": "/app/runflow/config/sample"
}
```

**Usage:** When running tests inside Docker network (e.g., `docker exec`)

**Note:** The `data_dir` parameter (Issue #680) allows you to specify a custom data directory. The default `/app/runflow/config/sample` can be changed by replacing "sample" with your desired sub-directory name. All analyze requests include `data_dir` in the request body, which will use this environment variable value.

### Cloud Environment (`Cloud.postman_environment.json`)

For production/Cloud Run:
```json
{
  "base_url": "https://your-cloud-run-url.run.app",
  "data_dir": "/data"
}
```

**Usage:** For testing deployed instances

---

## Test Cases

### 1. Saturday Only Scenario

**Request:**
```json
POST {{base_url}}/runflow/v2/analyze
{
  "description": "Saturday only scenario test with audit",
  "data_dir": "{{data_dir}}",
  "segments_file": "segments.csv",
  "flow_file": "flow.csv",
  "locations_file": "locations.csv",
  "enableAudit": "y",
  "events": [
    {
      "name": "elite",
      "day": "sat",
      "start_time": 480,
      "event_duration_minutes": 45,
      "runners_file": "elite_runners.csv",
      "gpx_file": "elite.gpx"
    },
    {
      "name": "open",
      "day": "sat",
      "start_time": 510,
      "event_duration_minutes": 75,
      "runners_file": "open_runners.csv",
      "gpx_file": "open.gpx"
    }
  ]
}
```

**Note:** The `data_dir` field (Issue #680) is included in all analyze requests. It uses the `{{data_dir}}` environment variable, which defaults to `/app/runflow/config/sample` for Docker environment. Users can replace "sample" with any sub-directory name in the environment variable to use different configuration files.

**Note:** All analyze requests include `enableAudit: "y"` to generate audit Parquet files for detailed flow analysis (Issue #607).

**Validations:**
- Status code: 200
- Response contains `run_id`
- Response contains `days: ["sat"]`
- Response contains `output_paths.sat`

### 2. Sunday Only Scenario

**Request:** Similar structure with `full`, `10k`, `half` events on `sun` day

**Validations:**
- Status code: 200
- Response contains `days: ["sun"]`
- All three events processed

### 3. Sat+Sun Combined Scenario

**Request:** All five events across both days

**Validations:**
- Status code: 200
- Response contains `days: ["sat", "sun"]`
- Both day outputs present

### 4. Error Cases

**Missing Required Field:**
- Request without `segments_file`
- Expected: 400 Bad Request

**Invalid Start Time:**
- Request with `start_time: 200` (below minimum)
- Expected: 422 Unprocessable Entity

**Missing Flow Pairs:**
- Request with events not in `flow.csv`
- Expected: 422 Unprocessable Entity

---

## Variables

Collections use Postman variables for flexibility:

| Variable | Description | Example |
|----------|-------------|---------|
| `base_url` | API base URL | `http://localhost:8080` |
| `run_id` | Latest run ID (auto-extracted) | `hCjWfQNKMePnRkrN4GX9Rj` |
| `data_dir` | Data directory path (Issue #680) | `/app/runflow/config/sample` (Docker) or `/data` (Local/Cloud) |

**Auto-extracted Variables:**
- `run_id` - Extracted from analyze response
- `sat_metadata_path` - Path to Saturday metadata
- `sun_metadata_path` - Path to Sunday metadata

---

## CI/CD Integration

### Using Newman (Postman CLI)

Run tests in CI/CD pipeline:

```bash
# Install Newman
npm install -g newman

# Run collection
newman run postman/collections/Runflow-v2-API.postman_collection.json \
  -e postman/environments/Local.postman_environment.json \
  --reporters cli,json \
  --reporter-json-export results.json
```

### GitHub Actions Example

Create `.github/workflows/postman-tests.yml`:

```yaml
name: Postman Tests

on:
  push:
    branches: [ main, dev ]
  pull_request:
    branches: [ main ]

jobs:
  postman-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      
      - name: Install Newman
        run: npm install -g newman
      
      - name: Start Docker services
        run: docker-compose up -d
      
      - name: Wait for server
        run: sleep 10
      
      - name: Run Postman tests
        run: |
          newman run postman/collections/Runflow-v2-API.postman_collection.json \
            -e postman/environments/Docker.postman_environment.json \
            --reporters cli,junit \
            --reporter-junit-export results.xml
      
      - name: Upload test results
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: postman-results
          path: results.xml
```

---

## Syncing with GitHub

### Workflow

1. **Edit in Postman:**
   - Make changes to collection/environment in Postman
   - Test changes locally

2. **Export to GitHub:**
   - In Postman, click collection/environment → **...** → **Export**
   - Save to `postman/collections/` or `postman/environments/`
   - Commit and push to GitHub

3. **Team Sync:**
   - Team members pull latest changes
   - Re-import collection/environment in Postman
   - Changes are automatically synced

### Best Practices

- ✅ **Commit frequently** - Keep collections in sync with code changes
- ✅ **Use descriptive commit messages** - "Add error case test for missing flow pairs"
- ✅ **Review in PRs** - Use pull requests to review test changes
- ✅ **Version collections** - Tag major collection versions
- ✅ **Document changes** - Update this README when adding new tests

---

## Comparison with E2E Tests

| Aspect | Postman | E2E Tests (pytest) |
|--------|---------|---------------------|
| **Purpose** | Manual testing, API exploration | Automated testing, CI/CD |
| **Location** | `postman/collections/` | `tests/v2/e2e.py` |
| **Execution** | Postman UI or Newman CLI | `make e2e` or `pytest` |
| **Validation** | Postman test scripts | Python assertions |
| **Use Case** | Quick API testing, debugging | Regression testing, validation |

**Both are valuable:**
- Use **Postman** for manual testing and API exploration
- Use **E2E tests** for automated regression testing

---

## Troubleshooting

### Import Issues

**Problem:** Collection won't import
- **Solution:** Ensure JSON is valid (use JSON validator)
- **Solution:** Check Postman version (requires v9+)

### Environment Variables Not Working

**Problem:** Variables show as `{{base_url}}` instead of actual URL
- **Solution:** Select environment from dropdown (top right)
- **Solution:** Verify environment file is imported

### Tests Failing

**Problem:** Tests pass in Postman but fail in Newman
- **Solution:** Check environment file path in Newman command
- **Solution:** Verify server is running before tests
- **Solution:** Check Newman version: `newman --version`

---

## Resources

- **Postman Documentation:** https://learning.postman.com/
- **Newman CLI:** https://learning.postman.com/docs/running-collections/using-newman-cli/command-line-integration/
- **GitHub Integration:** https://learning.postman.com/docs/integrations/available-integrations/github/
- **API User Guide:** `docs/user-guide/api-user-guide.md`
- **E2E Tests:** `tests/v2/e2e.py`

---

**Last Updated:** 2025-01-26  
**Maintained By:** Development Team
