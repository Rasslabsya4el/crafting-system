"""Random tiny recombinator worlds: lazy == unrestricted == HiGHS LP on the unrestricted product; pruning rates."""
import random, sys, os, time, itertools
HERE = os.path.dirname(os.path.abspath(__file__))
for rel in (".", "../../tests", "../../src"):
    sys.path.insert(0, os.path.join(HERE, rel))
from world import Cls, World
from model import run
from lazy import lazy_solve
from tiny import spec_of, states_of
from ssp_input_oracles import lp_values_inputs

def world_of(seed):
    rng = random.Random(seed)
    classes = [Cls("A", "p", rng.choice([1, 2, 5]), named=True), Cls("B", "p", rng.choice([1, 3, 9]), named=True)]
    if rng.random() < 0.7:
        classes.append(Cls("J", "p", rng.choice([2, 6, 20])))
    costs = {"alt": 1, "recomb": rng.choice([1, 3, 10])}
    if rng.random() < 0.5:
        costs["exalt"] = rng.choice([2, 5])
    if rng.random() < 0.5:
        costs["annul"] = rng.choice([1, 3])
    cap = 2
    return World(classes, costs=costs, caps={"p": cap, "s": 0}, goal=lambda s: s[1] == ("A", "B"))

bad = 0
n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
pruned_total = offered_total = 0
for seed in range(n):
    w = world_of(seed)
    S = states_of(w); donors = [s for s in S if s[1]]
    start = w.blank()
    cands = lambda s: [("recomb", d) for d in donors]
    full = lambda s: cands(s)
    sol, proc, acq, secs = run(w, full, start)
    x = acq.start(start)
    seed_fn = [lambda s: [], lambda s: [("recomb", d) for d in donors if len(d[1]) == 1]][seed % 2]
    lsol, lproc, lacq, offers, rounds = lazy_solve(w, start, S, cands, seed_fn, log=lambda *_: None, bound=["expected", "support"][(seed // 2) % 2])
    lx = lacq.start(start)
    a, b = sol.values[x], lsol.values[lx]
    spec = spec_of(acq, x)
    lp = lp_values_inputs(spec) if all(v < float("inf") for v in sol.values.values()) else None
    c = lp[x] if lp else None
    ok = abs(a - b) <= 1e-8 * max(1, a) and (c is None or abs(float(c) - a) <= 1e-7 * max(1, a))
    off = sum(len(v) for v in offers.values())
    offered_total += len(S) * len(donors); pruned_total += len(S) * len(donors) - off
    if not ok:
        bad += 1
    print(seed, "unres", round(a, 6), "lazy", round(b, 6), "lp", None if c is None else round(float(c), 6), "ok" if ok else "MISMATCH", "rounds", len(rounds), "offers", off, "of", len(S) * len(donors), flush=True)
print("mismatches", bad, "pruned fraction", pruned_total / offered_total)
