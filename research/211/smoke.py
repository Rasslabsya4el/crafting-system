import sys, time
sys.path.insert(0, ".")
sys.path.insert(0, "../../src")
from r25 import r25, all_states
from model import run

w = r25([(500, 2), (1000, 2), (1500, 1)], raw=True)
S = all_states(w)
print("raw states", len(S))
donors = [s for s in S if s[1]]
t0 = time.perf_counter()
offers = lambda s: [("recomb", d) for d in donors]
sol, proc, acq, secs = run(w, lambda s: [], w.blank())
print("no recomb V(blank) =", sol.values[acq.start(w.blank())], "states", len(sol.values), "time", secs)
sol, proc, acq, secs = run(w, lambda s: [("recomb", d) for d in donors if d[1] in (("A",), ("B",), ("C",), ("A","B"), ("A","C"), ("B","C"))], w.blank())
print("seed donors V(blank) =", sol.values[acq.start(w.blank())], "states", len(sol.values), "time", secs, "err", sol.error_bound)
