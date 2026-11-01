"""Equality sweep: raw dense (real colours, full link groups, no reduction) against the dedicated routine on reduced states.

Units = (class/weights/prices/actions/start) x chunk of the target list; runner i of N takes the units with index % N == i-1.
Writes one JSON line per case to $OUT_DIR/cases-<i>.jsonl.
"""
import itertools
import json
import os
import sys
import time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fractions import Fraction as F

import numpy as np
from fin import Cfg, RawModel, Target, runs_of
from red import Red
import dedicated
import dense

WEIGHTS = {"thirds": (F(1, 3),) * 3, "dexint": (F(1, 10), F(9, 20), F(9, 20)), "skew": (F(7, 10), F(2, 10), F(1, 10))}
PRICES = {"eq": {}, "omen30": {"omen": 30}}
ACTIONS = {"all": ("JEW", "JEWO", "FUSE", "CONN", "CHROM", "TRI", "BC", "BL", "BK"), "orbs": ("JEW", "FUSE", "CHROM")}
CHUNKS = 6


def targets(maxn):
    out = []
    vecs = [v for v in itertools.product(range(3), repeat=3) if 1 <= sum(v) <= 3]
    for count in (None, maxn):
        for links in (None, 2, 3, 4):
            if links and links > maxn:
                continue
            for v in vecs:
                if links and sum(v) > links:
                    continue
                out.append((count, links, v))
    return out


def unit(u):
    (classmax, wn, pn, an, n0), chunk = u
    cfg = Cfg(classmax=classmax, colour_w=WEIGHTS[wn], prices=PRICES[pn], actions=ACTIONS[an])
    start = (n0, (0,) * n0, (1,) * n0)
    G = dense.Graph(RawModel(cfg, None), start, expand_goals=True)
    rows = []
    for count, links, req in targets(cfg.maxn)[chunk::CHUNKS]:
        tgt = Target(count=count, links=links, req=req)
        goal = np.array([tgt.goal(n, c, runs_of(g)) for (n, c, g) in G.states])
        r = dense.solve(G, goal)
        rec = {"spec": [classmax, wn, pn, an, n0], "count": count, "links": links, "req": req}
        if r is None:
            rec["dead_end"] = True
        else:
            red = Red(cfg, tgt)
            key = red.key_of_raw(start)
            if red.is_goal(key):
                rec.update(dense=0.0, dedicated=0.0)
            else:
                B = dedicated.build(red, key)
                t = time.time()
                V, it, secs, nres = dedicated.solve_anderson(B)
                rec.update(dense=float(r[0][0]), dedicated=float(V[1]), sweeps=it, secs=round(time.time() - t, 3),
                           states=B.N - 1, raw_states=G.N)
        rows.append(rec)
    return rows


if __name__ == "__main__":
    out = os.environ.get("OUT_DIR", ".")
    idx, cnt = int(os.environ.get("RUNNER_INDEX", 1)), int(os.environ.get("RUNNER_COUNT", 1))
    only = sys.argv[1:] and sys.argv[1] or None  # optional: restrict to starts, e.g. "1"
    specs = [(4, wn, pn, an, n0) for wn in WEIGHTS for pn in PRICES for an in ACTIONS for n0 in (1, 4)]
    units = [(s, c) for s in specs for c in range(CHUNKS)]
    mine = [u for i, u in enumerate(units) if i % cnt == idx - 1]
    print("runner", idx, "of", cnt, "units", len(mine), flush=True)
    worst = 0.0
    n = 0
    with open(os.path.join(out, f"cases-{idx}.jsonl"), "w") as f, Pool(int(os.environ.get("PROCS", 4))) as pool:
        for rows in pool.imap_unordered(unit, mine):
            for rec in rows:
                f.write(json.dumps(rec) + "\n")
                if "dense" in rec:
                    n += 1
                    d = abs(rec["dense"] - rec["dedicated"]) / max(1.0, abs(rec["dense"]))
                    worst = max(worst, d)
                    if d > 1e-8:
                        print("MISMATCH", rec, flush=True)
            f.flush()
            print("unit done; cases so far", n, "worst rel diff", worst, flush=True)
    print("DONE cases", n, "worst rel diff", worst)
