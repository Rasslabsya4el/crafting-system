"""Raw (every mod named) against class (junk told apart by weight, overlap averaged hypergeometrically)."""
import sys, time
sys.path.insert(0, "."); sys.path.insert(0, "../../src")
from r25 import r25, all_states
from lazy import lazy_solve

ISO = {("A",), ("B",), ("C",), ("A", "B"), ("A", "C"), ("B", "C")}

def value(junk, raw, bound="expected", quiet=True):
    w = r25(junk, raw=raw)
    S = all_states(w); donors = [s for s in S if s[1]]
    sol, proc, acq, offers, rounds = lazy_solve(w, w.blank(), S, lambda s: [("recomb", d) for d in donors],
                                                 lambda s: [("recomb", d) for d in donors if d[1] in ISO], bound=bound, log=lambda *_: None)
    return sol.values[acq.start(w.blank())], len(S), rounds

if __name__ == "__main__":
    junk = eval(sys.argv[1])
    for raw in (True, False):
        t = time.perf_counter()
        v, n, rounds = value(junk, raw)
        print("raw" if raw else "class", "states", n, "V", v, "rounds", len(rounds), "wants", rounds[-1]["wants"], "prod", rounds[-1]["product_states"], "secs", round(time.perf_counter() - t, 1), flush=True)
