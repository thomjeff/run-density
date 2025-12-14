#!/bin/bash
# Test script for Phase 4: Density Pipeline
# Validates that density analysis runs correctly with real data

set -e

echo "=========================================="
echo "Phase 4: Density Pipeline Test"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    exit 1
fi

# Check if container exists
if ! docker-compose ps app | grep -q "Up"; then
    echo -e "${YELLOW}Starting Docker container...${NC}"
    docker-compose up -d app
    sleep 5
fi

echo "1. Testing API endpoint with Sunday events (full, half, 10k)..."
echo ""

# Create test payload
PAYLOAD=$(cat <<EOF
{
  "events": [
    {
      "name": "full",
      "day": "sun",
      "start_time": 420,
      "runners_file": "full_runners.csv",
      "gpx_file": "full.gpx"
    },
    {
      "name": "half",
      "day": "sun",
      "start_time": 440,
      "runners_file": "half_runners.csv",
      "gpx_file": "half.gpx"
    },
    {
      "name": "10k",
      "day": "sun",
      "start_time": 460,
      "runners_file": "10k_runners.csv",
      "gpx_file": "10k.gpx"
    }
  ],
  "segments_file": "segments.csv",
  "locations_file": "locations.csv",
  "flow_file": "flow.csv"
}
EOF
)

# Make API call
echo "Sending POST request to /runflow/v2/analyze..."
RESPONSE=$(docker-compose exec -T app curl -s -X POST "http://localhost:8000/runflow/v2/analyze" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")

echo "Response:"
echo "$RESPONSE" | python3 -m json.tool || echo "$RESPONSE"
echo ""

# Extract run_id
RUN_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('run_id', ''))" 2>/dev/null || echo "")

if [ -z "$RUN_ID" ]; then
    echo -e "${RED}Error: Failed to get run_id from response${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Analysis completed with run_id: $RUN_ID${NC}"
echo ""

# Check logs for density analysis
echo "2. Checking container logs for density analysis..."
echo ""

LOGS=$(docker-compose logs app --tail=100 | grep -i "density\|segment\|runner" | tail -20)
if [ -n "$LOGS" ]; then
    echo "$LOGS"
else
    echo -e "${YELLOW}No density-related logs found${NC}"
fi
echo ""

# Check for output files
echo "3. Checking output files..."
echo ""

RUNFLOW_ROOT="/app/runflow"
SUN_REPORTS="$RUNFLOW_ROOT/$RUN_ID/sun/reports"
SUN_BINS="$RUNFLOW_ROOT/$RUN_ID/sun/bins"

# Check if directories exist
if docker-compose exec -T app test -d "$SUN_REPORTS"; then
    echo -e "${GREEN}✓ Reports directory exists${NC}"
else
    echo -e "${RED}✗ Reports directory missing${NC}"
fi

if docker-compose exec -T app test -d "$SUN_BINS"; then
    echo -e "${GREEN}✓ Bins directory exists${NC}"
else
    echo -e "${RED}✗ Bins directory missing${NC}"
fi

# Check metadata.json
METADATA_FILE="$RUNFLOW_ROOT/$RUN_ID/sun/metadata.json"
if docker-compose exec -T app test -f "$METADATA_FILE"; then
    echo -e "${GREEN}✓ Metadata file exists${NC}"
    echo ""
    echo "Metadata contents:"
    docker-compose exec -T app cat "$METADATA_FILE" | python3 -m json.tool | head -30
else
    echo -e "${RED}✗ Metadata file missing${NC}"
fi
echo ""

# Check density results in metadata
echo "4. Validating density results..."
echo ""

DENSITY_PROCESSED=$(docker-compose exec -T app python3 -c "
import json
import sys
try:
    with open('$METADATA_FILE', 'r') as f:
        data = json.load(f)
        density = data.get('density', {})
        processed = density.get('processed_segments', 0)
        skipped = density.get('skipped_segments', 0)
        total = density.get('total_segments', 0)
        print(f'Processed: {processed}, Skipped: {skipped}, Total: {total}')
        sys.exit(0 if processed > 0 else 1)
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1)

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Density analysis completed: $DENSITY_PROCESSED${NC}"
else
    echo -e "${RED}✗ Density analysis failed or no segments processed${NC}"
    echo "$DENSITY_PROCESSED"
fi
echo ""

# Summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Run ID: $RUN_ID"
echo "Output path: runflow/$RUN_ID/sun/"
echo ""
echo -e "${GREEN}Phase 4 test completed!${NC}"
echo ""
echo "Next steps:"
echo "1. Check logs for segment coverage and runner mapping"
echo "2. Verify bins.parquet will be generated (Phase 6)"
echo "3. Proceed to Phase 5: Flow Pipeline"

