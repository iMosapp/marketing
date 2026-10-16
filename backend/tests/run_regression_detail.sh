#!/bin/bash
# Usage: bash tests/run_regression_detail.sh out.log module1.py ...  (one summary line per module + its FAILED/ERROR lines)
cd /app/backend
set -a; . ./.env; . ../frontend/.env; set +a
out=$1; shift
: > "$out"
for m in "$@"; do
  start=$(date +%s)
  res=$(timeout 900 python -m pytest "tests/$m" -q -p no:warnings -p no:cacheprovider --no-header -rfE 2>&1)
  line=$(echo "$res" | grep -E "passed|failed|error|no tests ran" | tail -1)
  echo "$m | $(( $(date +%s) - start ))s | ${line:-TIMEOUT/NO OUTPUT}" >> "$out"
  echo "$res" | grep -E "^(FAILED|ERROR) " | cut -c1-260 | sed 's/^/    /' >> "$out"
done
echo DONE >> "$out"
