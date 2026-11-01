"""The tail cut on the real R05 ring: the sweep of ADR-0023 (ticket #129). Needs the cached dump; skips without it, as CI does.

R05 is a ring (item level 86) with a fractured All Attributes, the goal Life and the forced Strength of the
Deafening Essence of Rage, and the essence, Remove Crafted Mods and every ring craft of the bench (141 in 3.29.3.3).
Prices are the placeholders of ADR-0023 (essence 2 Chaos, each bench option the Chaos value of what it consumes in a
made-up table); only the ratios count. The exact optimum from the ADR, 2.159763, was found by numpy value iteration on
the 13,172-state graph (measured, not certified); here no exact graph is built: the coarse state of the irrelevant
families pooled in one group (365 blocks) gives the leaf bounds and the cut expands the states its policy enters. The
ADR's sweep found no gap at any `theta`, since the leaves are already exact; so does this one. The sweep down to 1e-6
(thousands of states, tens of minutes) is run by hand and its numbers are in the pull request; the test takes the two
largest `theta` of it. Counts and bounds do not depend on the machine; the time is reported by the run and never
asserted (ADR-0014).
"""

import math

import pytest
from abstraction_support import real_game_data

from crafting_system.abstraction import Abstraction, Coarsening, Goal, Wanted, integer_weights
from crafting_system.actions import ActionError, ApplyEssence, RemoveCraftedMods
from crafting_system.actions.bench import bench_crafts
from crafting_system.items import ExplicitMod, Item, Rarity
from crafting_system.solver import Action, Outcome, solve_bounds, solve_tail_cut

BASE = "Metadata/Items/Rings/Ring1"
LEVEL = 86
FRACTURED, FORCED = "AllAttributes7", "StrengthEssence7_"
ESSENCE = ApplyEssence("Deafening Essence of Rage")
ESSENCE_CHAOS = 2.0
CHAOS = {  # placeholder Chaos values of the currencies a bench option consumes
    "Orb of Transmutation": 0.01, "Orb of Alteration": 0.05, "Orb of Augmentation": 0.02, "Orb of Alchemy": 0.2,
    "Orb of Chance": 0.1, "Chaos Orb": 1.0, "Exalted Orb": 15.0, "Divine Orb": 120.0, "Orb of Scouring": 0.2,
    "Regal Orb": 0.5, "Orb of Annulment": 1.0, "Blessed Orb": 0.1, "Orb of Binding": 0.2, "Jeweller's Orb": 0.01,
    "Orb of Fusing": 0.1, "Chromatic Orb": 0.01, "Orb of Regret": 1.0, "Vaal Orb": 1.0,
}  # fmt: skip
OPTIMUM = 2.159763  # ADR-0023, numpy value iteration on the exact graph, six digits
THETAS = (1e-2, 1e-3)
EXPANDED = {1e-2: 14, 1e-3: 151}  # measured with the entries rule of ADR-0023 (the prototype's visits gave 28 at 1e-2); they pin that rule


class Priced:
    """The exact states, or the blocks of a coarse model, under the offers at the placeholder prices; remembers its actions."""

    def __init__(self, offers, prices, kernel, is_goal):
        self.offers, self.prices, self.kernel, self.goal, self.known = offers, prices, kernel, is_goal, {}

    def is_goal(self, state):
        return self.goal(state)

    def actions(self, state):
        if state not in self.known:
            found = []
            for label, offer in self.offers:
                try:
                    weights = integer_weights(self.kernel(state, offer))
                except ActionError:
                    continue
                found.append(Action(label, self.prices[label], tuple(Outcome(s, w) for s, w in weights.items())))
            self.known[state] = tuple(found)
        return self.known[state]


@pytest.fixture(scope="module")
def r05():
    data = real_game_data()
    item_class = data.base_items[BASE].item_class
    crafts = [craft for craft in bench_crafts(data) if item_class in craft.option(data).item_classes]
    life = Wanted(frozenset(mod.id for mod in data.mods.values() if mod.families == ("IncreasedLife",)))
    ab = Abstraction(data, Goal((life, Wanted(frozenset({FORCED})))), BASE, LEVEL, [RemoveCraftedMods(), *crafts])
    low = tuple(min(stat.min, stat.max) for stat in data.mods[FRACTURED].stats)
    start = ab.compress(
        Item.build(data, base_id=BASE, item_level=LEVEL, rarity=Rarity.RARE, mods=(ExplicitMod(FRACTURED, 1, low, fractured=True),))
    )
    # the label of an offer names it once: 141 ring crafts share 80 display texts ("Bench craft +# to maximum Life" is three of them)
    offers = [("essence", ESSENCE), ("remove crafted mods", RemoveCraftedMods()), *((f"craft:{craft.mod_id}", craft) for craft in crafts)]
    prices = {label: ESSENCE_CHAOS if offer is ESSENCE else sum(CHAOS[x.currency] * x.count for x in offer.cost(data)) for label, offer in offers}
    pooling = Coarsening.pooling_irrelevant(ab, None, start)
    return {
        "start": start,
        "pooling": pooling,
        "exact": Priced(offers, prices, ab.kernel, ab.is_goal),
        "lower": Priced(offers, prices, lambda block, offer: pooling.kernel(block, offer, "lower"), pooling.is_goal),
        "upper": Priced(offers, prices, lambda block, offer: pooling.kernel(block, offer, "upper"), pooling.is_goal),
    }


def cut(r05, theta):
    return solve_tail_cut(r05["exact"], r05["lower"], r05["upper"], r05["pooling"].coarsen, r05["start"], theta)


def test_with_nothing_expanded_the_bounds_are_the_coarse_ones_and_bracket_the_optimum(r05):
    block = r05["pooling"].coarsen(r05["start"])
    coarse = solve_bounds(r05["lower"], r05["upper"], [block])

    found = cut(r05, math.inf)

    assert (found.bounds.lower[r05["start"]], found.bounds.upper[r05["start"]]) == (coarse.lower[block], coarse.upper[block])
    assert found.expanded == frozenset() and len(coarse.lower) == 365
    assert coarse.lower[block] <= OPTIMUM + 1e-6 and OPTIMUM - 1e-6 <= coarse.upper[block]
    assert coarse.gap < 1e-4  # ADR-0023: M1 has no gap on R05


def test_the_sweep_of_the_adr_keeps_the_bounds_around_the_optimum_and_opens_no_gap_at_any_theta(r05):
    start = r05["start"]
    before = frozenset()
    for theta in THETAS:
        found = cut(r05, theta)
        assert found.bounds.lower[start] <= OPTIMUM + 1e-6 and OPTIMUM - 1e-6 <= found.bounds.upper[start], theta
        assert found.bounds.gap < 1e-4, theta  # the leaves are already exact, so no theta opens a gap
        assert start in found.expanded and before < found.expanded, theta  # a smaller theta expands more states
        assert len(found.expanded) == EXPANDED[theta], theta  # of the 13,172 exact states
        before = found.expanded
        print(f"theta {theta:g}: expanded {len(found.expanded)}, leaves {found.leaves}, "
              f"bounds {found.bounds.lower[start]:.6f} .. {found.bounds.upper[start]:.6f}")  # fmt: skip
