#!/bin/bash
# Runs each test module in its own pytest process (several modules own their own asyncio loop) and summarises.
cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a
export TEST_ADMIN_PASS=${TEST_ADMIN_PASS:-$(python -c "from tests import qa_creds; print(qa_creds.password_for('forest@imosapp.com'))")}
OUT=${OUT:-/tmp/regress}
mkdir -p "$OUT"
: > "$OUT/summary.txt"
for f in "$@"; do
  name=$(basename "$f" .py)
  timeout 900 python -m pytest "$f" -q --no-header -p no:cacheprovider -W ignore > "$OUT/$name.log" 2>&1
  line=$(grep -E "^[0-9]+ (passed|failed)|passed|failed|error" "$OUT/$name.log" | tail -1)
  echo "$name: ${line:-NO RESULT (exit $?)}" >> "$OUT/summary.txt"
done
echo DONE >> "$OUT/summary.txt"
