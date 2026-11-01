"""One measured case per call; prints one JSON line.  `python exp.py CASE`.  Cases are named <world>:<config>:<what>."""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "../../src"))
from r25 import r25, all_states
from r18 import r18, donors_for, closure, C, S
from model import run, Proc
from lazy import lazy_solve
from components import report
from crafting_system.solver import Acquisition

R25 = {"n6": [(500, 2), (1000, 1)], "n8": [(500, 2), (1000, 2), (1500, 1)], "n12": [(500, 3), (1000, 3), (1500, 3)]}
R18 = {"c1": dict(junk_per_class=1, plain=1), "c2": dict(junk_per_class=1, plain=2), "c3": dict(junk_per_class=2, plain=2),
       "c4": dict(junk_per_class=2, plain=3, weight_classes=2)}
ISO = {("A",), ("B",), ("C",), ("A", "B"), ("A", "C"), ("B", "C")}


def setup(world_name, config):
    if world_name == "r25":
        raw = config.endswith("_raw") or True
    return None


def r25_case(config, mode, what):
    w = r25(R25[config], raw=(mode == "raw"))
    S_ = all_states(w); donors = [s for s in S_ if s[1]]
    cands = lambda s: [("recomb", d) for d in donors]
    start = w.blank()
    out = dict(case=f"r25:{config}:{mode}:{what}", base_states=len(S_), candidate_donors=len(donors))
    t0 = time.perf_counter()
    if what.startswith("lazy"):
        bound = "support" if what == "lazy_support" else "expected"
        per_want = what.startswith("lazy_pw")
        refine = int(what.split("_r")[1].split("_")[0]) if "_r" in what else 0
        seed = (lambda s: []) if what.endswith("empty") else (lambda s: [("recomb", d) for d in donors if d[1] in ISO])
        sol, proc, acq, offers, rounds = lazy_solve(w, start, S_, cands, seed, bound=bound, per_want=per_want, refine=refine, envelope=("_env" in what), log=lambda *_: None)
        out.update(rounds=len(rounds), wants=rounds[-1]["wants"], product_states=len(sol.values),
                   offers=rounds[-1]["offers"], offers_possible=len(S_) * len(donors),
                   violations_per_round=[r["violations"] for r in rounds], V=sol.values[acq.start(start)], error_bound=sol.error_bound,
                   wants_used_by_policy=len({a.label[1] for x, a in sol.policy.items() if isinstance(a.label, tuple) and a.label[0] == "recomb"}))
        out["structure"] = report(acq, acq.start(start))
    elif what == "unres":
        sol, proc, acq, secs = run(w, lambda s: [("recomb", d) for d in donors], start)
        out.update(product_states=len(sol.values), V=sol.values[acq.start(start)], error_bound=sol.error_bound, solve_seconds=secs)
    elif what == "sizes":
        import itertools
        trans = 0
        pairs = 0
        for i, r in enumerate(S_):
            for d in donors:
                dist = w.k_recomb(r, d)
                trans += len(dist)
                pairs += 1
        wants = len(donors)
        out.update(wants=wants, product_states_upper=(wants + 1) * len(S_), recomb_actions=(wants + 1) * pairs, recomb_transitions=(wants + 1) * trans,
                   input_edges=(wants + 1) * pairs)
    elif what == "struct_unres":
        proc, acq = __import__("model").build(w, lambda s: [("recomb", d) for d in donors])
        out["structure"] = report(acq, acq.start(start))
    out["seconds"] = time.perf_counter() - t0
    out["kernels"] = dict(w.stats)
    return out


def r18_case(config, what):
    w = r18(**R18[config])
    cands = lambda s: [("awk", d) for d in donors_for(w, s)]
    start = w.blank((C,))
    out = dict(case=f"r18:{config}:{what}")
    t0 = time.perf_counter()
    U = closure(w, [start, w.blank((S,))], cands)
    out.update(base_states=len(U), s_ring=sum(1 for s in U if s[0] == (S,)), c_ring=sum(1 for s in U if s[0] == (C,)),
               both=sum(1 for s in U if len(s[0]) == 2), projections=len({d for s in U for _, d in cands(s)}),
               candidate_actions=sum(len(cands(s)) for s in U))
    universe = sorted(U)
    seed_am = lambda s: [("awk", d) for d in donors_for(w, s) if d[1] == ("AM",)]
    if what.startswith("lazy"):
        sol, proc, acq, offers, rounds = lazy_solve(w, start, universe, cands, seed_am, per_want=what.startswith("lazy_pw"), log=lambda *_: None)
        out.update(rounds=len(rounds), wants=rounds[-1]["wants"], product_states=len(sol.values), offers=rounds[-1]["offers"],
                   violations_per_round=[r["violations"] for r in rounds], V=sol.values[acq.start(start)], error_bound=sol.error_bound)
        out["structure"] = report(acq, acq.start(start))
    elif what == "unres":
        sol, proc, acq, secs = run(w, cands, start)
        out.update(product_states=len(sol.values), V=sol.values[acq.start(start)], error_bound=sol.error_bound, solve_seconds=secs)
        out["structure"] = report(acq, acq.start(start))
    elif what == "unres_full":
        donors_full = [s for s in U if s[0] == (S,) and any(w.classes[t].infl for t in s[1])]
        donors_full_c = [s for s in U if s[0] == (C,) and any(w.classes[t].infl for t in s[1])]
        offers = lambda s: [("awkf", d) for d in (donors_full if s[0] == (C,) else donors_full_c if s[0] == (S,) else [])]
        sol, proc, acq, secs = run(w, offers, start)
        out.update(full_donor_states=len(donors_full) + len(donors_full_c), product_states=len(sol.values),
                   V=sol.values[acq.start(start)], error_bound=sol.error_bound, solve_seconds=secs)
        out["structure"] = report(acq, acq.start(start))
    out["seconds"] = time.perf_counter() - t0
    return out


def run_case(name):
    kind, config, *rest = name.split(":")
    if kind == "r25":
        return r25_case(config, rest[0], rest[1])
    return r18_case(config, rest[0])


if __name__ == "__main__":
    for name in sys.argv[1:]:
        print(json.dumps(run_case(name), default=str), flush=True)
