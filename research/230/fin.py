"""S4 throwaway: the socket finish as a stochastic shortest path, three encodings.

Colours: 0 white, 1 red, 2 green, 3 blue.  A raw state is (n, cols, groups) with `cols` a tuple of n real colours
and `groups` the link-group sizes in socket order.  A reduced key is (n, cols_reduced, qual): unnamed colours merged
with white, and `qual` the (start, size) of the link groups that are at least `links` long (smaller groups can never
grow, so the target never reads them again).
"""

from fractions import Fraction
from itertools import product
from math import lcm

NAMES = "WRGB"

# --- inputs of ADR-0047 -------------------------------------------------------------------------------------------
FUSE_W = {1: 17818, 2: 34818, 3: 26766, 4: 19672, 5: 826, 6: 100}  # 20% quality table, x 1e5
JEW_W6 = {1: 50, 2: 120, 3: 100, 4: 30, 5: 5, 6: 1}
JEW_W4 = {1: 100, 2: 90, 3: 80, 4: 30}
BENCH_COUNT_COST = {2: 1, 3: 3, 4: 10, 5: 70, 6: 350}  # Jeweller's Orbs
BENCH_LINK_COST = {2: 1, 3: 3, 4: 5, 5: 150, 6: 1500}  # Orbs of Fusing
BENCH_COLOUR_COST = {2: 5, 3: 20, 4: 75}  # Chromatic Orbs


class Cfg:
    """The item and the prices.  Defaults: dex-int helmet-like weights, item level 84, 20% quality, equal prices of 1."""

    def __init__(self, classmax=6, ilvl=84, quality=20, colour_w=(Fraction(1, 10), Fraction(9, 20), Fraction(9, 20)),
                 prices=None, actions=None, forced_w=None, fuse_ok=True):
        self.classmax = classmax
        self.gate = 6 if ilvl >= 50 else 5 if ilvl >= 35 else 4 if ilvl >= 25 else 3
        self.maxn = min(classmax, self.gate)
        self.p = Fraction(375, 100000) * max(ilvl - 14, 1) * (1 + Fraction(min(quality, 30), 100))
        self.colour_w = colour_w  # weights of R, G, B for a coloured socket
        self.forced_w = forced_w or colour_w
        self.prices = {"orb": 1, "omen": 1, **(prices or {})}
        self.actions = actions or ("JEW", "JEWO", "FUSE", "CONN", "CHROM", "TRI", "BC", "BL", "BK")
        self.jew_w = JEW_W4 if classmax == 4 else JEW_W6


class Target:
    def __init__(self, count=None, links=None, req=(0, 0, 0)):
        self.count, self.links, self.req = count, links, tuple(req)
        self.named = frozenset(i + 1 for i, r in enumerate(req) if r)

    def reduce_colour(self, c):
        return c if c in self.named else 0

    def goal(self, n, cols, groups):
        """groups: contiguous link groups (start, size) covering the item."""
        if self.count and n < self.count:
            return False
        if self.links is None:
            runs = [(0, n)]
        else:
            runs = [(s, z) for s, z in groups if z >= self.links]
        for s, z in runs:
            seg = cols[s:s + z]
            if all(seg.count(i + 1) >= r for i, r in enumerate(self.req)):
                return True
        return False


def runs_of(groups):
    out, s = [], 0
    for z in groups:
        out.append((s, z))
        s += z
    return out


# --- kernels ------------------------------------------------------------------------------------------------------
_cache = {}


def chrom_dist(cfg, n, mode=None, k=None):
    """Distribution of the colours a Chromatic Orb rolls on n sockets (real colours), as {tuple: Fraction}.

    mode None = plain; 'tri' = conditioned on >= 1 red, green, blue; ('min', k) = conditioned on >= k non-white.
    """
    key = ("chrom", id(cfg), n, mode)
    if key in _cache:
        return _cache[key]
    p, w, fw = cfg.p, cfg.colour_w, cfg.forced_w
    dist = {}
    for c in product(range(4), repeat=n):
        pr = Fraction(1)
        for x in c:
            pr *= (1 - p) if x == 0 else p * w[x - 1]
        if pr:
            dist[c] = pr
    allw = (1 - p) ** n
    for x in (1, 2, 3):  # every socket rolled white: the first socket is made coloured
        c = (x,) + (0,) * (n - 1)
        dist[c] = dist.get(c, Fraction(0)) + allw * fw[x - 1]
    del dist[(0,) * n]
    if mode == "tri":
        dist = {c: v for c, v in dist.items() if {1, 2, 3} <= set(c)}
    elif isinstance(mode, tuple):
        dist = {c: v for c, v in dist.items() if sum(1 for x in c if x) >= mode[1]}
    tot = sum(dist.values())
    dist = {c: v / tot for c, v in dist.items()}
    _cache[key] = dist
    return dist


def fl(key, d):
    k = ("fl", key)
    if k not in _cache:
        _cache[k] = {a: float(b) for a, b in d.items()}
    return _cache[k]


def fuse_dist(n):
    """{groups tuple: Fraction} of one Orb of Fusing on n sockets (sequential sizes, table cut to what remains)."""
    key = ("fuse", n)
    if key in _cache:
        return _cache[key]
    out = {}

    def go(rem, acc, pr):
        if rem == 0:
            out[acc] = pr
            return
        tot = sum(FUSE_W[j] for j in range(1, rem + 1))
        for z in range(1, rem + 1):
            go(rem - z, acc + (z,), pr * Fraction(FUSE_W[z], tot))

    go(n, (), Fraction(1))
    _cache[key] = out
    return out


def jew_dist(cfg, n):
    """{new count: Fraction}: weights of the class table, current count excluded, capped by class and item level."""
    cap = cfg.maxn
    w = {m: v for m, v in cfg.jew_w.items() if m <= cap and m != n}
    tot = sum(w.values())
    return {m: Fraction(v, tot) for m, v in w.items()}


# --- the raw model: full real colours, full link groups (the dense reference) ----------------------------------------
class RawModel:
    """Explicit model over raw states.  `actions(state)` -> list of (label, cost, {state: Fraction})."""

    def __init__(self, cfg, tgt):
        self.cfg, self.tgt = cfg, tgt

    def is_goal(self, s):
        n, cols, groups = s
        return self.tgt.goal(n, cols, runs_of(groups))

    @staticmethod
    def resize(s, m):
        n, cols, groups = s
        if m > n:
            return m, cols + (0,) * (m - n), groups + (1,) * (m - n)
        g, left = [], m
        for z in groups:
            if left <= 0:
                break
            g.append(min(z, left))
            left -= z
        return m, cols[:m], tuple(g)

    def actions(self, s):
        cfg = self.cfg
        n, cols, groups = s
        pr = cfg.prices
        acts = []
        A = cfg.actions
        if "JEW" in A and n < cfg.maxn:
            acts.append(("JEW", pr["orb"], {self.resize(s, m): v for m, v in fl(("jew", id(cfg), n), jew_dist(cfg, n)).items()}))
        if "JEWO" in A and n < cfg.maxn:
            acts.append(("JEWO", pr["orb"] + pr["omen"], {self.resize(s, cfg.maxn): 1.0}))
        all_linked = len(groups) == 1
        if "FUSE" in A and n >= 2 and not all_linked:
            acts.append(("FUSE", pr["orb"], {(n, cols, g): v for g, v in fl(("fuse", n), fuse_dist(n)).items()}))
        if "CONN" in A and n >= 2 and not all_linked:
            acts.append(("CONN", pr["orb"] + pr["omen"], {(n, cols, (n,)): 1.0}))
        for lab, mode, extra, excl in (("CHROM", None, 0, True), ("TRI", "tri", pr["omen"], True)):
            if lab in A and (lab != "TRI" or n >= 3):
                d = fl(("c", id(cfg), n, mode), chrom_dist(cfg, n, mode))
                pc = d.get(cols, 0.0) if excl else 0.0
                tot = 1.0 - pc
                acts.append((lab, pr["orb"] + extra, {(n, c, groups): v / tot for c, v in d.items() if not (excl and c == cols)}))
        if "BC" in A:
            for m, cost in BENCH_COUNT_COST.items():
                if m <= cfg.classmax and m != n:
                    acts.append((("BC", m), cost * pr["orb"], {self.resize(s, m): 1.0}))
        if "BL" in A:
            for m, cost in BENCH_LINK_COST.items():
                if m <= n:
                    g = (m,) + (1,) * (n - m)
                    if g != groups:
                        acts.append((("BL", m), cost * pr["orb"], {(n, cols, g): 1.0}))
        if "BK" in A:
            for k, cost in BENCH_COLOUR_COST.items():
                if k <= n:
                    d = fl(("c", id(cfg), n, ("min", k)), chrom_dist(cfg, n, ("min", k)))
                    acts.append((("BK", k), cost * pr["orb"], {(n, c, groups): v for c, v in d.items()}))
        return acts
