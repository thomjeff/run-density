#!/bin/bash
# Test Runner Script for Run-Density Analysis
# ===========================================
# 
# Usage:
#   ./run_tests.sh [test-id] [options]
#   
# Examples:
#   ./run_tests.sh --list                    # List all available tests
#   ./run_tests.sh temporal_flow_convergence # Run specific test
#   ./run_tests.sh --all                     # Run all tests
#   ./run_tests.sh --smoke                   # Run smoke tests only
#   ./run_tests.sh --comprehensive           # Run comprehensive tests only

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local status=$1
    local message=$2
    case $status in
        "SUCCESS")
            echo -e "${GREEN}✅ $message${NC}"
            ;;
        "ERROR")
            echo -e "${RED}❌ $message${NC}"
            ;;
        "WARNING")
            echo -e "${YELLOW}⚠️  $message${NC}"
            ;;
        "INFO")
            echo -e "${BLUE}ℹ️  $message${NC}"
            ;;
    esac
}

# Function to show usage
show_usage() {
    echo "Test Runner Script for Run-Density Analysis"
    echo "==========================================="
    echo ""
    echo "Usage: $0 [test-id] [options]"
    echo ""
    echo "Options:"
    echo "  --list                    List all available tests"
    echo "  --all                     Run all tests"
    echo "  --smoke                   Run smoke tests only"
    echo "  --comprehensive           Run comprehensive tests only"
    echo "  --save-report             Save test report to file"
    echo "  --help                    Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --list"
    echo "  $0 temporal_flow_convergence"
    echo "  $0 --all --save-report"
    echo "  $0 --smoke"
    echo ""
    echo "Available test IDs:"
    echo "  temporal_flow_convergence    Test convergence segment detection"
    echo "  temporal_flow_comprehensive  Comprehensive temporal flow validation"
    echo "  temporal_flow_smoke          Basic temporal flow smoke test"
    echo "  density_comprehensive        Comprehensive density analysis test"
    echo "  density_validation           Density calculation validation"
    echo "  density_smoke                Basic density smoke test"
}

# Check if Python is available
if ! command -v python &> /dev/null; then
    print_status "ERROR" "Python is not installed or not in PATH"
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "app/main.py" ]; then
    print_status "ERROR" "Please run this script from the project root directory"
    exit 1
fi

# Parse arguments
TEST_ID=""
SAVE_REPORT=false
RUN_ALL=false
RUN_SMOKE=false
RUN_COMPREHENSIVE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --list)
            print_status "INFO" "Listing all available tests..."
            python tests/test_runner.py --list-tests
            exit 0
            ;;
        --all)
            RUN_ALL=true
            shift
            ;;
        --smoke)
            RUN_SMOKE=true
            shift
            ;;
        --comprehensive)
            RUN_COMPREHENSIVE=true
            shift
            ;;
        --save-report)
            SAVE_REPORT=true
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        -*)
            print_status "ERROR" "Unknown option: $1"
            show_usage
            exit 1
            ;;
        *)
            if [ -z "$TEST_ID" ]; then
                TEST_ID="$1"
            else
                print_status "ERROR" "Multiple test IDs specified. Please specify only one."
                exit 1
            fi
            shift
            ;;
    esac
done

# Determine what to run
if [ "$RUN_ALL" = true ]; then
    print_status "INFO" "Running all tests..."
    if [ "$SAVE_REPORT" = true ]; then
        python tests/test_runner.py --run-all --save-report
    else
        python tests/test_runner.py --run-all
    fi
elif [ "$RUN_SMOKE" = true ]; then
    print_status "INFO" "Running smoke tests..."
    python tests/test_runner.py --test-id temporal_flow_smoke
    python tests/test_runner.py --test-id density_smoke
elif [ "$RUN_COMPREHENSIVE" = true ]; then
    print_status "INFO" "Running comprehensive tests..."
    python tests/test_runner.py --test-id temporal_flow_comprehensive
    python tests/test_runner.py --test-id density_comprehensive
elif [ -n "$TEST_ID" ]; then
    print_status "INFO" "Running test: $TEST_ID"
    if [ "$SAVE_REPORT" = true ]; then
        python tests/test_runner.py --test-id "$TEST_ID" --save-report
    else
        python tests/test_runner.py --test-id "$TEST_ID"
    fi
else
    print_status "WARNING" "No test specified. Use --help for usage information."
    show_usage
    exit 1
fi

# Check exit status
if [ $? -eq 0 ]; then
    print_status "SUCCESS" "Test execution completed successfully"
else
    print_status "ERROR" "Test execution failed"
    exit 1
fi
