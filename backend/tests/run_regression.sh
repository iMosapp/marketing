#!/bin/bash
# One pytest process per module (each module owns its asyncio loop). Usage: bash tests/run_regression.sh out.log module1.py module2.py ...
cd /app/backend
set -a; . ./.env; . ../frontend/.env; set +a
out=$1; shift
: > "$out"
for m in "$@"; do
  start=$(date +%s)
  res=$(timeout 600 python -m pytest "tests/$m" -q -p no:cacheprovider --no-header 2>&1 | tail -3 | tr '\n' ' ')
  echo "$m | $(( $(date +%s) - start ))s | $res" >> "$out"
done
echo DONE >> "$out"
