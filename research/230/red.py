"""Reduced states for the finish: key = (n, cols_reduced, qual), integer-weight tables, wide (Chromatic) actions."""

from fractions import Fraction
from math import lcm

from fin import (BENCH_COLOUR_COST, BENCH_COUNT_COST, BENCH_LINK_COST, chrom_dist, fuse_dist, jew_dist, runs_of)

GOAL = "goal"


def to_ints(dist):
    """{k: Fraction} -> ({k: int}, D) with a common denominator."""
    D = 1
    for v in dist.values():
        D = lcm(D, v.denominator)
    return {k: int(v * D) for k, v in dist.items()}, D


class Red:
    def __init__(self, cfg, tgt, merge=False):
        self.cfg, self.tgt = cfg, tgt
        self.rc = tgt.reduce_colour if merge else (lambda c: c)  # merge: unnamed colours become white
        self.L = tgt.links
        self._tab = {}

    # --- keys --------------------------------------------------------------------------------------------------
    def key_of_raw(self, s):
        n, cols, groups = s
        cols_r = tuple(self.rc(c) for c in cols)
        return (n, cols_r, self._qual(groups))

    def _qual(self, groups):
        if self.L is None:
            return ()
        return tuple((s, z) for s, z in runs_of(groups) if z >= self.L)

    def is_goal(self, key):
        n, cols, qual = key
        if self.tgt.count and n < self.tgt.count:
            return False
        runs = [(0, n)] if self.L is None else qual
        for s, z in runs:
            seg = cols[s:s + z]
            if all(seg.count(i + 1) >= r for i, r in enumerate(self.tgt.req)):
                return True
        return False

    def shell(self, key):
        return (key[0], key[2])

    # --- tables ------------------------------------------------------------------------------------------------
    def chrom_table(self, n, mode):
        """(reduced outcomes [(cols_r, weight)], real weights {real cols: weight}, D) for a Chromatic-type roll."""
        k = ("c", n, mode)
        if k in self._tab:
            return self._tab[k]
        real = chrom_dist(self.cfg, n, mode)
        real_i, D = to_ints(real)
        red = {}
        for c, w in real_i.items():
            r = tuple(self.rc(x) for x in c)
            red[r] = red.get(r, 0) + w
        out = (list(red.items()), real_i, D)
        self._tab[k] = out
        return out

    def fuse_table(self, n):
        k = ("f", n)
        if k in self._tab:
            return self._tab[k]
        d = fuse_dist(n)
        red = {}
        for g, v in d.items():
            q = self._qual(g)
            red[q] = red.get(q, Fraction(0)) + v
        out = to_ints(red)
        self._tab[k] = out
        return out

    # --- actions -----------------------------------------------------------------------------------------------
    def resize(self, key, m):
        n, cols, qual = key
        if m > n:
            return (m, cols + (0,) * (m - n), qual)
        q = tuple((s, min(z, m - s)) for s, z in qual if s < m and min(z, m - s) >= (self.L or 1))
        return (m, cols[:m], q)

    def small(self, key):
        """Actions with few outcomes: list of (label, cost, [(key, int weight)])."""
        cfg, n = self.cfg, key[0]
        cols, qual = key[1], key[2]
        pr = cfg.prices
        A = cfg.actions
        links_matter = self.L is not None
        out = []
        if "JEW" in A and n < cfg.maxn:
            d = jew_dist(cfg, n)
            di, D = to_ints(d)
            out.append(("JEW", pr["orb"], [(self.resize(key, m), w) for m, w in di.items()]))
        if "JEWO" in A and n < cfg.maxn:
            out.append(("JEWO", pr["orb"] + pr["omen"], [(self.resize(key, cfg.maxn), 1)]))
        all_linked = qual == ((0, n),)
        if links_matter:
            if "FUSE" in A and n >= 2 and not all_linked:
                tab, D = self.fuse_table(n)
                out.append(("FUSE", pr["orb"], [((n, cols, q), w) for q, w in tab.items()]))
            if "CONN" in A and n >= 2 and not all_linked:
                q = ((0, n),) if n >= self.L else ()
                out.append(("CONN", pr["orb"] + pr["omen"], [((n, cols, q), 1)]))
        if "BC" in A:
            for m, cost in BENCH_COUNT_COST.items():
                if m <= cfg.classmax and m != n:
                    out.append((("BC", m), cost * pr["orb"], [(self.resize(key, m), 1)]))
        if "BL" in A and links_matter:
            for m, cost in BENCH_LINK_COST.items():
                if m <= n:
                    q = ((0, m),) if m >= self.L else ()
                    if q != qual:
                        out.append((("BL", m), cost * pr["orb"], [((n, cols, q), 1)]))
        return out

    def wide(self, key):
        """Chromatic-type actions: list of (label, cost, mode, excluded real cols or None)."""
        cfg, n = self.cfg, key[0]
        pr = cfg.prices
        A = cfg.actions
        cur = key[1]  # unnamed colours are taken as white for the exclusion (exact when all colours are named)
        out = []
        if "CHROM" in A:
            out.append(("CHROM", pr["orb"], None, cur))
        if "TRI" in A and n >= 3:
            out.append(("TRI", pr["orb"] + pr["omen"], "tri", cur))
        if "BK" in A:
            for k, cost in BENCH_COLOUR_COST.items():
                if k <= n:
                    out.append((("BK", k), cost * pr["orb"], ("min", k), None))
        return out

    def expand_wide(self, key, w):
        label, cost, mode, excl = w
        red, real, D = self.chrom_table(key[0], mode)
        qual = key[2]
        n = key[0]
        ex = real.get(excl, 0) if excl is not None else 0
        outs = []
        for c, wt in red:
            if excl is not None and c == excl:
                wt -= ex
            if wt:
                outs.append(((n, c, qual), wt))
        return (label, cost, outs)

    def actions_int(self, key):
        """Every action with explicit integer-weight outcomes (the dense product)."""
        return self.small(key) + [self.expand_wide(key, w) for w in self.wide(key)]

    # adapter for dense.enumerate_model (Fractions)
    def actions(self, key):
        out = []
        for label, cost, outs in self.actions_int(key):
            tot = sum(w for _, w in outs)
            d = {}
            for k, w in outs:
                d[k] = d.get(k, 0) + Fraction(w, tot)
            out.append((label, cost, d))
        return out
