#!/bin/bash
# Run E2E waveform quality tests one by one and collect results
set -o pipefail

export DISPLAY=:99
RESULTS_FILE="/qqvip/proj/BeatFlow/frontend/e2e-results.txt"
cd /qqvip/proj/BeatFlow/frontend

echo "=== E2E Waveform Quality Test Run ===" > "$RESULTS_FILE"
echo "Started: $(date)" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

# Define test patterns to run
tests=(
  "capture and validate 50"
  "ECG and PCG timelines stay aligned"
  "waveform renders without errors at HR=45"
  "waveform renders without errors at HR=72"
  "waveform renders without errors at HR=120"
  "waveform renders without errors at HR=180"
  "AF produces expected beat annotations"
  "PVC produces expected beat annotations"
  "VT produces expected beat annotations"
  "10-second streaming without signal degradation"
  "ECG R-peak timing correlates with PCG"
)

passed=0
failed=0
total=${#tests[@]}

for pattern in "${tests[@]}"; do
  echo "--- Running: $pattern ---" >> "$RESULTS_FILE"
  echo "[$(date +%H:%M:%S)] Running: $pattern"
  
  output=$(npx playwright test e2e/waveform-quality.spec.ts --grep "$pattern" --reporter=line 2>&1)
  exit_code=$?
  
  echo "$output" >> "$RESULTS_FILE"
  
  if [ $exit_code -eq 0 ]; then
    echo "RESULT: PASS" >> "$RESULTS_FILE"
    ((passed++))
    echo "[$(date +%H:%M:%S)] PASS: $pattern"
  else
    echo "RESULT: FAIL (exit code: $exit_code)" >> "$RESULTS_FILE"
    ((failed++))
    echo "[$(date +%H:%M:%S)] FAIL: $pattern"
  fi
  echo "" >> "$RESULTS_FILE"
done

echo "=== SUMMARY ===" >> "$RESULTS_FILE"
echo "Total: $total | Passed: $passed | Failed: $failed" >> "$RESULTS_FILE"
echo "Finished: $(date)" >> "$RESULTS_FILE"
echo ""
echo "=== DONE: $passed/$total passed ==="
