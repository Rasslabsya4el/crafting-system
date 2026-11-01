"""The tiny recombinator case against exact brute force over every stationary policy of the product."""
import sys, math
from fractions import Fraction
import os
HERE = os.path.dirname(os.path.abspath(__file__))
for rel in (".", "../../tests", "../../src"):
    sys.path.insert(0, os.path.join(HERE, rel))
from world import Cls, World
from model import run
from lazy import lazy_solve
from ssp_input_oracles import brute_force_inputs, lp_values_inputs, policy_space

def tiny(junk=False):
    classes = [Cls("A", "p", 1, named=True), Cls("B", "p", 3, named=True)]
    if junk:
        classes.append(Cls("J", "p", 2))
    return World(classes, costs={"alt": 1, "recomb": 2}, caps={"p": 2, "s": 0}, goal=lambda s: s[1] == ("A", "B"))

def states_of(world):
    import itertools
    names = sorted(world.classes)
    out = []
    for n in range(world.caps["p"] + 1):
        for combo in itertools.combinations(names, n):
            out.append(world.state(combo))
    return out

def spec_of(acq, start):
    seen, order, table, goals = {start}, [start], {}, set()
    while order:
        x = order.pop()
        if acq.is_goal(x):
            goals.add(x); continue
        rows = []
        for a in acq.actions(x):
            rows.append((a.label, Fraction(a.cost), [(o.state, o.weight) for o in a.outcomes], list(a.extra_inputs)))
            for t in [o.state for o in a.outcomes] + list(a.extra_inputs):
                if t not in seen:
                    seen.add(t); order.append(t)
        table[x] = rows
    return goals, table

if __name__ == "__main__":
    for junk, donors_filter in ((False, None),):
        w = tiny(junk)
        S = states_of(w)
        donors = [s for s in S if s[1] in (("A",), ("B",))]
        start = w.blank()
        sol, proc, acq, secs = run(w, lambda s: [("recomb", d) for d in donors], start)
        spec = spec_of(acq, acq.start(start))
        n = sum(1 for _ in policy_space(spec))
        best = brute_force_inputs(spec)
        x = acq.start(start)
        print("product states", len(spec[1]) + len(spec[0]), "policies", n)
        print("solver", sol.values[x], "brute force", float(best[x]))
        bad = [s for s, v in sol.values.items() if s in best and best[s] is not None and abs(v - float(best[s])) > 1e-9 * max(1, v)]
        print("mismatches", len(bad))
