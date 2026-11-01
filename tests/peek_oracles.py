"""Independent oracles for the Peek kind of the solver (not collected as tests; ticket #293, ADR-0054).

* `random_peek_spec`: seeded tiny models with at most one Peek, in families (see `FAMILIES`).
* `product_spec`: the EXPLICIT PRODUCT EXPANSION of a Peek model as an ordinary ssp spec of `ssp_oracles`: the Lock
  becomes an ordinary action that leads, by the product of the chosen weights, to a "react" state for every
  combination of one result per option, and the react state lets the player choose. Nothing here uses `solve_peek`.
* `finite_states`, `restricted_spec`: which states of an ssp spec have a finite optimum (a graph fixed point, no
  numbers), and the spec cut down to them so that the HiGHS LP and the exact policy iteration are defined.
* `peek_model`: the same spec as a `TabularModel` holding a `Peek`.

A `PeekSpec` is `(size, table, state, lock, options, fallback, intent)`: base states `0..size-1` are not goals, the
goal is `size`; `table[s]` lists the plain actions `(label, Fraction cost, [(state, weight)])`; `state` is the one
state that offers the Peek `(lock price, options, fallback)` (or `None`, a Peek-free model); an option and a
fallback action are `(label, Fraction cost, [(state, weight)])` like a plain action.
"""

import itertools
import math
import random
from fractions import Fraction
from typing import NamedTuple

from crafting_system.solver import Action, Peek, TabularModel

MAX_COMBOS = 6
FAMILIES = ("burn", "return", "equal", "jewel", "trap")


class PeekSpec(NamedTuple):
    size: int
    table: dict
    state: int | None
    lock: Fraction | None
    options: list
    fallback: list
    intent: int  # seed % 8, the family the generator aimed at


def _weight(rng):
    return rng.randint(1, 10) if rng.random() < 0.85 else rng.choice([25, 100, 1000])


def _cost(rng):
    return Fraction(rng.randint(1, 20), 4)


def _target(rng, size):
    return size if rng.random() < 0.3 else rng.randrange(size)  # the goal is `size`


def _outcomes(rng, size, count):
    return [(_target(rng, size), _weight(rng)) for _ in range(count)]


def _distinct(outcomes):
    return len({state for state, _ in outcomes})


def _limit_combos(options):
    """Cut the options' outcome lists until the product of their distinct result counts is at most MAX_COMBOS."""
    while math.prod(_distinct(option[2]) for option in options) > MAX_COMBOS:
        widest = max(range(len(options)), key=lambda i: (_distinct(options[i][2]), -i))
        options[widest][2].pop()


def _plain_table(rng, size):
    table = {}
    for state in range(size):
        table[state] = [
            (f"{state}.{index}", _cost(rng), _outcomes(rng, size, rng.randint(1, 3)))
            for index in range(rng.choice([0, 1, 1, 1, 2, 2, 2]))
        ]
    return table


def random_peek_spec(seed):
    """A seeded tiny Peek model. `seed % 8` picks the family; everything else is random.

    0 burn self-loop, 1 an option returns to the Peek state, 2 two options with equal kernels, 3 a jewel (empty
    fallback), 4 a trap that never accepts, 5 and 7 fully random (one in ten without any Peek), 6 a mix of 0 to 2.
    """
    rng = random.Random(seed)
    intent = seed % 8
    size = rng.randint(3, 4)
    state = rng.randrange(size)
    table = _plain_table(rng, size)
    lock = _cost(rng)
    count = rng.choice([1, 2, 2])
    options = [
        (f"opt{a}", _cost(rng), _outcomes(rng, size, rng.randint(1, 3))) for a in range(count)
    ]
    fallback = [
        (f"fb{i}", _cost(rng), _outcomes(rng, size, rng.randint(1, 2))) for i in range(rng.randint(0, 2))
    ]
    burn = ("burn", _cost(rng), [(state, _weight(rng))])
    equal = intent == 2 or (intent == 6 and rng.random() < 0.5)
    if intent == 0 or (intent == 6 and rng.random() < 0.5):
        fallback = [burn, *fallback[:1]] if rng.random() < 0.5 else [burn]
    if intent == 1 or (intent == 6 and rng.random() < 0.5):
        options[0][2][rng.randrange(len(options[0][2]))] = (state, _weight(rng))
    if equal:
        if len(options) == 1:
            options.append(options[0])
        first = options[0]
        first[2][:] = first[2][:2]
        options[1] = ("twin", _cost(rng), list(first[2]))
        del options[2:]
    if intent == 3:
        fallback = []
    if intent == 4:
        _make_trap(rng, size, state, table, options, fallback)
    elif intent in (5, 7) and rng.random() < 0.1:
        return PeekSpec(size, table, None, None, [], [], intent)
    _limit_combos(options)
    return PeekSpec(size, table, state, lock, options, fallback, intent)


def _make_trap(rng, size, state, table, options, fallback):
    """Every option result is a dead or trap state, and the fallback is a burn back to the Peek state."""
    others = [s for s in range(size) if s != state]
    dead, loop = others[0], others[1]
    table[dead] = []
    table[loop] = [(f"{loop}.loop", _cost(rng), [(loop, _weight(rng))])]
    for _, _, outcomes in options:
        outcomes[:] = [(rng.choice([dead, loop]), _weight(rng)) for _ in range(rng.randint(1, 3))]
    fallback[:] = [("burn", _cost(rng), [(state, _weight(rng))])]
    if rng.random() < 0.5:  # no plain way out of the Peek state at all
        table[state] = [] if rng.random() < 0.5 else [(f"{state}.loop", _cost(rng), [(state, 1)])]
    else:
        table[state] = [(f"{state}.out", _cost(rng), [(size, _weight(rng)), (state, _weight(rng))])]


def _merged(outcomes):
    merged = {}
    for state, weight in outcomes:
        if weight:
            merged[state] = merged.get(state, 0) + weight
    return list(merged.items())


def _is_dead(spec, state):
    """No action, or only actions that never leave the state."""
    return all(all(t == state for t, _ in outs) for _, _, outs in spec.table[state])


def families(spec):
    """The families a spec belongs to, read off its structure (not from the seed it was drawn with)."""
    found = set()
    if spec.state is None:
        return found
    p = spec.state
    if any(all(t == p for t, _ in outs) for _, _, outs in spec.fallback):
        found.add("burn")
    if any(p in {t for t, _ in _merged(outs)} for _, _, outs in spec.options):
        found.add("return")
    kernels = [sorted(_merged(outs)) for _, _, outs in spec.options]
    if any(kernels[i] == kernels[j] for i, j in itertools.combinations(range(len(kernels)), 2)):
        found.add("equal")
    if not spec.fallback:
        found.add("jewel")
    results = {t for _, _, outs in spec.options for t, _ in outs}
    if (
        spec.fallback
        and all(all(t == p for t, _ in outs) for _, _, outs in spec.fallback)
        and all(t != p and t < spec.size and _is_dead(spec, t) for t in results)
    ):
        found.add("trap")
    return found


def product_spec(spec):
    """The explicit product expansion: an ordinary ssp spec `(size, table)` for `ssp_oracles`.

    The base states keep their numbers; the react states follow, one per combination of one (merged) result per
    option, and the goal stays last. At the Peek state `s` the extra action `('lock', L, ...)` leads to the react
    state of a combination with the product of the chosen weights; a react state offers `('apply a', c_a, [(result_a,
    1)])` for each option and the fallback actions as they are.
    """
    size, table = spec.size, spec.table
    if spec.state is None:
        return size, {s: list(actions) for s, actions in table.items()}
    combos = list(itertools.product(*(_merged(outs) for _, _, outs in spec.options)))
    goal = size + len(combos)

    def remap(outcomes):
        return [(goal if t == size else t, w) for t, w in outcomes]

    product = {s: [(label, cost, remap(outs)) for label, cost, outs in actions] for s, actions in table.items()}
    lock = []
    for index, combo in enumerate(combos):
        node = size + index
        lock.append((node, math.prod(weight for _, weight in combo)))
        product[node] = [
            (f"apply {label}", cost, remap([(result, 1)]))
            for (label, cost, _), (result, _) in zip(spec.options, combo)
        ] + [(label, cost, remap(outs)) for label, cost, outs in spec.fallback]
    product[spec.state].append(("lock", spec.lock, lock))
    return goal, product


def peek_model(spec):
    """The spec as a `TabularModel` with a `Peek` at its state (costs in float64, as the solver reads them)."""

    def action(label, cost, outcomes):
        return Action(label, float(cost), tuple(outcomes))

    actions = {s: [action(*a) for a in plain] for s, plain in spec.table.items()}
    if spec.state is not None:
        actions[spec.state].append(
            Peek(
                "lock",
                float(spec.lock),
                tuple(action(*o) for o in spec.options),
                tuple(action(*f) for f in spec.fallback),
            )
        )
    return TabularModel([spec.size], actions)


def policy_count(spec):
    """How many deterministic policies `brute_force` would try on this ssp spec."""
    size, table = spec
    return math.prod(len(table[s]) or 1 for s in range(size))


def finite_states(spec):
    """The states with a finite optimum: those with a proper policy (the greatest fixed point; graph only).

    Repeat: keep the states that reach the goal using only actions whose outcomes all stay in the kept set.
    """
    size, table = spec
    alive = set(range(size))
    while True:
        usable = {
            s: [outs for _, _, outs in table[s] if all(t == size or t in alive for t, _ in outs)] for s in alive
        }
        reach, grew = set(), True
        while grew:
            grew = False
            for s in alive - reach:
                if any(t == size or t in reach for outs in usable[s] for t, _ in outs):
                    reach.add(s)
                    grew = True
        if reach == alive:
            return alive
        alive = reach


def restricted_spec(spec, keep):
    """The spec cut to the states `keep` (renumbered in order, goal last) and the actions that stay inside them.

    Returns `(restricted spec, order)`, `order` the kept states in the new numbering. With `keep` the finite
    states the restricted problem has a proper policy everywhere, and the same optimum as the original.
    """
    size, table = spec
    order = sorted(keep)
    number = {s: i for i, s in enumerate(order)}
    goal = len(order)
    cut = {}
    for s in order:
        cut[number[s]] = [
            (label, cost, [(goal if t == size else number[t], w) for t, w in outs])
            for label, cost, outs in table[s]
            if all(t == size or t in number for t, _ in outs)
        ]
    return (goal, cut), order
