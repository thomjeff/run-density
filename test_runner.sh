#!/usr/bin/env bash
set -euo pipefail

# --- load .env if present ----------------------------------------------------
ENV_FILE="${ENV_FILE:-.env}"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

# --- defaults (can be overridden by .env) ------------------------------------
ENVIRONMENT="${ENVIRONMENT:-local}"
LOCAL_URL="${LOCAL_URL:-http://localhost:8081}"
PROD_URL="${PROD_URL:-https://run-density-ln4r3sfkha-uc.a.run.app}"
API_URL="${API_URL:-}"
PACE_CSV="${PACE_CSV:-data/your_pace_data.csv}"
OVERLAPS_CSV="${OVERLAPS_CSV:-data/overlaps.csv}"
START_TIMES_JSON="${START_TIMES_JSON:-{\"Full\":420,\"10K\":440,\"Half\":460}}"
TIME_WINDOW="${TIME_WINDOW:-300}"
STEP_KM="${STEP_KM:-0.03}"
DEPTH_M="${DEPTH_M:-3.0}"
VERBOSE="${VERBOSE:-false}"
DRY_RUN="${DRY_RUN:-false}"

# --- color functions ---------------------------------------------------------
log_info() {
  echo -e "\033[1;34mℹ️  $1\033[0m"
}

log_success() {
  echo -e "\033[1;32m✅ $1\033[0m"
}

log_error() {
  echo -e "\033[1;31m❌ $1\033[0m"
}

log_test() {
  echo -e "\033[1;35m🧪 $1\033[0m"
}

# --- interactive menu --------------------------------------------------------
show_interactive_menu() {
  clear
  echo "╔══════════════════════════════════════════════════════════════╗"
  echo "║                    RUN-DENSITY TEST RUNNER                   ║"
  echo "║                        Interactive Menu                       ║"
  echo "╚══════════════════════════════════════════════════════════════╝"
  echo ""
  
  # Show current environment
  local current_url
  case "$ENVIRONMENT" in
    local) current_url="$LOCAL_URL" ;;
    prod) current_url="$PROD_URL" ;;
    custom) current_url="$API_URL" ;;
    *) current_url="$LOCAL_URL" ;;
  esac
  
  echo "🌍 Environment: $ENVIRONMENT ($current_url)"
  echo "📁 Pace CSV: $PACE_CSV"
  echo "📁 Overlaps CSV: $OVERLAPS_CSV"
  echo ""
  
  echo "📋 Available Tests:"
  echo "  1. Health Check"
  echo "  2. Service Readiness"
  echo "  3. Density Endpoint"
  echo "  4. Overlap Endpoints"
  echo "  5. Map Endpoints"
  echo "  6. Run All Tests"
  echo ""
  echo "⚙️  Options:"
  echo "  7. Change Environment"
  echo "  8. Change CSV Paths"
  echo "  9. Show Current Settings"
  echo "  0. Exit"
  echo ""
  
  read -p "Select an option (0-9): " choice
  
  case "$choice" in
    1) run_health_test ;;
    2) run_ready_test ;;
    3) run_density_test ;;
    4) run_overlap_test ;;
    5) run_map_test ;;
    6) run_all_tests ;;
    7) change_environment ;;
    8) change_csv_paths ;;
    9) show_current_settings ;;
    0) echo "👋 Goodbye!"; exit 0 ;;
    *) echo "❌ Invalid option. Please try again."; sleep 2; show_interactive_menu ;;
  esac
}

change_environment() {
  clear
  echo "🌍 Environment Selection:"
  echo "  1. Local (http://localhost:8081)"
  echo "  2. Production (Cloud Run)"
  echo "  3. Custom URL"
  echo "  4. Back to main menu"
  echo ""
  
  read -p "Select environment (1-4): " env_choice
  
  case "$env_choice" in
    1) ENVIRONMENT="local"; API_URL="" ;;
    2) ENVIRONMENT="prod"; API_URL="" ;;
    3) read -p "Enter custom URL: " custom_url; ENVIRONMENT="custom"; API_URL="$custom_url" ;;
    4) show_interactive_menu; return ;;
    *) echo "❌ Invalid option."; sleep 1; change_environment; return ;;
  esac
  
  echo "✅ Environment changed to: $ENVIRONMENT"
  sleep 1
  show_interactive_menu
}

change_csv_paths() {
  clear
  echo "📁 CSV Path Configuration:"
  echo "Current Pace CSV: $PACE_CSV"
  echo "Current Overlaps CSV: $OVERLAPS_CSV"
  echo ""
  
  read -p "Enter new Pace CSV path (or press Enter to keep current): " new_pace
  if [[ -n "$new_pace" ]]; then
    PACE_CSV="$new_pace"
  fi
  
  read -p "Enter new Overlaps CSV path (or press Enter to keep current): " new_overlaps
  if [[ -n "$new_overlaps" ]]; then
    OVERLAPS_CSV="$new_overlaps"
  fi
  
  echo "✅ CSV paths updated"
  sleep 1
  show_interactive_menu
}

show_current_settings() {
  clear
  echo "⚙️  Current Settings:"
  echo "  Environment: $ENVIRONMENT"
  case "$ENVIRONMENT" in
    local) echo "  URL: $LOCAL_URL" ;;
    prod) echo "  URL: $PROD_URL" ;;
    custom) echo "  URL: $API_URL" ;;
  esac
  echo "  Pace CSV: $PACE_CSV"
  echo "  Overlaps CSV: $OVERLAPS_CSV"
  echo "  Start Times: $START_TIMES_JSON"
  echo "  Time Window: $TIME_WINDOW seconds"
  echo "  Step KM: $STEP_KM"
  echo "  Depth M: $DEPTH_M"
  echo ""
  read -p "Press Enter to continue..."
  show_interactive_menu
}

# --- test functions ---------------------------------------------------------
run_health_test() {
  log_test "Health Check Test"
  local url
  url=$(get_api_url)
  
  log_info "Testing health endpoint..."
  if $CURL_BIN -fsS "$url/health" >/dev/null 2>&1; then
    log_success "Health endpoint test passed"
  else
    log_error "Health endpoint test failed"
  fi
  
  echo ""
  read -p "Press Enter to continue..."
  show_interactive_menu
}

run_ready_test() {
  log_test "Service Readiness Test"
  local url
  url=$(get_api_url)
  
  log_info "Testing ready endpoint..."
  if $CURL_BIN -fsS "$url/ready" >/dev/null 2>&1; then
    log_success "Ready endpoint test passed"
  else
    log_error "Ready endpoint test failed"
  fi
  
  echo ""
  read -p "Press Enter to continue..."
  show_interactive_menu
}

run_density_test() {
  log_test "Density Endpoint Test"
  local url
  url=$(get_api_url)
  
  log_info "Testing density endpoint..."
  local payload
  payload=$(cat <<JSON
{
  "paceCsv": "$PACE_CSV",
  "overlapsCsv": "$OVERLAPS_CSV",
  "startTimes": $START_TIMES_JSON,
  "stepKm": $STEP_KM,
  "timeWindow": $TIME_WINDOW,
  "depth_m": $DEPTH_M
}
JSON
)
  
  if $CURL_BIN -fsS -X POST "$url/api/density.summary" \
      -H "Content-Type: application/json" \
      -d "$payload" >/dev/null 2>&1; then
    log_success "Density endpoint test passed"
  else
    log_error "Density endpoint test failed"
  fi
  
  echo ""
  read -p "Press Enter to continue..."
  show_interactive_menu
}

run_overlap_test() {
  log_test "Overlap Endpoints Test"
  local url
  url=$(get_api_url)
  
  # Test 1: Basic overlap analysis (text)
  log_info "Testing overlap endpoint (text)..."
  local payload1
  payload1=$(cat <<JSON
{
  "paceCsv": "$PACE_CSV",
  "overlapsCsv": "$OVERLAPS_CSV",
  "startTimes": $START_TIMES_JSON,
  "stepKm": $STEP_KM,
  "timeWindow": $TIME_WINDOW,
  "depth_m": $DEPTH_M
}
JSON
)
  
  if $CURL_BIN -fsS -X POST "$url/api/overlap" \
      -H "Content-Type: application/json" \
      -d "$payload1" >/dev/null 2>&1; then
    log_success "overlap endpoint (text) test passed"
  else
    log_error "overlap endpoint (text) test failed"
  fi
  
  # Test 2: Overlap analysis with CSV export
  log_info "Testing overlap endpoint (CSV export)..."
  if $CURL_BIN -fsS -X POST "$url/api/overlap?export_csv=true" \
      -H "Content-Type: application/json" \
      -d "$payload1" >/dev/null 2>&1; then
    log_success "overlap endpoint (CSV export) test passed"
  else
    log_error "overlap endpoint (CSV export) test failed"
  fi
  
  echo ""
  read -p "Press Enter to continue..."
  show_interactive_menu
}

run_map_test() {
  log_test "Map Endpoints Test"
  local url
  url=$(get_api_url)
  
  # Test map endpoint
  log_info "Testing map endpoint..."
  if $CURL_BIN -fsS "$url/map" >/dev/null 2>&1; then
    log_success "Map endpoint test passed"
  else
    log_error "Map endpoint test failed"
  fi
  
  # Test segments GeoJSON endpoint
  log_info "Testing segments GeoJSON endpoint..."
  if $CURL_BIN -fsS "$url/api/segments.geojson" >/dev/null 2>&1; then
    log_success "Segments GeoJSON endpoint test passed"
  else
    log_error "Segments GeoJSON endpoint test failed"
  fi
  
  echo ""
  read -p "Press Enter to continue..."
  show_interactive_menu
}

run_all_tests() {
  log_test "Running All Tests"
  echo ""
  
  run_health_test
  run_ready_test
  run_density_test
  run_overlap_test
  run_map_test
  
  echo ""
  log_success "All tests completed!"
  read -p "Press Enter to continue..."
  show_interactive_menu
}

# --- helper functions -------------------------------------------------------
get_api_url() {
  case "$ENVIRONMENT" in
    local) echo "$LOCAL_URL" ;;
    prod) echo "$PROD_URL" ;;
    custom) echo "$API_URL" ;;
    *) echo "$LOCAL_URL" ;;
  esac
}

# --- main logic ------------------------------------------------------------
main() {
  # Check if curl is available
  if ! command -v curl >/dev/null 2>&1; then
    log_error "curl is required but not installed"
    exit 1
  fi
  
  CURL_BIN="curl"
  
  # If no arguments provided, show interactive menu
  if [[ $# -eq 0 ]]; then
    show_interactive_menu
    exit 0
  fi
  
  # Otherwise, run as command-line tool (existing functionality)
  case "$1" in
    health) run_health_test ;;
    ready) run_ready_test ;;
    density) run_density_test ;;
    overlaps) run_overlap_test ;;
    map) run_map_test ;;
    all) run_all_tests ;;
    list) 
      echo "Available commands: health, ready, density, overlaps, map, all, list"
      echo "Run without arguments for interactive menu"
      ;;
    --help|-h)
      cat <<HELP
Usage: $0 [COMMAND] [OPTIONS]

COMMANDS:
  health       - Basic health check
  ready        - Service readiness check
  density      - Test density endpoint
  overlaps     - Test overlap endpoints
  map          - Test map endpoints
  all          - Run all tests
  list         - List all available tests
  (no args)    - Show interactive menu

OPTIONS:
  --env ENV    - Environment: local, prod, or custom URL
  --dry-run    - Show commands without executing
  --verbose    - Verbose output
  --help       - Show this help

ENVIRONMENT VARIABLES (can be set in .env):
  ENVIRONMENT  - local, prod, or custom
  LOCAL_URL    - Local service URL (default: http://localhost:8081)
  PROD_URL     - Production service URL
  API_URL      - Custom API URL (overrides ENVIRONMENT)
  PACE_CSV     - Path to pace CSV (default: data/your_pace_data.csv)
  OVERLAPS_CSV - Path to overlaps CSV (default: data/overlaps.csv)
  START_TIMES_JSON - Start times JSON (default: {"Full":420,"10K":440,"Half":460})
  TIME_WINDOW  - Time window in seconds (default: 300)
  STEP_KM      - Step distance in km (default: 0.03)
  DEPTH_M      - Segment depth in meters (default: 3.0)

EXAMPLES:
  $0                    # Show interactive menu
  $0 health            # Basic health check
  $0 --env prod health # Health check against production
  $0 --env local density # Test density endpoint locally
  $0 --dry-run all    # Show all test commands without running
  $0 overlaps          # Test all overlap endpoints
HELP
      ;;
    *) 
      log_error "Unknown command: $1"
      echo "Run '$0 --help' for usage information"
      echo "Run '$0' (no arguments) for interactive menu"
      exit 1
      ;;
  esac
}

# Run main function with all arguments
main "$@"
