import sys, time
sys.path.insert(0, "."); sys.path.insert(0, "../../src")
from r18 import *
from model import run
w = r18()
cands = lambda s: [("awk", d) for d in donors_for(w, s)]
start = w.blank((C,))
t0 = time.perf_counter()
U = closure(w, [start, w.blank((S,))], cands)
print("universe", len(U), "closure secs", time.perf_counter() - t0, flush=True)
good = lambda s: [("awk", d) for d in donors_for(w, s) if d[1] == ("AM",)]
t0 = time.perf_counter()
sol, proc, acq, secs = run(w, good, start)
print("seed (AM only) V", sol.values[acq.start(start)], "states", len(sol.values), "secs", secs, "total", time.perf_counter() - t0, flush=True)
