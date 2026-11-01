"""The base model over a `World`, the acquisition product through the real `solver.Acquisition`, and the lazy offer loop.

A want is `(kind, state)`: kind "full" is a whole item (a recombinator's donor, every mod counts), kind "awk" is the
Awakener's projection (the influences and the influenced mods; the rest of the donor is rerolled and never read).
`reaches(s, want)` is the want predicate of the acquisition: equality of the whole item, or of the projection.
"""

import heapq
import math
import time
from collections import Counter
from dataclasses import dataclass, field

from crafting_system.solver import Acquisition, Action, Need, solve

from world import World, scaled


def awk_proj(world: World, state):
    """What the Awakener's Orb reads of a donor: its influences and the influenced mods."""
    return (state[0], tuple(t for t in state[1] if world.classes[t].infl is not None))


class Proc:
    """The base model: single-item actions plus the two-input actions to the donors `offers(state)` names."""

    def __init__(self, world: World, offers, kinds=("recomb", "awk")):
        self.world = world
        self.offers = offers  # state -> iterable of (kind, donor)
        self.kinds = kinds
        self._cache: dict = {}
        self.calls = 0

    def is_goal(self, state):
        return self.world.goal(state)

    def reaches(self, state, want):
        kind, target = want
        if kind == "full":
            return state == target
        return awk_proj(self.world, state) == target

    def actions(self, state):
        found = self._cache.get(state)
        if found is not None:
            return found
        self.calls += 1
        world = self.world
        out = []
        for label, cost, dist in world.base_actions(state):
            out.append(Action(label, cost, scaled(dist)))
        for kind, donor in self.offers(state):
            action = self.two_input(state, kind, donor)
            if action is not None:
                out.append(action)
        found = tuple(out)
        self._cache[state] = found
        return found

    def two_input(self, state, kind, donor):
        world = self.world
        if kind == "recomb":
            dist = world.k_recomb(state, donor)
            cost = world.costs["recomb"]
        elif kind == "awkf":  # the Awakener asked for a whole donor item instead of its projection
            dist = world.k_awakener(state, donor)
            cost = world.costs["awk"]
        else:
            dist = world.k_awakener(state, donor)
            cost = world.costs["awk"]
        if not dist:
            return None
        need = Need(world.blank(donor[0]), ("awk" if kind == "awk" else "full", donor))
        return Action((kind, donor), cost, scaled(dist), (need,))


def build(world: World, offers):
    proc = Proc(world, offers)
    acq = Acquisition(proc, reaches=proc.reaches)
    return proc, acq


def run(world: World, offers, start, **options):
    """Solve the product from `start`; returns (solution, proc, acq, seconds)."""
    proc, acq = build(world, offers)
    t0 = time.perf_counter()
    sol = solve(acq, [acq.start(start)], **options)
    return sol, proc, acq, time.perf_counter() - t0


def product_stats(sol):
    """States of the product by want, with the finite ones, and the number of wants."""
    wants = Counter()
    for (tag, want, state), value in sol.values.items():
        wants[want if want != "MAIN" else "MAIN"] += 1
    return wants


def determinized(world, proc, candidates, wants_goal):
    """Shortest path (no randomness, inputs free) to a state that reaches `want`, over every offered and candidate action."""
    raise NotImplementedError


class PerWantAcquisition(Acquisition):
    """Needs offered per product state `(want, state)` instead of per base state: the base model gives only the single-item
    actions, `offers(want, state)` the two-input ones (`want` is `MAIN` or a want tuple)."""

    def __init__(self, proc: Proc, offers, **kwargs):
        super().__init__(proc, **kwargs)
        self._proc, self._offers = proc, offers
        self._single: dict = {}

    def actions(self, product):
        _, want, state = product
        single = self._single.get(state)
        if single is None:
            single = tuple(Action(label, cost, scaled(dist)) for label, cost, dist in self._proc.world.base_actions(state))
            self._single[state] = single
        out = [Action(a.label, a.cost, tuple((("in", want, o.state), o.weight) for o in a.outcomes)) for a in single]
        for kind, donor in self._offers(want, state):
            a = self._proc.two_input(state, kind, donor)
            if a is not None:
                out.append(Action(a.label, a.cost, tuple((("in", want, o.state), o.weight) for o in a.outcomes),
                                  tuple(("in", n.want, n.start) for n in a.extra_inputs)))
        return tuple(out)


def run_per_want(world: World, offers, start, **options):
    proc = Proc(world, lambda s: [])
    acq = PerWantAcquisition(proc, offers, reaches=proc.reaches)
    t0 = time.perf_counter()
    sol = solve(acq, [acq.start(start)], **options)
    return sol, proc, acq, time.perf_counter() - t0
