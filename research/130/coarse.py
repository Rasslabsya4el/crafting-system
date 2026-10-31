"""Variants on a coarse state (ticket #130 prototype): pools of junk kinds, per-member kernels by their extremes, two models.

A block is (rarity, slots) whose pooled slots have kind "=<side>:<i>". Its members put the n pooled slots on the families of the
pool (a kind of N families can be held up to N times, a family once). For an adding action the kernel of a member depends on the
pool only through H, the weight of the families held, and every outcome probability is linear over linear in H, so the largest
and the smallest value of a backup over all members are reached at the members that hold the lightest or the heaviest families
(`variants` below); `check_extremes` verifies that on random blocks by enumerating every member.
"""
from light import *
import itertools, math
import numpy as np

PRICE = dict(transmute=0.1, alter=0.2, augment=0.2, regal=1.0, annul=20.0, exalt=15.0, scour=1.0)
if os.environ.get("PRICES") == "cheap":  # Exalted and Annulment cheap: the route leans on them
    PRICE = dict(transmute=0.1, alter=0.2, augment=0.2, regal=0.5, annul=2.0, exalt=2.0, scour=0.5)


class Coarse:
    def __init__(self, L, groups):
        """`groups`: list of lists of kind names, all of one side. [] is the exact model."""
        self.L = L
        self.groups = [tuple(g) for g in groups]
        self.pool_of = {}
        self.pools = []  # (kind name, side, kinds sorted by weight)
        for i, g in enumerate(self.groups):
            sides = {L.info[k]["side"] for k in g}
            assert len(sides) == 1, g
            side = sides.pop()
            name = f"={side[0]}{i}"
            for k in g:
                assert all(sum(c) == 0 for c, _ in L.info[k]["classes"]), "only non-goal kinds are pooled"
                assert k not in self.pool_of
                self.pool_of[k] = name
            ordered = sorted(g, key=lambda k: L.info[k]["W"])
            self.pools.append((name, side, tuple(ordered)))
        self.pool_info = {name: (side, kinds) for name, side, kinds in self.pools}
        self._cache = {}

    # ---- the map ---------------------------------------------------------------------------------
    def coarsen(self, state):
        r, slots = state
        return (r, tuple(sorted((s, self.pool_of.get(k, k), c) for s, k, c in slots)))

    def _fill(self, name, n, heavy):
        """The counts of the kinds of a pool when n slots sit on the lightest (or heaviest) families."""
        side, kinds = self.pool_info[name]
        order = kinds[::-1] if heavy else kinds
        left, counts = n, {}
        for k in order:
            take = min(self.L.info[k]["N"], left)
            if take:
                counts[k] = take
                left -= take
        if left:
            raise ValueError(f"block holds {n} slots of {name}, the pool has fewer families")
        return counts

    def members_extremes(self, block):
        """The representative exact states: every combination of the lightest/heaviest fill of each active pool."""
        r, slots = block
        counts = Counter(k for _, k, _ in slots)
        active = [name for name in self.pool_info if counts.get(name)]
        rest = tuple(s for s in slots if s[1] not in self.pool_info)
        fills = []
        for name in active:
            lo, hi = self._fill(name, counts[name], False), self._fill(name, counts[name], True)
            fills.append([lo] if lo == hi else [lo, hi])
        out = []
        for combo in itertools.product(*fills):
            exact = list(rest)
            for name, fill in zip(active, combo):
                side = self.pool_info[name][0]
                for k, m in fill.items():
                    exact += [(side, k, self.L.info[k]["classes"][0][0])] * m
            out.append((r, tuple(sorted(exact))))
        return out

    # ---- kernels ---------------------------------------------------------------------------------
    def push(self, kernel):
        out = defaultdict(float)
        for s, p in kernel.items():
            out[self.coarsen(s)] += p
        return dict(out)

    def variants(self, block, name):
        """(distributions over blocks, one per distinct extreme member that can take the action; True when every member can)."""
        key = (block, name)
        if key in self._cache:
            return self._cache[key]
        dists, legal = [], True
        for member in self.members_extremes(block):
            k = self.L.kernel(member, name)
            if k is None:
                legal = False
                continue
            d = self.push(k)
            if not any(close(d, e) for e in dists):
                dists.append(d)
        if name not in ("regal", "exalt", "augment") and len(dists) > 1:
            raise AssertionError(f"{name} is not block-invariant on {block}")
        self._cache[key] = (dists, legal)
        return dists, legal


def close(a, b, tol=1e-13):
    return a.keys() == b.keys() and all(abs(a[k] - b[k]) <= tol for k in a)


class Game:
    """Arrays of a min-max model: groups (state, action) of rows (variants); optimistic takes every row, pessimistic the max of a group."""

    def _finish(self, n, goal, rows_state, rows_action, rows_cost, edges, groups):
        self.n = n
        self.goal = np.asarray(goal, dtype=bool)
        self.groups_ = groups  # (state, action, first row, number of rows, legal in every member)
        self.row_state = np.array(rows_state, dtype=np.int64)
        self.row_action = np.array(rows_action, dtype=np.int64)
        self.row_cost = np.array(rows_cost, dtype=np.float64)
        self.e_row = np.fromiter((x[0] for x in edges), dtype=np.int64, count=len(edges))
        self.e_dst = np.fromiter((x[1] for x in edges), dtype=np.int64, count=len(edges))
        self.e_p = np.fromiter((x[2] for x in edges), dtype=np.float64, count=len(edges))
        self.nrows = len(rows_state)
        self.nedges = len(edges)
        g = groups
        self.g_state = np.array([x[0] for x in g], dtype=np.int64)
        self.g_first = np.array([x[2] for x in g], dtype=np.int64)
        self.g_n = np.array([x[3] for x in g], dtype=np.int64)
        self.g_legal = np.array([x[4] for x in g], dtype=bool)
        if self.nrows:
            change = np.flatnonzero(np.r_[True, self.row_state[1:] != self.row_state[:-1]])
            self.r_start, self.r_state = change, self.row_state[change]
            gchange = np.flatnonzero(np.r_[True, self.g_state[1:] != self.g_state[:-1]])
            self.gs_start, self.gs_state = gchange, self.g_state[gchange]

    @classmethod
    def from_tables(cls, n, goal, table):
        """`table`: list over states of list over actions of (legal_everywhere, [(cost, {dst: p}), ...] variants)."""
        self = object.__new__(cls)
        rs, ra, rc, edges, groups = [], [], [], [], []
        for s in range(n):
            if goal[s]:
                continue
            for ai, (legal, variants) in enumerate(table[s]):
                first = len(rs)
                for cost, dist in variants:
                    row = len(rs)
                    rs.append(s); ra.append(ai); rc.append(cost)
                    for dst, p in dist.items():
                        edges.append((row, dst, p))
                groups.append((s, ai, first, len(variants), legal))
        self._finish(n, goal, rs, ra, rc, edges, groups)
        return self

class Graph(Game):
    def __init__(self, C, start, names, price=PRICE, limit=None):
        self.C, self.names, self.price = C, names, price
        L = C.L
        b0 = C.coarsen(start)
        index = {b0: 0}
        blocks = [b0]
        rows_state, rows_action, rows_cost, edges, groups = [], [], [], [], []
        q = 0
        while q < len(blocks):
            b = blocks[q]
            sidx = q
            q += 1
            if L.is_goal(b):
                continue
            for ai, nm in enumerate(names):
                dists, legal = C.variants(b, nm)
                if not dists:
                    continue
                first = len(rows_state)
                for d in dists:
                    row = len(rows_state)
                    rows_state.append(sidx)
                    rows_action.append(ai)
                    rows_cost.append(price[nm])
                    for dst, p in d.items():
                        j = index.get(dst)
                        if j is None:
                            j = index[dst] = len(blocks)
                            blocks.append(dst)
                        edges.append((row, j, p))
                groups.append((sidx, ai, first, len(dists), legal))
            if limit and len(blocks) > limit:
                raise RuntimeError("limit")
        self.blocks = blocks
        self.index = index
        self._finish(len(blocks), [L.is_goal(b) for b in blocks], rows_state, rows_action, rows_cost, edges, groups)

    # -- one backup of each model (V: values by block) --
    def rowvals(self, V):
        return self.row_cost + np.bincount(self.e_row, weights=self.e_p * V[self.e_dst], minlength=self.nrows)

    def backup_lower(self, V):
        rv = self.rowvals(V)
        out = np.full(self.n, np.inf)
        out[self.r_state] = np.minimum.reduceat(rv, self.r_start)
        out[self.goal] = 0.0
        return out, rv

    def backup_upper(self, V):
        rv = self.rowvals(V)
        # max over the rows of a group
        gmax = np.maximum.reduceat(rv, self.g_first) if len(self.g_first) else np.array([])
        gmax = np.where(self.g_legal, gmax, np.inf)
        out = np.full(self.n, np.inf)
        out[self.gs_state] = np.minimum.reduceat(gmax, self.gs_start)
        out[self.goal] = 0.0
        return out, gmax

    def solve(self, which, tol=1e-12, max_iter=2_000_000, report=False):
        back = self.backup_lower if which == "lower" else self.backup_upper
        V = np.zeros(self.n)
        it = 0
        t = time.time()
        while True:
            Vn, _ = back(V)
            Vn = np.where(np.isinf(Vn), np.inf, Vn)
            fin = np.isfinite(Vn)
            delta = np.max(np.where(fin, Vn - V, 0.0)) if fin.any() else 0.0
            V = Vn
            it += 1
            if it % 2000 == 0 and report:
                print("  iter", it, "V0", V[0], "delta", delta, round(time.time() - t, 1), flush=True)
            if delta <= tol * max(1.0, V[0] if np.isfinite(V[0]) else 1.0) or it >= max_iter:
                break
        self.iterations = getattr(self, "iterations", {})
        self.iterations[which] = it
        return V

    def solve_acc(self, which, eps_rel=1e-10, plain=150, max_rounds=400, report=False, V0=None):
        """Value iteration from zero with a geometric jump along the slowest mode every `plain` steps.

        Returns (V, eps): eps is the sup norm of T V - V over the non-goal states with a finite value; the certificate
        below turns it into a bracket of the model's value. The jump is only a way to find V quickly: its result is checked.
        """
        back = self.backup_lower if which == "lower" else self.backup_upper
        V = np.zeros(self.n) if V0 is None else V0.copy()
        free = ~self.goal
        t = time.time()
        steps = 0
        for rnd in range(max_rounds):
            for i in range(plain):
                Vn, _ = back(V)
                d_prev = (Vn - V) if i == plain - 2 else None if i != plain - 2 else None
                if i == plain - 2:
                    d1 = np.where(np.isfinite(Vn), Vn - V, 0.0)
                V = Vn
                steps += 1
            Vn, _ = back(V)
            fin = np.isfinite(Vn) & np.isfinite(V) & free
            d2 = np.where(fin, Vn - V, 0.0)
            eps = float(np.max(d2)) if fin.any() else 0.0
            eps = max(eps, float(np.max(-d2)) if fin.any() else 0.0)
            scale = float(np.max(V[fin])) if fin.any() else 1.0
            if report:
                print(f"  round {rnd} steps {steps} V0 {V[0]:.6f} residual {eps:.3e} {time.time() - t:.0f}s", flush=True)
            if eps <= eps_rel * max(1.0, scale) * self.row_cost.min():
                V = Vn
                steps += 1
                break
            den = float(d1 @ d1)
            lam = float(d2 @ d1) / den if den > 0 else 0.0
            lam = min(max(lam, 0.0), 1 - 1e-9)
            V = Vn
            steps += 1
            if lam > 0.3:
                cand = V + d2 * (lam / (1 - lam))
                cand[self.goal] = 0.0
                # accept the jump when the residual does not grow
                Tc, _ = back(cand)
                finc = np.isfinite(Tc) & np.isfinite(cand) & free
                res_c = float(np.max(np.abs(np.where(finc, Tc - cand, 0.0))))
                if res_c < eps * 1.0:
                    V = cand
        self.steps = getattr(self, "steps", {})
        self.steps[which] = steps
        Vn, _ = back(V)
        fin = np.isfinite(Vn) & np.isfinite(V) & free
        eps = float(np.max(np.abs(np.where(fin, Vn - V, 0.0)))) if fin.any() else 0.0
        return V, eps

    def solve_restart(self, which, inner_eps=1e-9, report=False, root=0, max_outer=60):
        """Solve with the start state as a parameter: fix V(root) = x, iterate the other states to rest, and find x with h(x) = x.

        h(x) is one backup of the root from the resting inner values; it is concave, increasing, piecewise linear with slope below 1,
        so Newton steps on x - h(x) end in a few rounds. The answer is only a candidate: its residual (sup norm of T V - V) is
        what the certificate `bracket` uses.
        """
        back = self.backup_lower if which == "lower" else self.backup_upper
        free = ~self.goal
        free_inner = free.copy()
        free_inner[root] = False
        g = float(self.row_cost.min())
        V = np.zeros(self.n)
        steps = 0

        def inner(x, V):
            nonlocal steps
            V = V.copy()
            V[root] = x
            for _ in range(2_000_000):
                Vn, _ = back(V)
                Vn[root] = x
                fin = np.isfinite(Vn) & np.isfinite(V) & free_inner
                d = float(np.max(np.abs(np.where(fin, Vn - V, 0.0)))) if fin.any() else 0.0
                V = Vn
                steps += 1
                if d <= inner_eps * g:
                    break
            Tv, _ = back(V)
            return V, float(Tv[root])

        x = 0.0
        V, hx = inner(x, V)
        for it in range(max_outer):
            if report:
                print(f"  outer {it} x {x:.9g} h {hx:.9g} steps {steps}", flush=True)
            if abs(hx - x) <= 1e-12 * max(1.0, abs(x)):
                break
            x2 = hx if it == 0 else x + (hx - x) / max(1e-12, 1 - slope)
            V2, h2 = inner(x2, V)
            slope = (h2 - hx) / (x2 - x) if x2 != x else 0.0
            slope = min(max(slope, 0.0), 1 - 1e-12)
            x, hx, V = x2, h2, V2
            # one Newton step from (x, hx) with this slope
            if abs(hx - x) <= 1e-12 * max(1.0, abs(x)):
                break
            x2 = x + (hx - x) / (1 - slope)
            V2, h2 = inner(x2, V)
            slope = min(max((h2 - hx) / (x2 - x) if x2 != x else 0.0, 0.0), 1 - 1e-12)
            x, hx, V = x2, h2, V2
        V[root] = x
        self.steps = getattr(self, "steps", {})
        self.steps[which] = steps
        Vn, _ = back(V)
        fin = np.isfinite(Vn) & np.isfinite(V) & free
        eps = float(np.max(np.abs(np.where(fin, Vn - V, 0.0)))) if fin.any() else 0.0
        return V, eps

    # ---- policy iteration with sparse solves (scipy is a scratch-only dependency of this prototype) ----
    def _sparse(self):
        if getattr(self, "_P", None) is None:
            from scipy import sparse
            self._sp = sparse
            self._P = sparse.csr_matrix((self.e_p, (self.e_row, self.e_dst)), shape=(self.nrows, self.n))
        return self._P

    def _evaluate(self, row_of_state, states):
        """Value of the stationary choice `row_of_state` (a row per state in `states`): solve (I - P) V = c on those states."""
        sp = self._sp
        P = self._P[row_of_state][:, states]
        A = (sp.identity(len(states), format="csc") - P).tocsc()
        c = self.row_cost[row_of_state]
        V = np.zeros(self.n)
        V[states] = sp.linalg.spsolve(A, c)
        return V

    def _row_exit(self):
        mass = np.bincount(self.e_row, weights=self.e_p, minlength=self.nrows)
        return mass < 1 - 1e-12  # the row leaves the model (folded leaf values) with positive probability

    def _row_edges(self):
        order = np.argsort(self.e_row, kind="stable")
        e_row, e_dst = self.e_row[order], self.e_dst[order]
        ptr = np.searchsorted(e_row, np.arange(self.nrows + 1))
        return e_dst, ptr

    def _safe_rows(self):
        """For the optimistic model: a row per state whose some successor is closer to the goal (hop distance over all rows)."""
        e_dst, ptr = self._row_edges()
        dist = np.full(self.n, -1)
        dist[self.goal] = 0
        pick = np.full(self.n, -1, dtype=np.int64)
        # backward BFS over rows
        pred = defaultdict(list)  # dst -> rows
        for r in range(self.nrows):
            for d_ in set(e_dst[ptr[r]:ptr[r + 1]].tolist()):
                pred[d_].append(r)
        frontier = list(np.flatnonzero(self.goal))
        level = 0
        exits = self._row_exit()
        first = []
        for r in np.flatnonzero(exits):
            st = int(self.row_state[r])
            if dist[st] < 0 and not self.goal[st]:
                dist[st] = 1
                pick[st] = r
                first.append(st)
        level = 1
        frontier = frontier + first
        while frontier:
            level += 1
            nxt = []
            for d_ in frontier:
                for r in pred[d_]:
                    s = int(self.row_state[r])
                    if dist[s] < 0:
                        dist[s] = level
                        pick[s] = r
                        nxt.append(s)
            frontier = nxt
        return pick

    def _safe_groups(self):
        """For the pessimistic model: a group per state that is proper against any nature (greatest fixed point of
        'every variant stays inside the set and one of its successors is closer')."""
        e_dst, ptr = self._row_edges()
        exits = self._row_exit()
        n = self.n
        inY = np.ones(n, dtype=bool)
        while True:
            dist = np.full(n, -1)
            dist[self.goal] = 0
            pick = np.full(n, -1, dtype=np.int64)
            level = 0
            changed = True
            while changed:
                changed = False
                level += 1
                newly = []
                for gi in range(len(self.g_state)):
                    s = self.g_state[gi]
                    if dist[s] >= 0 or not self.g_legal[gi] or not inY[s]:
                        continue
                    ok = True
                    for r in range(self.g_first[gi], self.g_first[gi] + self.g_n[gi]):
                        dsts = e_dst[ptr[r]:ptr[r + 1]]
                        if not inY[dsts].all() or not ((dist[dsts] >= 0).any() or exits[r]):
                            ok = False
                            break
                    if ok:
                        newly.append((s, gi))
                for s, gi in newly:
                    if dist[s] < 0:
                        dist[s] = level
                        pick[s] = gi
                        changed = True
            newY = dist >= 0
            if (newY == inY).all():
                return pick
            inY = newY & inY

    def _first_hits(self, keys, mask_positions):
        """The first position of each key among `mask_positions` (array of positions), as {key: position}."""
        ks = keys[mask_positions]
        uniq, idx = np.unique(ks, return_index=True)
        return dict(zip(uniq.tolist(), mask_positions[idx].tolist()))

    def solve_pi(self, which, tol=1e-13, max_iter=200, report=False):
        """Policy iteration; "lower": every row is a choice; "upper": the controller picks a group, nature a row of it."""
        self._sparse()
        n = self.n
        has_rows = np.zeros(n, dtype=bool)
        has_rows[self.g_state] = True
        if which == "lower":
            pick = self._safe_rows()
            states = np.flatnonzero(~self.goal & has_rows & (pick >= 0))
            choice = pick.copy()
            for it in range(max_iter):
                V = self._evaluate(choice[states], states)
                rv = self.row_cost + self._P @ V
                m = np.full(n, np.inf)
                m[self.r_state] = np.minimum.reduceat(rv, self.r_start)
                cur = np.full(n, np.inf)
                cur[states] = rv[choice[states]]
                better = states[m[states] < cur[states] * (1 - tol) - 1e-15]
                if report:
                    print(f"  PI lower iter {it}: V0 {V[0]:.9g}, {len(better)} states switch", flush=True)
                if len(better) == 0:
                    self.choice_rows = choice
                    return V
                hits = self._first_hits(self.row_state, np.flatnonzero(rv <= m[self.row_state] * (1 + 1e-15)))
                for st in better:
                    choice[st] = hits[int(st)]
            raise RuntimeError("policy iteration did not settle")
        pick = self._safe_groups()
        gchoice = pick.copy()
        states = np.flatnonzero(~self.goal & has_rows & (gchoice >= 0))
        nu = np.full(n, -1, dtype=np.int64)
        nu[states] = self.g_first[gchoice[states]]
        for it in range(max_iter):
            for inner in range(500):  # nature's best response to the controller's groups
                V = self._evaluate(nu[states], states)
                rv = self.row_cost + self._P @ V
                gmax_rows = np.full(n, -np.inf)
                switched = 0
                for s in states:
                    gi = gchoice[s]
                    if self.g_n[gi] > 1:
                        lo, hi = self.g_first[gi], self.g_first[gi] + self.g_n[gi]
                        j = lo + int(np.argmax(rv[lo:hi]))
                        if rv[j] > rv[nu[s]] * (1 + tol) + 1e-15:
                            nu[s] = j
                            switched += 1
                if not switched:
                    break
            gmax = np.maximum.reduceat(rv, self.g_first)
            gmax = np.where(self.g_legal, gmax, np.inf)
            best = np.full(n, np.inf)
            best[self.gs_state] = np.minimum.reduceat(gmax, self.gs_start)
            cur = np.full(n, np.inf)
            cur[states] = gmax[gchoice[states]]
            better = states[best[states] < cur[states] * (1 - tol) - 1e-15]
            if report:
                print(f"  PI upper iter {it}: V0 {V[0]:.9g}, {len(better)} states switch", flush=True)
            if len(better) == 0:
                self.gchoice = gchoice
                return V
            hits = self._first_hits(self.g_state, np.flatnonzero(gmax <= best[self.g_state] * (1 + 1e-15)))
            for st in better:
                gi = hits[int(st)]
                gchoice[st] = gi
                nu[st] = self.g_first[gi]
        raise RuntimeError("policy iteration did not settle")

    def residual(self, which, V):
        """Sup norm of T V - V over the non-goal states with a finite value (the certificate's epsilon)."""
        back = self.backup_lower if which == "lower" else self.backup_upper
        Vn, _ = back(V)
        fin = np.isfinite(Vn) & np.isfinite(V) & ~self.goal
        return float(np.max(np.abs(np.where(fin, Vn - V, 0.0)))) if fin.any() else 0.0

    def bracket(self, V, eps):
        """(lower multiplier, upper multiplier) of the certificate: V g/(g + eps) <= value <= V g/(g - eps), g the smallest cost."""
        g = float(self.row_cost.min())
        if eps >= g:
            raise RuntimeError("residual too large to certify")
        return g / (g + eps), g / (g - eps)

    def certify_upper(self, V):
        """Scale a converged pessimistic V into a checked supersolution: T(aV) <= aV pointwise. Returns (a, V*a, residual)."""
        Vn, _ = self.backup_upper(V)
        fin = np.isfinite(V) & ~self.goal
        a = 1.0
        for _ in range(60):
            Va = V * a
            Ta, _ = self.backup_upper(Va)
            bad = (Ta[fin] > Va[fin] * (1 + 1e-15)).any()
            if not bad:
                return a, Va, float(np.max((Ta - Va)[fin]) if fin.any() else 0.0)
            a = 1 + (a - 1) * 2 + 1e-13
        raise RuntimeError("no supersolution found")

    def policy(self, V):
        """argmin action per block under the pessimistic model (action index) at the values V."""
        _, gmax = self.backup_upper(V)
        best = np.full(self.n, np.inf)
        act = np.full(self.n, -1, dtype=np.int64)
        for gi in range(len(self.g_state)):
            s = self.g_state[gi]
            if gmax[gi] < best[s]:
                best[s] = gmax[gi]
                act[s] = self.groups_[gi][1]
        return act
