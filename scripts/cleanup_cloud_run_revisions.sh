#!/bin/bash
# Cloud Run Revision Cleanup Script
# Keeps the last 5 revisions and deletes all older ones
# Created: 2025-10-22

set -e  # Exit on error

SERVICE_NAME="run-density"
REGION="us-central1"
KEEP_COUNT=5

echo "🧹 Cloud Run Revision Cleanup Script"
echo "===================================="
echo "Service: $SERVICE_NAME"
echo "Region: $REGION"
echo "Keeping: Last $KEEP_COUNT revisions"
echo ""

# Get total count
TOTAL=$(gcloud run revisions list \
  --service=$SERVICE_NAME \
  --region=$REGION \
  --format="value(name)" | wc -l)

TO_DELETE=$((TOTAL - KEEP_COUNT))

echo "📊 Current State:"
echo "  Total revisions: $TOTAL"
echo "  Revisions to keep: $KEEP_COUNT"
echo "  Revisions to delete: $TO_DELETE"
echo ""

if [ $TO_DELETE -le 0 ]; then
  echo "✅ No cleanup needed. Already at or below $KEEP_COUNT revisions."
  exit 0
fi

echo "🗑️  Starting deletion of $TO_DELETE old revisions..."
echo ""

# Get revisions to delete (all except last 5)
REVISIONS_TO_DELETE=$(gcloud run revisions list \
  --service=$SERVICE_NAME \
  --region=$REGION \
  --format="value(name)" \
  --sort-by="~metadata.creationTimestamp" \
  | tail -n +$(($KEEP_COUNT + 1)))

# Delete revisions one by one with progress
COUNT=0
TOTAL_TO_DELETE=$TO_DELETE

echo "$REVISIONS_TO_DELETE" | while read -r revision; do
  if [ -n "$revision" ]; then
    COUNT=$((COUNT + 1))
    echo "[$COUNT/$TOTAL_TO_DELETE] Deleting $revision..."
    gcloud run revisions delete "$revision" --region=$REGION --quiet 2>&1 | grep -v "Deleted" || true
  fi
done

echo ""
echo "✅ Cleanup complete!"
echo ""

# Show final state
FINAL_COUNT=$(gcloud run revisions list \
  --service=$SERVICE_NAME \
  --region=$REGION \
  --format="value(name)" | wc -l)

echo "📊 Final State:"
echo "  Remaining revisions: $FINAL_COUNT"
echo ""

# Show the revisions we kept
echo "📋 Kept Revisions:"
gcloud run revisions list \
  --service=$SERVICE_NAME \
  --region=$REGION \
  --limit=$KEEP_COUNT \
  --format="table(name,status.conditions[0].status,metadata.creationTimestamp)"

echo ""
echo "🎉 Done!"























