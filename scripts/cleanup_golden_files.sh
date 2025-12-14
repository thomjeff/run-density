#!/bin/bash
# Clean up inconsistent golden files before regeneration
# Issue #502: Remove existing golden files that contain wrong day directories

set -e

GOLDEN_BASE="tests/v2/golden"

echo "🧹 Cleaning up inconsistent golden files..."
echo ""

# Remove all existing golden scenario directories
for scenario in saturday_only sunday_only mixed_day; do
    if [ -d "${GOLDEN_BASE}/${scenario}" ]; then
        echo "Removing ${GOLDEN_BASE}/${scenario}/"
        rm -rf "${GOLDEN_BASE}/${scenario}"
    fi
done

echo ""
echo "✅ Golden files cleaned up"
echo ""
echo "📝 Next steps:"
echo "   1. Run tests for each scenario to get proper run_ids:"
echo "      - Saturday-only: pytest tests/v2/e2e.py::TestV2E2EScenarios::test_saturday_only_scenario -v"
echo "      - Sunday-only: pytest tests/v2/e2e.py::TestV2E2EScenarios::test_sunday_only_scenario -v"
echo "      - Mixed-day: pytest tests/v2/e2e.py::TestV2E2EScenarios::test_mixed_day_scenario -v"
echo ""
echo "   2. Generate golden files for each scenario:"
echo "      python scripts/generate_golden_files.py <saturday_run_id> --scenario saturday_only"
echo "      python scripts/generate_golden_files.py <sunday_run_id> --scenario sunday_only"
echo "      python scripts/generate_golden_files.py <mixed_day_run_id> --scenario mixed_day"

