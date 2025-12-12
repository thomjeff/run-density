#!/bin/bash
# Test script for v2 analysis API
# Starts container without --reload to avoid duplicate requests during testing

set -e

PORT=${PORT:-8080}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🧪 Testing v2 Analysis API (no reload mode)"
echo ""

# Stop any running container
echo "🛑 Stopping any running containers..."
cd "$PROJECT_DIR"
docker-compose down > /dev/null 2>&1 || true

# Start container without --reload
# Use docker-compose run with command override to disable reload
echo "🚀 Starting container without hot reload..."
docker-compose run --rm -d \
  --name run-density-test \
  --service-ports \
  -e PORT=8080 \
  app \
  uvicorn app.main:app --host 0.0.0.0 --port 8080 \
  > /dev/null 2>&1

# Wait for container to be ready
echo "⏳ Waiting for container to be ready..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
  if curl -fsS "http://localhost:${PORT}/health" > /dev/null 2>&1; then
    echo "✅ Container is ready"
    break
  fi
  attempt=$((attempt + 1))
  sleep 1
done

if [ $attempt -eq $max_attempts ]; then
  echo "❌ Container failed to start"
  docker-compose down > /dev/null 2>&1 || true
  exit 1
fi

# Create test payload
PAYLOAD_FILE=$(mktemp)
cat > "$PAYLOAD_FILE" << 'EOF'
{
  "events": [
    {"name": "full", "day": "sun", "start_time": 420, "runners_file": "full_runners.csv", "gpx_file": "full.gpx"},
    {"name": "10k", "day": "sun", "start_time": 440, "runners_file": "10k_runners.csv", "gpx_file": "10k.gpx"},
    {"name": "half", "day": "sun", "start_time": 460, "runners_file": "half_runners.csv", "gpx_file": "half.gpx"},
    {"name": "elite", "day": "sat", "start_time": 480, "runners_file": "elite_runners.csv", "gpx_file": "5k.gpx"},
    {"name": "open", "day": "sat", "start_time": 510, "runners_file": "open_runners.csv", "gpx_file": "5k.gpx"}
  ]
}
EOF

echo ""
echo "📤 Sending POST request to /runflow/v2/analyze..."
echo ""

# Make API request
RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
  -X POST "http://localhost:${PORT}/runflow/v2/analyze" \
  -H "Content-Type: application/json" \
  -d "@${PAYLOAD_FILE}" \
  --max-time 600)

# Extract HTTP status and body
HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_STATUS/d')

# Clean up payload file
rm -f "$PAYLOAD_FILE"

echo "📥 Response:"
echo "HTTP Status: $HTTP_STATUS"
echo ""

if [ "$HTTP_STATUS" = "200" ]; then
  echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
  echo ""
  
  # Extract run_id from response
  RUN_ID=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin).get('run_id', ''))" 2>/dev/null || echo "")
  
  if [ -n "$RUN_ID" ]; then
    echo "✅ Analysis completed successfully"
    echo "📊 Run ID: $RUN_ID"
    echo ""
    echo "📁 Check results in: /Users/jthompson/Documents/runflow/$RUN_ID/"
  else
    echo "⚠️  Could not extract run_id from response"
  fi
else
  echo "❌ Request failed with status $HTTP_STATUS"
  echo "$BODY"
fi

# Keep container running for log inspection
echo ""
if [ "$HTTP_STATUS" = "200" ]; then
  echo "🎉 Test completed successfully"
  echo ""
  echo "📝 Container 'run-density-test' is still running for log inspection"
  echo "   To view logs: docker logs run-density-test"
  echo "   To stop: docker stop run-density-test && docker rm run-density-test"
  exit 0
else
  echo "❌ Test failed"
  echo ""
  echo "📝 Container 'run-density-test' is still running for debugging"
  echo "   To view logs: docker logs run-density-test"
  echo "   To stop: docker stop run-density-test && docker rm run-density-test"
  exit 1
fi

