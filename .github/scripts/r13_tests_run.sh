#!/usr/bin/env bash
# The two R13 real test files side by side in two processes, as two slots of a CI job run them (ticket #717): logs and durations into $OUT_DIR.
#   bash .github/scripts/r13_tests_run.sh
set -u
KEEP='not R12 and not R10 and not R05'
uv run --no-sync python -m pytest -p no:cacheprovider -v --durations=25 tests/test_cli_r13_real.py > "$OUT_DIR/cli.log" 2>&1 &
uv run --no-sync python -m pytest -p no:cacheprovider -v --durations=25 -k "$KEEP" tests/test_packed_plan_real.py > "$OUT_DIR/packed.log" 2>&1
wait
tail -n 45 "$OUT_DIR/cli.log"
tail -n 45 "$OUT_DIR/packed.log"
