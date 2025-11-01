#!/usr/bin/env bash
set -euo pipefail

# Where to write local outputs
export OUTPUT_DIR="${OUTPUT_DIR:-$PWD/reports}"

# Enable bins and set sane defaults
export ENABLE_BIN_DATASET="${ENABLE_BIN_DATASET:-true}"
export BIN_MAX_FEATURES="${BIN_MAX_FEATURES:-10000}"
export DEFAULT_BIN_TIME_WINDOW_SECONDS="${DEFAULT_BIN_TIME_WINDOW_SECONDS:-60}"
export MAX_BIN_GENERATION_TIME_SECONDS="${MAX_BIN_GENERATION_TIME_SECONDS:-120}"

mkdir -p "$OUTPUT_DIR"

echo "==> OUTPUT_DIR=$OUTPUT_DIR"
echo "==> ENABLE_BIN_DATASET=$ENABLE_BIN_DATASET"

# TODO: Cursor MUST update the entrypoint below to the exact command
# that runs your density analysis locally.
# Examples:
#   python -m app.run_scenario --scenario scenarios/full.json
#   python app/density_report.py --manifest ./manifests/sample.json
echo "!! Replace the next line with your real entrypoint !!"
python -c 'print("ENTRYPOINT NOT SET — edit scripts/run_local_bins.sh")' && exit 2

# If the entrypoint above succeeds, run the verifier
# python verify_bins.py --reports-dir "$OUTPUT_DIR" --strict
