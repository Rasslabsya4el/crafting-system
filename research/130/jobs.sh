#!/usr/bin/env bash
# Ticket #130 research jobs; one job per runner (RUNNER_INDEX 1..9). Prototype, not product code.
set -u
P="uv run --frozen --with scipy python research/130"
OUT="${OUT_DIR:-out}"; mkdir -p "$OUT"
TH="100 10 1 0.1 0.01 0.001 0.0001 0.00001 0.000001 0.0000001"
case "$RUNNER_INDEX" in
  1) $P/tailcut.py abs:1000 $TH ;;
  2) $P/tailcut.py abs:2000 $TH ;;
  3) $P/tailcut.py abs:1500 $TH ;;
  4) $P/tailcut.py one $TH ;;
  5) PRICES=cheap $P/exact_cfg.py ;;
  6) PRICES=cheap $P/tailcut.py abs:1000 $TH ;;
  7) GOAL=B $P/tailcut.py abs:1000 $TH ;;
  8) $P/oracle.py ;;
  9) $P/lifted.py abs:1000 abs:500 ;;
esac 2>&1 | tee "$OUT/job$RUNNER_INDEX.log"
