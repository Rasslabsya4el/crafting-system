#!/bin/bash
# t1360: the big certificate LPs with HiGHS interior point (simplex did not end in 90-100 min), 4 h cap each, one process each.
cd "/root/projects/crafting system/.claude/scratch/t1360"; export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 METHOD=highs-ipm REWEIGHT=0
run() { timeout 4h systemd-run --scope -q -p MemoryMax=12G -p MemorySwapMax=0 lpenv/bin/python cert.py "$@"; }
( run e-R04.npz 0.01 floor S-R04-floor.npy > i-R04-floor.log 2>&1 ) &
( FREE=ruin run e-R04.npz 0.01 floor > i-R04-ruin.log 2>&1 ) &
( run e-R04q.npz 0.01 floor > i-R04q-floor.log 2>&1 ) &
( run e-R13.npz 0.01 floor S-R13-floor.npy > i-R13-floor.log 2>&1 ) &
wait; touch ipm.done
