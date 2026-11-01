"""Worlds for the donor-wants fixtures of ADR-0062 (tickets #211 and #212): a tiny recombinator world and an R25-sized one.

`TinyWorld` is the small world of `test_donor_wants_reference.py` (mods named one by one, a recombination whose donor is a
`Need`); `R25World` is the recombinator world of the R25 measurement of the ADR (three target prefixes and nine junk prefixes
in three weight classes, junk told apart by weight in class mode or named one by one in raw mode). Both give the full model
`M` that `solve_lazily` takes: every plain action of a state and, for every donor, a candidate recombination.
"""

import itertools
import random
from collections import Counter
from fractions import Fraction
from math import comb, lcm

from crafting_system.solver import Acquisition, Action, Need, solve

# percent kept by pooled count (ADR-0033, the guide's table; renormalised per row)
COUNT_TABLE = {1: {0: 41, 1: 59}, 2: {1: 67, 2: 33}, 3: {1: 39, 2: 52, 3: 10}, 4: {1: 11, 2: 59, 3: 31}}


def scaled(dist):
    denominator = lcm(*(Fraction(p).denominator for p in dist.values()))
    return tuple((state, int(Fraction(p) * denominator)) for state, p in dist.items() if p)


class TinyWorld:
    """Items are sorted tuples of mod names (every mod its own family); `weights` maps a mod to its spawn weight."""

    def __init__(self, weights, costs, cap=2):
        self.weights, self.costs, self.cap = weights, costs, cap
        self.goal = tuple(sorted(name for name in weights if name in "AB"))

    def states(self):
        names = sorted(self.weights)
        return [c for n in range(self.cap + 1) for c in itertools.combinations(names, n)]

    def donors(self):
        return [s for s in self.states() if s]

    def is_goal(self, state):
        return state == self.goal

    # --- kernels ---
    def alt(self, state):
        total = sum(self.weights.values())
        return {(name,): Fraction(w, total) for name, w in self.weights.items()}

    def exalt(self, state):
        free = {n: w for n, w in self.weights.items() if n not in state}
        if len(state) >= self.cap or not free:
            return None
        total = sum(free.values())
        return {tuple(sorted(state + (n,))): Fraction(w, total) for n, w in free.items()}

    def annul(self, state):
        if not state:
            return None
        dist = {}
        for i in range(len(state)):
            rest = state[:i] + state[i + 1 :]
            dist[rest] = dist.get(rest, 0) + Fraction(1, len(state))
        return dist

    def recomb(self, a, b):
        """Dynamic programming over the picked sets: pooled entries (a mod on both inputs twice), a family closed once picked."""
        entries = list(a) + list(b)
        row = COUNT_TABLE[min(len(entries), 4)]
        total = sum(row.values())
        out = {}
        for kept, percent in row.items():
            dist = {(): Fraction(1)}
            for _ in range(min(kept, self.cap)):
                nxt = {}
                for picked, p in dist.items():
                    live = [(n, self.weights[n]) for n in entries if n not in picked]
                    weight = sum(w for _, w in live)
                    if not weight:
                        nxt[picked] = nxt.get(picked, 0) + p
                        continue
                    for n in {n for n, _ in live}:
                        share = Fraction(sum(w for m, w in live if m == n), weight)
                        key = tuple(sorted(picked + (n,)))
                        nxt[key] = nxt.get(key, 0) + p * share
                dist = nxt
            for picked, p in dist.items():
                out[picked] = out.get(picked, 0) + p * Fraction(percent, total)
        return out

    def recomb_by_orders(self, a, b):
        """The same kernel from the ordered draws of the formula, one entry at a time, closing its family."""
        entries = list(a) + list(b)
        row = COUNT_TABLE[min(len(entries), 4)]
        total = sum(row.values())
        out = {}

        def draw(remaining, picked, left, p, percent):
            if left == 0 or not remaining:
                key = tuple(sorted(picked))
                out[key] = out.get(key, 0) + p * Fraction(percent, total)
                return
            weight = sum(self.weights[n] for n in remaining)
            for i, n in enumerate(remaining):
                rest = [m for m in remaining if m != n]
                draw(rest, picked + [n], left - 1, p * Fraction(self.weights[n], weight), percent)

        for kept, percent in row.items():
            draw(entries, [], min(kept, self.cap), Fraction(1), percent)
        return out

    # --- the base model of the solver ---
    def model(self, offers):
        world = self
        cache = {}

        class Model:
            def is_goal(self, state):
                return world.is_goal(state)

            def actions(self, state):
                if state in cache:
                    return cache[state]
                found = []
                for label, kernel in (("alt", world.alt), ("exalt", world.exalt), ("annul", world.annul)):
                    if label in world.costs and (dist := kernel(state)):
                        found.append(Action(label, world.costs[label], scaled(dist)))
                for donor in offers(state):
                    found.append(
                        Action(("recomb", donor), world.costs["recomb"], scaled(world.recomb(state, donor)), (Need((), donor),))
                    )
                cache[state] = tuple(found)
                return cache[state]

        return Model()

    def full_model(self):
        """The full model `M` of `solve_lazily`: every plain action of a state and a recombination candidate for every donor."""
        return self.model(lambda state: self.donors())

    def solve(self, offers, **options):
        acquisition = Acquisition(self.model(offers))
        solution = solve(acquisition, [acquisition.start(())], **options)
        return solution, acquisition


def world_of(seed):
    rng = random.Random(seed)
    weights = {"A": rng.choice([1, 2, 5]), "B": rng.choice([1, 3, 9])}
    if rng.random() < 0.7:
        weights["J"] = rng.choice([2, 6, 20])
    costs = {"alt": 1, "recomb": rng.choice([1, 3, 10])}
    if rng.random() < 0.5:
        costs["exalt"] = rng.choice([2, 5])
    if rng.random() < 0.5:
        costs["annul"] = rng.choice([1, 3])
    return TinyWorld(weights, costs)


def product_spec(acquisition, start):
    """The reachable product as an oracle spec: goals and, per state, (label, cost, outcomes, inputs)."""
    seen, stack, table, goals = {start}, [start], {}, set()
    while stack:
        x = stack.pop()
        if acquisition.is_goal(x):
            goals.add(x)
            continue
        rows = []
        for a in acquisition.actions(x):
            rows.append((a.label, Fraction(a.cost), [(o.state, o.weight) for o in a.outcomes], list(a.extra_inputs)))
            for t in [o.state for o in a.outcomes] + list(a.extra_inputs):
                if t not in seen:
                    seen.add(t)
                    stack.append(t)
        table[x] = rows
    return goals, table


def branching_components(acquisition, start):
    """Sizes of the strongly connected components of the product that hold an input edge (outcome and input edges alike)."""
    order, edges = [start], {}
    seen = {start}
    for x in order:
        out = []
        if not acquisition.is_goal(x):
            for a in acquisition.actions(x):
                out += [(o.state, False) for o in a.outcomes] + [(y, True) for y in a.extra_inputs]
        edges[x] = out
        for y, _ in out:
            if y not in seen:
                seen.add(y)
                order.append(y)
    forward = {x: [y for y, _ in out] for x, out in edges.items()}
    backward = {x: [] for x in order}
    for x, ys in forward.items():
        for y in ys:
            backward[y].append(x)

    def closure(root, graph):
        found, stack = {root}, [root]
        while stack:
            for y in graph[stack.pop()]:
                if y not in found:
                    found.add(y)
                    stack.append(y)
        return found

    done, sizes = set(), []
    for x in order:
        if x in done:
            continue
        component = closure(x, forward) & closure(x, backward)
        done |= component
        if any(is_input and y in component for z in component for y, is_input in edges[z]):
            sizes.append(len(component))
    return sorted(sizes, reverse=True)


# --- the R25-sized recombinator world of the ADR-0062 measurement ---------------------------------------------------

# The guide's kept-count table of ADR-0033, rows 1 to 6 (percent kept by pooled count; rows 3 and 4 sum to 101 and are renormalised)
R25_COUNT_TABLE = {
    1: {0: 41, 1: 59},
    2: {1: 67, 2: 33},
    3: {1: 39, 2: 52, 3: 10},
    4: {1: 11, 2: 59, 3: 31},
    5: {2: 43, 3: 57},
    6: {2: 28, 3: 72},
}

R25_COSTS = {"alt": 1, "exalt": 50, "annul": 20, "recomb": 140}

# An item is a sorted tuple of class names with repeats; a class stands for `size` mods that every action treats alike.
type Item = tuple[str, ...]


class R25World:
    """Prefixes on one item: three target mods and junk classes; the recombinator of ADR-0033 on one side.

    Class mode (`raw=False`) tells junk apart by weight: a class `J<weight>` stands for `count` mods of that weight, and the
    chance that a donor's junk is the receiver's own is the hypergeometric overlap of the class counts. Raw mode names
    every junk mod (`J<weight>_<k>`, a class of size 1). Targets are named in both modes. A mod is its own family, and a mod
    on both inputs of a recombination is drawn with twice the chance and then closes its family. Draws are successive,
    without replacement, weighted by the mod's weight.

    `junk` lists `(weight, count)` per weight class; `cap` is the number of prefix slots; the goal holds exactly `targets`.
    """

    def __init__(
        self,
        raw: bool,
        junk: tuple[tuple[int, int], ...] = ((500, 3), (1000, 3), (1500, 3)),
        targets: tuple[str, ...] = ("A", "B", "C"),
        target_weight: int = 100,
        costs: dict[str, int] | None = None,
        cap: int = 3,
    ) -> None:
        self.raw, self.cap = raw, cap
        self.costs = dict(R25_COSTS if costs is None else costs)
        self.targets = tuple(sorted(targets))
        self.weight: dict[str, int] = {name: target_weight for name in targets}
        self.size: dict[str, int] = {name: 1 for name in targets}
        for weight, count in junk:
            if raw:
                for k in range(count):
                    self.weight[f"J{weight}_{k}"] = weight
                    self.size[f"J{weight}_{k}"] = 1
            else:
                self.weight[f"J{weight}"] = weight
                self.size[f"J{weight}"] = count
        self.blank: Item = ()
        self._kernels: dict[tuple[Item, Item], dict[Item, Fraction]] = {}
        self._actions: dict[Item, tuple[Action[Item], ...]] = {}

    # --- states ---
    def states(self) -> list[Item]:
        """Every item the world can hold: multisets of classes within the cap and the class sizes."""
        names = sorted(self.weight)
        found: list[Item] = []
        for n in range(self.cap + 1):
            for combo in itertools.combinations_with_replacement(names, n):
                if all(count <= self.size[name] for name, count in Counter(combo).items()):
                    found.append(combo)
        return found

    def donors(self) -> list[Item]:
        return [state for state in self.states() if state]

    def is_goal(self, state: Item) -> bool:
        return state == self.targets

    def isolated_feeder(self, state: Item, action: Action[Item]) -> bool:
        """The seed of the lazy loop: a recombination candidate whose donor holds only target classes."""
        _, donor = action.label
        return all(name in self.targets for name in donor)

    feeder_seed = isolated_feeder  # the same callable under the name the lazy runs pass as `seed`

    # --- single-item kernels ---
    def alt(self, state: Item) -> dict[Item, Fraction]:
        total = sum(self.size[name] * self.weight[name] for name in self.weight)
        return {(name,): Fraction(self.size[name] * self.weight[name], total) for name in sorted(self.weight)}

    def exalt(self, state: Item) -> dict[Item, Fraction] | None:
        if len(state) >= self.cap:
            return None
        held = Counter(state)
        pool = [(name, self.size[name] - held.get(name, 0)) for name in sorted(self.weight)]
        pool = [(name, free) for name, free in pool if free > 0]
        total = sum(free * self.weight[name] for name, free in pool)
        if not total:
            return None
        return {tuple(sorted(state + (name,))): Fraction(free * self.weight[name], total) for name, free in pool}

    def annul(self, state: Item) -> dict[Item, Fraction] | None:
        if not state:
            return None
        dist: dict[Item, Fraction] = {}
        for i in range(len(state)):
            rest = state[:i] + state[i + 1 :]
            dist[rest] = dist.get(rest, 0) + Fraction(1, len(state))
        return dist

    # --- the recombination ---
    def draw(self, entries: list[tuple[int, int, int, str]], k: int) -> dict[Item, Fraction]:
        """Draw up to `k` families successively. An entry is (count, mult, weight, token): `count` families of multiplicity
        `mult` (a family on both inputs has mult 2: twice the chance, then closed), `weight` each mod. Returns
        {sorted tuple of picked tokens: probability}. The cap of the item closes the draw; so does an empty pool."""
        counts = tuple(entry[0] for entry in entries)
        dist: dict[tuple[tuple[int, ...], Item], Fraction] = {(counts, ()): Fraction(1)}
        done: dict[Item, Fraction] = {}
        for _ in range(k):
            nxt: dict[tuple[tuple[int, ...], Item], Fraction] = {}
            for (left, picked), p in dist.items():
                weights = [left[i] * mult * weight for i, (_, mult, weight, _) in enumerate(entries)]
                total = sum(weights)
                if not total:
                    done[picked] = done.get(picked, 0) + p
                    continue
                for i, entry in enumerate(entries):
                    if not weights[i]:
                        continue
                    key = (left[:i] + (left[i] - 1,) + left[i + 1 :], tuple(sorted((*picked, entry[3]))))
                    nxt[key] = nxt.get(key, 0) + p * Fraction(weights[i], total)
            dist = nxt
        out = dict(done)
        for (_, picked), p in dist.items():
            out[picked] = out.get(picked, 0) + p
        return out

    def overlap(self, name: str, receiver: int, donor: int) -> list[tuple[int, Fraction]]:
        """P(the receiver and the donor share s mods of the class), the donor's names uniform among the class (hypergeometric)."""
        if receiver == 0 or donor == 0:
            return [(0, Fraction(1))]
        size = self.size[name]
        if size == 1:
            return [(1, Fraction(1))]  # one named mod held by both inputs
        out = []
        for shared in range(min(receiver, donor) + 1):
            ways = comb(receiver, shared) * comb(size - receiver, donor - shared)
            if ways:
                out.append((shared, Fraction(ways, comb(size, donor))))
        return out

    def recomb(self, receiver: Item, donor: Item) -> dict[Item, Fraction]:
        """The unpredictable recombinator on one side (ADR-0033): how many mods are kept depends on the pooled count."""
        key = (receiver, donor) if receiver <= donor else (donor, receiver)
        found = self._kernels.get(key)
        if found is not None:
            return found
        held_receiver, held_donor = Counter(receiver), Counter(donor)
        names = [name for name in sorted(self.weight) if held_receiver.get(name) or held_donor.get(name)]
        pooled = len(receiver) + len(donor)
        out: dict[Item, Fraction] = {}
        if pooled == 0:
            out[()] = Fraction(1)
        else:
            row = R25_COUNT_TABLE[min(pooled, 6)]
            row_total = sum(row.values())
            overlaps = [self.overlap(name, held_receiver.get(name, 0), held_donor.get(name, 0)) for name in names]
            for combo in itertools.product(*overlaps):
                p_overlap = Fraction(1)
                entries: list[tuple[int, int, int, str]] = []
                for name, (shared, prob) in zip(names, combo):
                    p_overlap *= prob
                    singles = held_receiver.get(name, 0) + held_donor.get(name, 0) - 2 * shared
                    if singles:
                        entries.append((singles, 1, self.weight[name], name))
                    if shared:
                        entries.append((shared, 2, self.weight[name], name))
                for kept, percent in row.items():
                    chance = p_overlap * Fraction(percent, row_total)
                    if kept == 0:
                        out[()] = out.get((), 0) + chance
                        continue
                    for picked, p in self.draw(entries, min(kept, self.cap)).items():
                        out[picked] = out.get(picked, 0) + chance * p
        self._kernels[key] = out
        return out

    # --- the full model M ---
    def actions(self, state: Item) -> tuple[Action[Item], ...]:
        found = self._actions.get(state)
        if found is None:
            built: list[Action[Item]] = []
            for label, kernel in (("alt", self.alt), ("exalt", self.exalt), ("annul", self.annul)):
                if label in self.costs and (dist := kernel(state)):
                    built.append(Action(label, self.costs[label], scaled(dist)))
            for donor in self.donors():
                if dist := self.recomb(state, donor):
                    built.append(Action(("recomb", donor), self.costs["recomb"], scaled(dist), (Need(self.blank, donor),)))
            found = self._actions[state] = tuple(built)
        return found

    def full_model(self) -> "R25World":
        """The model `M` of `solve_lazily`: every plain action of a state and, for every donor, a recombination candidate."""
        return self
