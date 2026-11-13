#!/usr/bin/env bash
# One measurement job of ticket #881 on a GitHub runner (Linux or Windows), started only through the dispatcher:
#   python .github/scripts/heavy_dispatch.py run --no-wait [--os windows-latest] --ref <branch> --runners 4 --command 'bash research/881/run_job.sh $RUNNER_INDEX'
# 1, 2: the hot loop on the pools of R04 / essences/medium: today's Python against flat Python, Numba and Cython (bench_kernels.py).
# 3, 4: the whole plan of R04 / essences/medium, first as it is, then on a copy of the package compiled by Cython as it is, on the same runner.
set -euo pipefail
job="$1"
out="${OUT_DIR:-out}"
uv pip install numba==0.68.1 cython==3.3.1 setuptools
py() { uv run --no-sync python -u "$@"; }
whole() {  # $@: the plan's arguments
  py research/881/profile_plan.py "$@" --mode plain --tag .as-is --out "$out"
  py research/881/build_cython.py source --out "$PWD/compiled-source" --smoke r13
  cp compiled-source/compiled.json "$out/compiled.json"
  CRAFTING_SOURCE="$PWD/compiled-source" py research/881/profile_plan.py "$@" --mode plain --tag .compiled --out "$out"
}
case "$job" in
  1) py research/881/build_cython.py flat; py research/881/bench_kernels.py --route r04 --out "$out" ;;
  2) py research/881/build_cython.py flat; py research/881/bench_kernels.py --case essences/medium --out "$out" ;;
  3) whole --route r04 ;;
  4) whole --case essences/medium ;;
  *) echo "no job $job"; exit 2 ;;
esac
