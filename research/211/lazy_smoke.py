import sys, time
sys.path.insert(0, "."); sys.path.insert(0, "../../src")
from r25 import r25, all_states
from model import run
from lazy import lazy_solve
w = r25([(500, 2), (1000, 1)], raw=True)
S = all_states(w)
donors = [s for s in S if s[1]]
cands = lambda s: [("recomb", d) for d in donors]
iso = {("A",), ("B",), ("C",), ("A","B"), ("A","C"), ("B","C")}
seed = lambda s: [("recomb", d) for d in donors if d[1] in iso]
t0 = time.perf_counter()
sol, proc, acq, offers, rounds = lazy_solve(w, w.blank(), S, cands, seed)
print("lazy time", time.perf_counter() - t0, sol.values[acq.start(w.blank())])
t0 = time.perf_counter()
sol2, proc2, acq2, secs = run(w, lambda s: [("recomb", d) for d in donors], w.blank())
print("unrestricted", secs, len(sol2.values), sol2.values[acq2.start(w.blank())])
