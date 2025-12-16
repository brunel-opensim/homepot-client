#!/bin/bash
# Workflow Performance Monitoring Script
# Usage: ./scripts/check-workflow-performance.sh [workflow-name] [limit]

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

WORKFLOW_NAME="${1:-CI/CD Pipeline}"
LIMIT="${2:-20}"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}HOMEPOT Workflow Performance Analysis${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "Workflow: ${GREEN}${WORKFLOW_NAME}${NC}"
echo -e "Analyzing last ${LIMIT} runs..."
echo ""

# Get workflow runs with timing data
RUNS=$(gh run list --workflow "${WORKFLOW_NAME}" --limit "${LIMIT}" \
  --json conclusion,startedAt,updatedAt,databaseId,displayTitle,event 2>/dev/null)

if [ -z "$RUNS" ] || [ "$RUNS" = "[]" ]; then
  echo -e "${RED}No workflow runs found for '${WORKFLOW_NAME}'${NC}"
  echo ""
  echo "Available workflows:"
  gh workflow list
  exit 1
fi

# Calculate statistics using jq
echo "$RUNS" | jq -r '
  # Calculate durations
  map({
    id: .databaseId,
    title: .displayTitle[0:60],
    conclusion: .conclusion,
    event: .event,
    duration: ((.updatedAt | fromdateiso8601) - (.startedAt | fromdateiso8601))
  }) |
  
  # Filter out in-progress runs
  map(select(.conclusion != null)) |
  
  # Calculate stats
  . as $runs |
  {
    total: length,
    successful: map(select(.conclusion == "success")) | length,
    failed: map(select(.conclusion == "failure")) | length,
    cancelled: map(select(.conclusion == "cancelled")) | length,
    durations: map(.duration),
    runs: $runs
  } |
  
  # Add calculated fields
  .avg_duration = (.durations | add / length) |
  .min_duration = (.durations | min) |
  .max_duration = (.durations | max) |
  .median_duration = (.durations | sort | .[length/2 | floor]) |
  .success_rate = ((.successful / .total) * 100) |
  
  # Format output
  "Statistics (last \(.total) completed runs):",
  "═══════════════════════════════════════════════════════",
  "",
  "  Duration:",
  "   Average:  \(.avg_duration / 60 | floor)m \(.avg_duration % 60 | floor)s",
  "   Median:   \(.median_duration / 60 | floor)m \(.median_duration % 60 | floor)s",
  "   Min:      \(.min_duration / 60 | floor)m \(.min_duration % 60 | floor)s",
  "   Max:      \(.max_duration / 60 | floor)m \(.max_duration % 60 | floor)s",
  "",
  "Success Rate: \(.success_rate | floor)% (\(.successful) successful)",
  "Failures:     \(.failed)",
  "Cancelled:    \(.cancelled)",
  "",
  "Recent Runs:",
  "─────────────────────────────────────────────────────────",
  (.runs[0:10] | .[] | 
    if .conclusion == "success" then "OK" 
    elif .conclusion == "failure" then "FAIL" 
    elif .conclusion == "cancelled" then "WARNING "
    else "PAUSE " end + 
    " \(.duration / 60 | floor)m \(.duration % 60 | floor)s - \(.title)"
  )
' 

# Check for performance regression
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

AVG_DURATION=$(echo "$RUNS" | jq -r '
  map(select(.conclusion == "success")) |
  map((.updatedAt | fromdateiso8601) - (.startedAt | fromdateiso8601)) |
  add / length
')

AVG_MINUTES=$(echo "$AVG_DURATION / 60" | bc)

if [ "$AVG_MINUTES" -gt 10 ]; then
  echo -e "${RED}PERFORMANCE WARNING${NC}"
  echo -e "  - Average duration: ${AVG_MINUTES}m (threshold: 10m)"
  echo "  - Consider optimizing slow tests or CI configuration"
elif [ "$AVG_MINUTES" -gt 5 ]; then
  echo -e "${YELLOW}  - PERFORMANCE NOTICE${NC}"
  echo -e "  - Average duration: ${AVG_MINUTES}m (target: <5m)"
  echo "  - Room for optimization exists"
else
  echo -e "${GREEN}  - EXCELLENT PERFORMANCE${NC}"
  echo -e "  - Average duration: ${AVG_MINUTES}m"
  echo "  - Workflow is well optimized!"
fi

echo ""

# Show trend
echo -e "${BLUE}Trend Analysis:${NC}"
echo "$RUNS" | jq -r '
  map(select(.conclusion == "success")) |
  reverse |
  .[0:10] |
  to_entries |
  .[] |
  "\(.key + 1). \(.value.displayTitle[0:40]): \((.value.updatedAt | fromdateiso8601) - (.value.startedAt | fromdateiso8601) / 60 | floor)m"
'

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "Tips:"
echo "  - Run this script regularly to track performance trends"
echo "  - Set up alerts if average duration exceeds thresholds"
echo "  - Use 'gh run view <run-id>' for detailed timing per job"
echo ""
