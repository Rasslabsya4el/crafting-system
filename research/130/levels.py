"""The levels of ticket #130 on the R14-like Hunter Thicket Bow: pools of junk kinds with variants (per-member kernels by their extremes).

usage: levels.py <config> ...   with config one of  exact | one | tau:<x> | size:<k>
"""
import sys, json
from coarse import *

d, ab, L = make(float, True)
START = (NORMAL, ())


def junk_by_side():
    out = {}
    for side in ("prefix", "suffix"):
        ks = [k for k, v in L.info.items() if v["side"] == side and all(sum(c) == 0 for c, _ in v["classes"])]
        out[side] = sorted(ks, key=lambda k: (L.info[k]["W"], k))
    return out


def groups_for(cfg):
    if cfg == "exact":
        return []
    junk = junk_by_side()
    groups = []
    kind, _, arg = cfg.partition(":")
    for side, ks in junk.items():
        if kind == "one":
            groups.append(ks)
        elif kind == "tau":  # consecutive kinds (by per-family weight) whose weights are within 1 + tau of the lightest
            tau = float(arg)
            cur = []
            for k in ks:
                if cur and L.info[k]["W"] > L.info[cur[0]]["W"] * (1 + tau):
                    groups.append(cur)
                    cur = []
                cur.append(k)
            if cur:
                groups.append(cur)
        elif kind == "light":  # every kind up to the weight in one pool per side, the rest exact
            groups.append([k for k in ks if L.info[k]["W"] <= float(arg)])
        elif kind == "abs":  # consecutive kinds whose per-family weights are within `arg` of the lightest
            width = float(arg)
            cur = []
            for k in ks:
                if cur and L.info[k]["W"] - L.info[cur[0]]["W"] > width:
                    groups.append(cur)
                    cur = []
                cur.append(k)
            if cur:
                groups.append(cur)
        elif kind == "size":
            n = int(arg)
            groups += [ks[i:i + n] for i in range(0, len(ks), n)]
        else:
            raise ValueError(cfg)
    return [g for g in groups if len(g) > 1]  # a pool of one kind is the kind itself


def run(cfg, names=NAMES, price=PRICE, verbose=False):
    t0 = time.time()
    groups = groups_for(cfg)
    C = Coarse(L, groups)
    G = Graph(C, START, names, price)
    build = time.time() - t0
    t0 = time.time()
    Vl = G.solve_pi("lower"); el = G.residual("lower", Vl)
    Vu = G.solve_pi("upper"); eu = G.residual("upper", Vu)
    solve = time.time() - t0
    ll, _ = G.bracket(Vl, el)
    _, uu = G.bracket(Vu, eu)
    lower, upper = Vl[0] * ll, Vu[0] * uu
    return dict(cfg=cfg, pools=len(groups), pooled_kinds=sum(len(g) for g in groups), blocks=G.n, rows=G.nrows, edges=G.nedges,
                lower=lower, upper=upper, gap=upper / lower - 1, V_lower=Vl[0], V_upper=Vu[0], eps_lower=el, eps_upper=eu,
                build_s=round(build, 1), solve_s=round(solve, 1)), G, (Vl, Vu)


if __name__ == "__main__":
    for cfg in sys.argv[1:]:
        res, G, _ = run(cfg)
        print(json.dumps(res), flush=True)
