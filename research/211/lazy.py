"""The lazy offer loop: solve with the donors offered so far, then prove every other donor unneeded or offer it.

Sound for the reason the module docstring of the ADR gives: L = V on built finite states and the determinized distance
elsewhere is a sub-solution of the full operator T when every action passes the test below, and a sub-solution
is at most V*, while V of a feasible (restricted) policy set is at least V*.
"""

import heapq
import math
import time
from collections import defaultdict

from model import Proc, run, run_per_want, awk_proj
from crafting_system.solver import MAIN
from world import scaled


class Determinized:
    """D_w(s): cheapest path (costs of the actions, inputs free, any positive-probability successor) to a state that reaches w."""

    def __init__(self, world, proc, universe_states, candidates):
        self.world, self.proc = world, proc
        # forward edges s -> [(cost, successor)] over single-item actions and every candidate two-input action
        self.rev = defaultdict(list)
        for s in universe_states:
            for label, cost, dist in world.base_actions(s):
                for j in dist:
                    if j != s:
                        self.rev[j].append((cost, s))
            for kind, d in candidates(s):
                dist = world.k_recomb(s, d) if kind == "recomb" else world.k_awakener(s, d)
                cost = world.costs["recomb" if kind == "recomb" else "awk"]
                for j in dist or ():
                    if j != s:
                        self.rev[j].append((cost, s))
        self.universe = universe_states
        self.candidates = candidates
        self._memo = {}

    def refined(self, want, sweeps):
        """`sweeps` Gauss-Seidel sweeps of the Bellman operator started from the determinized distance, with every donor at its
        determinized cost: still a sub-solution (the operator is monotone and the start is below its image), so still a lower bound."""
        key = ("refined", want, sweeps)
        got = self._memo.get(key)
        if got is not None:
            return got
        L = dict(self.dist(want))
        goals = {s for s in self.universe if (self.world.goal(s) if want == "MAIN" else self.proc.reaches(s, want))}
        for _ in range(sweeps):
            for s in self.universe:
                if s in goals:
                    continue
                best = L.get(s, math.inf)
                for label, cost, dist in self.world.base_actions(s):
                    q = cost + sum(float(p) * L.get(j, math.inf) for j, p in dist.items())
                    best = min(best, q)
                for kind, d in self.candidates(s):
                    dd = self.world.k_recomb(s, d) if kind == "recomb" else self.world.k_awakener(s, d)
                    if not dd:
                        continue
                    dw_ = ("awk" if kind == "awk" else "full", d)
                    acq = self.dist(dw_).get(self.world.blank(d[0]), math.inf)
                    q = self.world.costs["recomb" if kind == "recomb" else "awk"] + acq + sum(float(p) * L.get(j, math.inf) for j, p in dd.items())
                    best = min(best, q)
                if best < L.get(s, math.inf):
                    L[s] = best
        self._memo[key] = L
        return L

    def dist(self, want):
        got = self._memo.get(want)
        if got is not None:
            return got
        if want == "MAIN":
            goals = [s for s in self.universe if self.world.goal(s)]
        else:
            goals = [s for s in self.universe if self.proc.reaches(s, want)]
        best = {s: 0.0 for s in goals}
        heap = [(0.0, i, s) for i, s in enumerate(goals)]
        heapq.heapify(heap)
        counter = len(heap)
        while heap:
            d, _, s = heapq.heappop(heap)
            if d > best.get(s, math.inf):
                continue
            for cost, prev in self.rev.get(s, ()):
                nd = d + cost
                if nd < best.get(prev, math.inf):
                    best[prev] = nd
                    counter += 1
                    heapq.heappush(heap, (nd, counter, prev))
        self._memo[want] = best
        return best


def lazy_solve(world, start, universe_states, candidates, seed, *, bound="expected", max_rounds=50, log=print, per_want=False, refine=0, **options):
    """Returns (final solution, proc, acq, offers, rounds). `candidates(s)` lists every (kind, donor) that could be offered at s;
    `seed(s)` the donors offered at the start; `bound` is "expected" (c + acq + sum p L) or "support" (c + acq + min L over the support).
    `per_want`: donors are offered per product state (want, state) instead of per base state, so a donor process need not
    inherit what the main target needs."""
    added = defaultdict(set)  # key: base state (shared) or (want, state) (per_want)
    key_of = (lambda w, s: (w, s)) if per_want else (lambda w, s: s)
    seed_of = (lambda w, s: set(seed(s)) if w is MAIN else set()) if per_want else (lambda w, s: set(seed(s)))
    offered = lambda w, s: added[key_of(w, s)] | seed_of(w, s)
    det = Determinized(world, None, universe_states, candidates)
    rounds = []
    for number in range(1, max_rounds + 1):
        if per_want:
            sol, proc, acq, secs = run_per_want(world, lambda w, s: sorted(offered(w, s)), start, **options)
        else:
            sol, proc, acq, secs = run(world, lambda s: sorted(offered(None, s)), start, **options)
        det.proc = proc
        det._memo.clear()
        values = sol.values
        wants = {w for (_, w, _) in values}
        violations = set()
        checked = 0
        for (tag, w, s), v in values.items():
            if v == 0.0:
                continue
            have = offered(w, s)
            if not math.isfinite(v):  # no incumbent here: nothing can be pruned, offer every candidate
                for kind, d in candidates(s):
                    if (kind, d) not in have:
                        violations.add((w, s, kind, d))
                continue
            wkey = "MAIN" if w is MAIN else w
            dw = det.refined(wkey, refine) if refine else det.dist(wkey)

            def L(j):
                got = values.get((tag, w, j))
                if got is not None and math.isfinite(got):
                    return got
                return dw.get(j, math.inf)

            for kind, d in candidates(s):
                if (kind, d) in have:
                    continue
                checked += 1
                want = ("awk" if kind == "awk" else "full", d)
                acq_value = values.get((tag, want, world.blank(d[0])))
                if acq_value is None or not math.isfinite(acq_value):
                    acq_value = (det.refined(want, refine) if refine else det.dist(want)).get(world.blank(d[0]), math.inf)
                dist = world.k_recomb(s, d) if kind == "recomb" else world.k_awakener(s, d)
                if not dist:
                    continue
                cost = world.costs["recomb" if kind == "recomb" else "awk"]
                if bound == "expected":
                    q = cost + acq_value + sum(float(p) * L(j) for j, p in dist.items())
                else:
                    q = cost + acq_value + min(L(j) for j in dist)
                if q < v * (1 - 1e-9) - 1e-9:
                    violations.add((w, s, kind, d))
        offers_now = sum(len(offered(w, s)) for w, s in {(w, s) for (_, w, s) in values}) if per_want else sum(len(offered(None, s)) for s in universe_states)
        rounds.append(dict(round=number, product_states=len(values), wants=len(wants), offers=offers_now,
                           violations=len(violations), checked=checked, seconds=secs, value=values[acq.start(start)]))
        log(rounds[-1])
        if not violations:
            return sol, proc, acq, (added, seed_of), rounds
        for w, s, kind, d in violations:
            added[key_of(w, s)].add((kind, d))
    raise RuntimeError("no fixed point")
