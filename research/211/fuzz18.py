"""Random tiny Awakener worlds: projection wants vs whole-item wants vs lazy; HiGHS LP on the projection product."""
import random, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
for rel in (".", "../../tests", "../../src"):
    sys.path.insert(0, os.path.join(HERE, rel))
from world import Cls, World
from model import run
from lazy import lazy_solve
from r18 import donors_for, closure, C, S
from tiny import spec_of
from ssp_input_oracles import lp_values_inputs

def world_of(seed):
    rng = random.Random(seed)
    w = lambda: rng.choice([50, 100, 300, 900])
    classes = [Cls("ES", "p", w(), infl=C, named=True), Cls("CJp", "p", w(), infl=C), Cls("SJp", "p", w(), infl=S),
               Cls("AM", "s", w(), infl=S, named=True), Cls("CJs", "s", w(), infl=C), Cls("SJs", "s", w(), infl=S)]
    if rng.random() < 0.5:
        classes.append(Cls("P", "p", w()))
    costs = {"chaos": rng.choice([1, 3]), "awk": rng.choice([5, 30, 100]), "buys": {"buy_AM": (((S,), ()), ((S,), ("AM",)), rng.choice([20, 100, 400]))}}
    if rng.random() < 0.5:
        costs["annul"] = rng.choice([1, 4])
    if rng.random() < 0.5:
        costs["exalt"] = rng.choice([2, 8])
    return World(classes, costs=costs, caps={"p": 2, "s": 2}, goal=lambda s: set(s[0]) == {C, S} and "ES" in s[1] and "AM" in s[1])

bad = 0
n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
for seed in range(n):
    w = world_of(seed)
    cands = lambda s: [("awk", d) for d in donors_for(w, s)]
    start = w.blank((C,))
    U = sorted(closure(w, [start, w.blank((S,))], cands))
    sol, proc, acq, secs = run(w, cands, start)
    x = acq.start(start)
    full_c = [s for s in U if s[0] == (C,) and any(w.classes[t].infl for t in s[1])]
    full_s = [s for s in U if s[0] == (S,) and any(w.classes[t].infl for t in s[1])]
    solf, procf, acqf, _ = run(w, lambda s: [("awkf", d) for d in (full_s if s[0] == (C,) else full_c if s[0] == (S,) else [])], start)
    lsol, lproc, lacq, offers, rounds = lazy_solve(w, start, U, cands, [lambda s: [], lambda s: [("awk", d) for d in donors_for(w, s) if d[1] == ("AM",)]][seed % 2], log=lambda *_: None)
    a, b, c = sol.values[x], lsol.values[lacq.start(start)], solf.values[acqf.start(start)]
    lp = None
    if all(v < float("inf") for v in sol.values.values()):
        lp = float(lp_values_inputs(spec_of(acq, x))[x])
    ok = abs(a - b) <= 1e-8 * max(1, abs(a)) and c >= a - 1e-8 * max(1, abs(a)) and (lp is None or abs(lp - a) <= 1e-7 * max(1, abs(a)))
    bad += not ok
    print(seed, "base", len(U), "proj-unres", a, "lazy", b, "full-unres", c, "full-minus-proj", c - a, "lp", lp, "ok" if ok else "MISMATCH", "prod", len(sol.values), len(lsol.values), len(solf.values), "wants", len({k[1] for k in sol.values}), len({k[1] for k in solf.values}), flush=True)
print("mismatches", bad)
