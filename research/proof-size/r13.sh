#!/bin/bash
# t1360: every count of the note on the R13 dump, once k-R13.pkl exists.
cd "/root/projects/crafting system/.claude/scratch/t1360"; export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
until [ -s k-R13.pkl ] && grep -q "END" k-R13.log; do sleep 30; done
W="/root/projects/crafting system/.claude/worktrees/t1360"
(cd "$W" && .venv/bin/python "/root/projects/crafting system/.claude/scratch/t1360/export.py" "/root/projects/crafting system/.claude/scratch/t1360/k-R13.pkl" "/root/projects/crafting system/.claude/scratch/t1360/e-R13.npz") > r13-export.log 2>&1
lpenv/bin/python bisim.py e-R13.npz > bisim-R13.log 2>&1
lpenv/bin/python q1.py e-R13.npz > q1-R13.log 2>&1
lpenv/bin/python q2.py e-R13.npz > q2-R13.log 2>&1
lpenv/bin/python anaF.py e-R13.npz > anaF-R13.log 2>&1
lpenv/bin/python quot.py e-R13.npz e-R13q.npz > quot-R13.log 2>&1
( REWEIGHT=1 timeout 60m lpenv/bin/python cert.py e-R13q.npz 0.01 floor > c-R13q-floor.log 2>&1 ) &
( FREE=oracle REWEIGHT=1 timeout 60m lpenv/bin/python cert.py e-R13.npz 0.01 floor > c-R13-free-oracle.log 2>&1 ) &
( FREE=ruin REWEIGHT=1 timeout 60m lpenv/bin/python cert.py e-R13.npz 0.01 floor > c-R13-free-ruin.log 2>&1 ) &
( REWEIGHT=1 timeout 90m lpenv/bin/python cert.py e-R13.npz 0.01 floor S-R13-floor.npy > c-R13-0.01-floor.log 2>&1 ) &
wait
echo done > r13.done
