import sys, random, time
sys.path.insert(0, "."); sys.path.insert(0, "../../src")
from r25 import r25, all_states
from lazy import lazy_solve
ISO = {("A",), ("B",), ("C",), ("A", "B"), ("A", "C"), ("B", "C")}
def one(seed, raw):
    rng = random.Random(seed)
    tw = rng.choice([25, 100, 250])
    junk = [(rng.choice([250, 500, 1000, 1500]), 2), (rng.choice([250, 500, 1000, 1500]), rng.choice([1, 2]))]
    junk = [(w, n) for w, n in junk]
    if junk[0][0] == junk[1][0]:
        junk[1] = (junk[1][0] + 1, junk[1][1])
    costs = {"alt": 1, "exalt": rng.choice([20, 50, 200]), "annul": rng.choice([5, 20, 60]), "recomb": rng.choice([10, 50, 140, 400])}
    w = r25(junk, raw=raw, target_weight=tw, costs=costs)
    S = all_states(w); donors = [s for s in S if s[1]]
    sol, proc, acq, offers, rounds = lazy_solve(w, w.blank(), S, lambda s: [("recomb", d) for d in donors],
                                                 lambda s: [("recomb", d) for d in donors if d[1] in ISO], log=lambda *_: None)
    used = set()
    for s, a in sol.policy.items():
        if isinstance(a.label, tuple) and a.label[0] == "recomb" and s[1] == "MAIN":
            used.add(a.label[1][1])
    junky = [d for d in used if any(t.startswith("J") for t in d)]
    return sol.values[acq.start(w.blank())], junk, tw, costs, junky, len(rounds)
for seed in range(int(sys.argv[1]), int(sys.argv[2])):
    t = time.perf_counter()
    vr, junk, tw, costs, jr, rr = one(seed, True)
    vc, _, _, _, jc, rc = one(seed, False)
    print(seed, "tw", tw, junk, costs, "raw", round(vr, 4), "class", round(vc, 4), "rel", (vc - vr) / vr, "junk donors raw/class", len(jr), len(jc), "rounds", rr, rc, "secs", round(time.perf_counter() - t, 1), flush=True)
