import sys, time
sys.path.insert(0, "."); sys.path.insert(0, "../../src")
from r25 import r25, all_states
from model import run
w = r25([(500, 2), (1000, 1)], raw=True)
S = all_states(w); donors = [s for s in S if s[1]]
sol, proc, acq, secs = run(w, lambda s: [("recomb", d) for d in donors], w.blank())
print("unrestricted", secs, len(sol.values), sol.values[acq.start(w.blank())], sol.error_bound, flush=True)
