#!/usr/bin/env bash
# Build and smoke-test the combined Create image (Dockerfile / app.main).
# CI calls this script directly. It is not a Makefile target (#935).
# Default: build the committed tree (git archive), so uncommitted files are excluded.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERIFY_REF="${VERIFY_REF:-HEAD}"
IMAGE_TAG="${IMAGE_TAG:-runflow:dev-$(git rev-parse --short "$VERIFY_REF")}"
VERIFY_PORT="${VERIFY_PORT:-18080}"
SKIP_BUILD="${SKIP_BUILD:-0}"
CONTAINER_NAME="${CONTAINER_NAME:-runflow-verify-$$}"

cleanup() {
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT

if [[ "$SKIP_BUILD" != "1" ]]; then
  echo "Building combined image from git archive ${VERIFY_REF} → ${IMAGE_TAG}"
  git archive "$VERIFY_REF" | docker build -t "$IMAGE_TAG" -
else
  echo "Skipping build; using existing image ${IMAGE_TAG}"
fi

IMAGE_ID="$(docker inspect --format='{{.Id}}' "$IMAGE_TAG")"
echo "Image ID: ${IMAGE_ID}"

echo "Starting ${CONTAINER_NAME} on host port ${VERIFY_PORT}"
docker run -d --name "$CONTAINER_NAME" \
  -p "${VERIFY_PORT}:8080" \
  -e PORT=8080 \
  -e DASHBOARD_PASSWORD= \
  "$IMAGE_TAG" >/dev/null

ok=""
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${VERIFY_PORT}/health" >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 1
done
if [[ -z "$ok" ]]; then
  echo "Server did not become healthy on port ${VERIFY_PORT}"
  docker logs "$CONTAINER_NAME" --tail 80
  exit 1
fi

assert_http() {
  local path="$1"
  local allowed="$2"
  local code
  code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${VERIFY_PORT}${path}")"
  if [[ " ${allowed} " != *" ${code} "* ]]; then
    echo "FAIL ${path} → ${code} (allowed: ${allowed})"
    exit 1
  fi
  echo "OK   ${path} → ${code}"
}

assert_http /health "200"
assert_http /ready "200"
assert_http / "200"
assert_http /dashboard "200 303"
assert_http /overview "200 303"
assert_http /density "200 303"
assert_http /flow "200 303"
assert_http /junctions "200 303"
assert_http /motion "200 303"
assert_http /progression "200 303"
assert_http /locations "200 303"
assert_http /course-mapping "200 303"
assert_http /execute "200 303"
assert_http /execute/participants "200 303"
assert_http /execute/incidents "200 303"

echo
echo "Combined image verified."
echo "  ref:      ${VERIFY_REF} ($(git rev-parse "$VERIFY_REF"))"
echo "  tag:      ${IMAGE_TAG}"
echo "  image_id: ${IMAGE_ID}"
echo "  command:  git archive ${VERIFY_REF} | docker build -t ${IMAGE_TAG} -"
