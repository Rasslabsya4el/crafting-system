"""Ticket #211 prototype: a small crafting world whose items are multisets of mod classes, with exact kernels.

A state is `(influences, tokens)`: influences a sorted tuple of names, tokens a sorted tuple of class names with repeats.
A class is a group of mods that every action treats alike (`size` mods of one side, one `weight`, one influence); a
class of size 1 is a single named mod, so "raw" (every mod told apart) and "class" (junk told apart by weight only) are
the same code with different class tables. Draws are successive, without replacement, weighted by `weight`, and a family
is closed once a mod of it is picked (every mod is its own family, a doubled mod of a recombination is one family).

Actions of the item process (`World.actions`): alt, exalt, annul, chaos, recomb (a donor from `offers`), awakener
(a donor from `offers`), buy. Everything is exact (`Fraction`), then scaled to the integer weights the solver wants.
"""

import itertools
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from math import comb, lcm

from crafting_system.solver import Action, Need, Outcome

State = tuple[tuple[str, ...], tuple[str, ...]]

# The guide's kept-count table of ADR-0033 (percent kept by pooled count; rows 3 and 4 sum to 101 and are renormalised).
COUNT_TABLE = {
    1: {0: 41, 1: 59},
    2: {1: 67, 2: 33},
    3: {1: 39, 2: 52, 3: 10},
    4: {1: 11, 2: 59, 3: 31},
    5: {2: 43, 3: 57},
    6: {2: 28, 3: 72},
}
CHAOS_TOTAL = {4: Fraction(8, 12), 5: Fraction(3, 12), 6: Fraction(1, 12)}


@dataclass(frozen=True)
class Cls:
    name: str
    side: str  # "p" or "s"
    weight: int
    size: int = 1  # how many mods the class stands for
    infl: str | None = None  # influence the mods need
    named: bool = False  # told apart by the target or by a donor's want (kept by name even in class mode)


def scaled(dist: dict) -> list[tuple[object, int]]:
    """A `Fraction` distribution as integer weights with a common denominator."""
    if not dist:
        return []
    denominator = lcm(*(p.denominator for p in dist.values()))
    return [(state, int(p * denominator)) for state, p in dist.items() if p]


class World:
    """Classes, caps and prices; the kernels and the offered actions of every state."""

    def __init__(self, classes, *, costs, caps=None, goal, count_table=COUNT_TABLE):
        self.classes: dict[str, Cls] = {c.name: c for c in classes}
        self.caps = caps or {"p": 3, "s": 3}
        self.costs = costs
        self.goal = goal  # (state) -> bool
        self.count_table = count_table
        self._kernels: dict = {}
        self.stats = Counter()

    # ----- states -----
    def state(self, tokens=(), infl=()) -> State:
        return (tuple(sorted(infl)), tuple(sorted(tokens)))

    def blank(self, infl=()) -> State:
        return self.state((), infl)

    def held(self, state: State, side: str | None = None) -> Counter:
        counts = Counter(state[1])
        if side is not None:
            counts = Counter({t: n for t, n in counts.items() if self.classes[t].side == side})
        return counts

    def pool(self, infl, held: Counter, sides_open: dict[str, bool]) -> list[tuple[str, int, int]]:
        """(class name, available count, weight) of the classes an item with `infl` can draw, on the open sides."""
        out = []
        for c in self.classes.values():
            if not sides_open.get(c.side, False):
                continue
            if c.infl is not None and c.infl not in infl:
                continue
            avail = c.size - held.get(c.name, 0)
            if avail > 0:
                out.append((c.name, avail, c.weight))
        return out

    def open_sides(self, held_all: Counter) -> dict[str, bool]:
        total = {side: 0 for side in self.caps}
        for token, n in held_all.items():
            total[self.classes[token].side] += n
        return {side: total[side] < self.caps[side] for side in self.caps}

    # ----- generic successive draw -----
    def draw(self, entries, k: int, caps_left: dict[str, int]) -> dict[tuple, Fraction]:
        """Draw up to `k` families successively. `entries` is a list of (key, side, weight, count, mult, out_token): `count`
        families of multiplicity `mult` (a family doubled over two inputs has mult 2: twice the chance, then closed), `weight`
        each mod. Returns {sorted tuple of out_tokens: probability}. A side whose cap is reached closes. Ends early when the pool is empty."""
        keys = [e[0] for e in entries]
        info = {e[0]: e for e in entries}
        sides = sorted(caps_left)
        room0 = tuple(caps_left[s] for s in sides)
        dist = {(tuple(info[key][3] for key in keys), room0, ()): Fraction(1)}
        done: dict[tuple, Fraction] = {}
        for _ in range(k):
            nxt: dict = {}
            for (counts, room, picked), p in dist.items():
                weights = []
                for i, key in enumerate(keys):
                    _, side, weight, _, mult, _ = info[key]
                    ok = counts[i] > 0 and room[sides.index(side)] > 0
                    weights.append(counts[i] * mult * weight if ok else 0)
                total = sum(weights)
                if total == 0:
                    done[picked] = done.get(picked, 0) + p
                    continue
                for i, key in enumerate(keys):
                    if not weights[i]:
                        continue
                    _, side, _, _, _, token = info[key]
                    new_counts = counts[:i] + (counts[i] - 1,) + counts[i + 1 :]
                    j = sides.index(side)
                    new_room = room[:j] + (room[j] - 1,) + room[j + 1 :]
                    state = (new_counts, new_room, tuple(sorted(picked + (token,))))
                    nxt[state] = nxt.get(state, 0) + p * Fraction(weights[i], total)
            dist = nxt
        out: dict[tuple, Fraction] = dict(done)
        for (counts, room, picked), p in dist.items():
            out[picked] = out.get(picked, 0) + p
        return out

    # ----- single-item kernels -----
    def k_alt(self, state):
        infl = state[0]
        pool = self.pool(infl, Counter(), {s: True for s in self.caps})
        total = sum(a * w for _, a, w in pool)
        dist = {}
        for name, a, w in pool:
            dist[self.state((name,), infl)] = Fraction(a * w, total)
        return dist

    def k_exalt(self, state):
        held = self.held(state)
        pool = self.pool(state[0], held, self.open_sides(held))
        total = sum(a * w for _, a, w in pool)
        if not total:
            return None
        return {self.state(state[1] + (name,), state[0]): Fraction(a * w, total) for name, a, w in pool}

    def k_annul(self, state):
        if not state[1]:
            return None
        n = len(state[1])
        dist: dict = {}
        for i, token in enumerate(state[1]):
            rest = state[1][:i] + state[1][i + 1 :]
            key = self.state(rest, state[0])
            dist[key] = dist.get(key, 0) + Fraction(1, n)
        return dist

    def k_chaos(self, state):
        cached = self._kernels.get(("chaos", state[0]))
        if cached is not None:
            return cached
        entries = [
            (c.name, c.side, c.weight, c.size, 1, c.name)
            for c in self.classes.values()
            if c.infl is None or c.infl in state[0]
        ]
        dist: dict = {}
        for total_mods, p in CHAOS_TOTAL.items():
            for picked, q in self.draw(entries, total_mods, dict(self.caps)).items():
                key = self.state(picked, state[0])
                dist[key] = dist.get(key, 0) + p * q
        self._kernels[("chaos", state[0])] = dist
        return dist

    # ----- two-item kernels -----
    def k_recomb(self, r: State, d: State):
        """The unpredictable recombinator on one side per call; the hypergeometric overlap of class counts when classes hold several mods."""
        key = (r, d) if r <= d else (d, r)
        cached = self._kernels.get(("recomb", key))
        if cached is not None:
            return cached
        self.stats["recomb_kernels"] += 1
        rc, dc = self.held(r), self.held(d)
        sides = sorted({c.side for c in self.classes.values()})
        per_side = []
        for side in sides:
            names = [c for c in self.classes.values() if c.side == side and (rc.get(c.name) or dc.get(c.name))]
            pooled = sum(rc.get(c.name, 0) + dc.get(c.name, 0) for c in names)
            if pooled == 0:
                per_side.append({(): Fraction(1)})
                continue
            row = self.count_table[min(pooled, 6)]
            row_total = sum(row.values())
            overlaps = [self._overlap(c, rc.get(c.name, 0), dc.get(c.name, 0)) for c in names]  # lists of (shared, prob)
            side_dist: dict = {}
            for combo in itertools.product(*overlaps):
                p_overlap = Fraction(1)
                entries = []
                for c, (shared, prob) in zip(names, combo):
                    p_overlap *= prob
                    singles = rc.get(c.name, 0) + dc.get(c.name, 0) - 2 * shared
                    if singles:
                        entries.append((c.name + "|1", side, c.weight, singles, 1, c.name))
                    if shared:
                        entries.append((c.name + "|2", side, c.weight, shared, 2, c.name))
                for kept, q in row.items():
                    pk = Fraction(q, row_total)
                    if kept == 0:
                        side_dist[()] = side_dist.get((), 0) + p_overlap * pk
                        continue
                    for picked, pp in self.draw(entries, min(kept, self.caps[side]), {side: self.caps[side]}).items():
                        side_dist[picked] = side_dist.get(picked, 0) + p_overlap * pk * pp
            per_side.append(side_dist)
        out: dict = {}
        for combo in itertools.product(*(list(d.items()) for d in per_side)):
            tokens: tuple = ()
            prob = Fraction(1)
            for picked, pp in combo:
                tokens += picked
                prob *= pp
            key2 = self.state(tokens, r[0])
            out[key2] = out.get(key2, 0) + prob
        self._kernels[("recomb", key)] = out
        return out

    def _overlap(self, c: Cls, kr: int, kd: int):
        """P(the receiver and the donor share s mods of the class), the donor's names uniform among the class (hypergeometric)."""
        if kr == 0 or kd == 0:
            return [(0, Fraction(1))]
        if c.size == 1:
            return [(1, Fraction(1))]  # one named mod held by both inputs
        out = []
        for s in range(0, min(kr, kd) + 1):
            ways = comb(kr, s) * comb(c.size - kr, kd - s)
            if ways:
                out.append((s, Fraction(ways, comb(c.size, kd))))
        return out

    def influenced(self, state: State) -> Counter:
        return Counter({t: n for t, n in self.held(state).items() if self.classes[t].infl is not None})

    def k_awakener(self, r: State, d: State):
        """ADR-0032 without the group conflict: one influenced mod of each input (uniform among the valid pairs), the rest a Chaos-style reroll with the kept mods counted inside the total."""
        pkey = ("awake", (r[0], tuple(t for t in r[1] if self.classes[t].infl is not None)), (d[0], tuple(t for t in d[1] if self.classes[t].infl is not None)))
        if pkey in self._kernels:
            return self._kernels[pkey]
        self.stats["awakener_kernels"] += 1
        ri, di = self.influenced(r), self.influenced(d)
        infl = tuple(sorted(set(r[0]) | set(d[0])))
        pairs = Counter()
        for a, na in ri.items():
            for b, nb in di.items():
                ways = na * nb
                if a == b and self.classes[a].size == 1:
                    ways = 0  # the same mod cannot be on both inputs
                if a == b and self.classes[a].size > 1:
                    ways = na * nb - min(na, nb)  # class mode: some pairs coincide
                if ways:
                    pairs[(a, b)] += ways
        total = sum(pairs.values())
        out: dict = {}
        if not total:
            self._kernels[pkey] = None
            return None
        for (a, b), ways in pairs.items():
            kept = (a, b)
            held = Counter(kept)
            sides_room = dict(self.caps)
            for token in kept:
                sides_room[self.classes[token].side] -= 1
            entries = [
                (c.name, c.side, c.weight, c.size - held.get(c.name, 0), 1, c.name)
                for c in self.classes.values()
                if (c.infl is None or c.infl in infl) and c.size - held.get(c.name, 0) > 0
            ]
            for total_mods, p in CHAOS_TOTAL.items():
                fill = total_mods - 2
                for picked, q in self.draw(entries, fill, sides_room).items():
                    state = self.state(kept + picked, infl)
                    out[state] = out.get(state, 0) + Fraction(ways, total) * p * q
        self._kernels[pkey] = out
        return out

    # ----- actions -----
    def base_actions(self, state: State):
        """Single-item actions of `state` as (label, cost, {successor: probability})."""
        c = self.costs
        out = []
        for label, kernel in (("alt", self.k_alt), ("exalt", self.k_exalt), ("annul", self.k_annul), ("chaos", self.k_chaos)):
            if label not in c:
                continue
            dist = kernel(state)
            if dist:
                out.append((label, c[label], dist))
        if "scour" in c and state[1]:
            out.append(("scour", c["scour"], {self.state((), state[0]): Fraction(1)}))
        for label, (at, to, price) in c.get("buys", {}).items():
            if state == at:
                out.append((label, price, {to: Fraction(1)}))
        return out
