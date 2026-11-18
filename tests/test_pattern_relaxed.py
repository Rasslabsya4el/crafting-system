"""The relaxed draw of the bound's build (#975, `abstraction/_relaxed.py`): for a reroll that weighs the families the item holds (the
likelihood Harvest reforges), the choice nodes made at one member stand below the action's exact backup at every member they stand for.

On the toy amulets of `test_planner_harvest_likelihood` (one-weight families, three prefixes and three or four suffixes), at the states a
reforge reaches from the start, for both reforges and for random values of the keys: the least value of the choice nodes (each node the
least of its corner kernels) is at most the backup of the exact kernel (`Abstraction.kernel`, pushed to the keys) at every member of the
key with the same relevant mods and the same count of pure junk families per class, whatever pure junk it holds. And the box of a class
is worked by hand on a small pool.
"""

import dataclasses
import random
from collections import Counter
from fractions import Fraction

import test_planner_harvest_likelihood as toy

from crafting_system.abstraction._pattern import Mode, Pattern, _base, _tagset
from crafting_system.abstraction._relaxed import class_box, relaxed_draw
from crafting_system.actions import HarvestReforgeLikelihood
from crafting_system.data import Weight

MORE, LESS = HarvestReforgeLikelihood(more=True), HarvestReforgeLikelihood(more=False)


def _shape(pattern: Pattern, state) -> tuple:
    """What the members a relaxed draw stands for share: the slots that are not pure junk, and the count of pure junk per class."""
    universe = pattern.universe(state.flags.influences)
    pure = [slot for slot in state.slots if not slot.crafted and _base(slot.kind) in universe.pure[slot.side]]
    kept = tuple(sorted((slot for slot in state.slots if slot not in pure), key=repr))
    return kept, tuple(sorted(Counter((slot.side, _tagset(slot.kind)) for slot in pure).items(), key=repr))


def _check(tmp_path, wanted, held, data) -> int:
    plan = toy._plan(toy._target(tmp_path, wanted, held, data), [], data)
    ab = plan.abstraction
    pattern = Pattern(ab, actions=[MORE, LESS])
    rng = random.Random(975)
    values: dict = {}

    def value(state) -> float:
        key = pattern.key(state)
        if key not in values:
            values[key] = 0.0 if ab.is_goal(state) else rng.uniform(1.0, 100.0)
        return values[key]

    states = {plan.start: None}
    for action in (MORE, LESS):
        states.update(dict.fromkeys(ab.kernel(plan.start, action)))
    checked = 0
    for state in states:
        key = pattern.key(state)
        every = pattern.members(key, Mode.ALL)
        for action in (MORE, LESS):
            assert pattern.mode_of(action, key) is Mode.RELAXED
            for member in pattern.members(key, Mode.RELAXED):
                draw = relaxed_draw(pattern, member, action, action.held_weight_factor())
                assert draw is not None
                least: dict[int, float] = {}

                def node(at: int) -> float:
                    if at not in least:
                        least[at] = min(
                            sum(float(chance) * (node(t) if isinstance(t, int) else value(t)) for t, chance in kernel.items())
                            for kernel in draw.nodes[at]
                        )
                    return least[at]

                node(0)
                for other in every:
                    if _shape(pattern, other) != _shape(pattern, member):
                        continue
                    exact = ab.kernel(other, action)
                    backup = sum(float(chance) * value(successor) for successor, chance in exact.items())
                    assert least[0] <= backup + 1e-9, (state, action)
                    checked += 1
    return checked


def test_the_choice_nodes_stand_below_every_member_of_the_key(tmp_path):
    checked = _check(tmp_path, (toy.GEM, toy.DAMAGE_1, toy.LIFE_1), (toy.GEM, toy.DAMAGE_1, toy.RESIST_1, toy.COLD_RESIST), toy.TOY7)
    assert checked >= 10


def test_the_choice_nodes_stand_below_every_member_where_one_family_is_wanted(tmp_path):
    checked = _check(tmp_path, (toy.LIFE_1,), (toy.GEM, toy.DAMAGE_1, toy.RESIST_1, toy.COLD_RESIST), toy.TOY)
    assert checked >= 4


WEIGHTED = {toy.GEM: 1, toy.DAMAGE_1: 2, toy.LIFE_1: 3, toy.RESIST_1: 5, toy.COLD_RESIST: 8, toy.MANA_1: 13, toy.FIRE_RESIST: 40}


def test_the_choice_nodes_stand_below_every_member_where_the_families_weigh_differently(tmp_path):
    """The box reads the lightest and heaviest fills of a class: with one-weight families they are the same, so the toys above do not test it."""
    data = dataclasses.replace(
        toy.TOY7,
        mods={
            mod_id: dataclasses.replace(mod, spawn_weights=(Weight("amulet", WEIGHTED[mod_id]), Weight("default", 0))) if mod_id in WEIGHTED else mod
            for mod_id, mod in toy.TOY7.mods.items()
        },
    )
    checked = _check(tmp_path, (toy.GEM, toy.DAMAGE_1, toy.LIFE_1), (toy.GEM, toy.DAMAGE_1, toy.RESIST_1, toy.COLD_RESIST), data)
    assert checked >= 10


def test_the_box_of_a_class_by_hand():
    """Three junk families of weights 1, 2 and 4 (`A` = 7), two held, one drawn, More Likely (`f` = 10). Of the drawn and the held the walk
    knows the counts: the least weight left is `7 - 4 + 9 * 1` = 12 (the heaviest drawn, the lightest one held left), the greatest
    `7 - 1 + 9 * (2 + 4)` = 60 (the lightest drawn, the two heaviest held, neither drawn). A fill reaches each: held {1, 4}, the 4 drawn,
    leaves 1*10 + 2 = 12; held {2, 4}, the 1 drawn, leaves 20 + 40 = 60."""
    weights = [Fraction(1), Fraction(2), Fraction(4)]
    factor = Fraction(10)
    lo, hi = class_box(weights, 2, 1, factor)
    fills = []
    for held in ({0, 1}, {0, 2}, {1, 2}):
        for drawn in range(3):
            fills.append(sum(w * (factor if i in held else 1) for i, w in enumerate(weights) if i != drawn))
    assert (lo, hi) == (min(fills), max(fills)) == (12, 60)
    # Less Likely (`f` = 1/10): the least `7 - 4 - 0.9 * (2 + 4)` = -2.4, clipped at 0 (the box is wider than the fills, still sound); the
    # greatest `7 - 1 - 0.9 * 1` = 5.1 (the lightest drawn, the lightest one held left): the fills reach 0.3 and 4.2, inside the box (it
    # takes the drawn and the held apart, so it is wider than the fills where they share a family; wider is still below every member)
    lo, hi = class_box(weights, 2, 1, 1 / factor)
    fills = [sum(w * (1 / factor if i in held else 1) for i, w in enumerate(weights) if i != drawn) for held in ({0, 1}, {0, 2}, {1, 2}) for drawn in range(3)]
    assert lo == 0 <= min(fills) == Fraction(3, 10) and max(fills) == Fraction(21, 5) <= hi == Fraction(51, 10)
