"""The per-use chance of what R08 and R09 wait for, and the size of the fossil action set, on the real 3.29.3.3 dump (ticket #61).

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with
`CRAFTING_CACHE_DIR`). They skip cleanly when it is not there; CI fetches it (ticket #165), so they run there.

The pins are what the engine gave on the data of 3.29.3.3 once the Battle Royale copies are out of the pool
(ticket #310; `MovementVelocity2Royale` used to add 1,000 to 1,500 to the boots pools), to twelve digits (a regression pin: the
independent check is the hand oracle of `test_actions_fossil.py` on a small world, and the sampler
below, which rolls the same resonators at random and must agree within five standard errors). Both
routes are at item level 86 on the first released base the guide names:

* R08: Dense + Shuddering in a Potent Chaotic Resonator on Sorcerer Boots (intelligence). "High
  Energy Shield" is a `% increased Energy Shield` prefix of the two best tiers (required level 72 or
  84, 80% to 100%); Movement Speed is the 35% mod (required level 86) or any Movement Speed mod.
* R09: Pristine + Shuddering in a Potent Chaotic Resonator on Two-Toned Boots (evasion and energy
  shield). "High Life" is a Life prefix of the two best tiers (required level 44 or 54, 100 to 129);
  Movement Speed as above.
"""

import random
from collections import Counter
from collections.abc import Callable
from fractions import Fraction

import pytest
from abstraction_support import real_game_data

from crafting_system.actions import ApplyFossils, fossil_actions
from crafting_system.items import Item, Rarity

HIGH_ES = ("DefencesPercent", 72)
HIGH_LIFE = ("IncreasedLife", 44)
TOP_SPEED_LEVEL = 86

R08 = {"high": 0.20126546056572778, "ms35": 0.10768114196413651, "any_ms": 0.6460868517848191,
       "high_ms35": 0.01926147715596514, "high_any_ms": 0.11556886293579084}  # fmt: skip
R09 = {"high": 0.21165771077970283, "ms35": 0.14970395795152905, "any_ms": 0.8982237477091743,
       "high_ms35": 0.031539849723239866, "high_any_ms": 0.1892390983394392}  # fmt: skip


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def base_named(data, name: str) -> str:
    return next(base.id for base in data.base_items.values() if base.name == name)


def empty_rare(data, name: str) -> Item:
    return Item.build(data, base_id=base_named(data, name), item_level=86, rarity=Rarity.RARE, mods=())


def labelled(high: tuple[str, int]) -> Callable:
    family, level = high

    def label(mod):
        if mod.families[0] == family and mod.required_level >= level:
            return "high"
        if mod.families[0] == "MovementVelocity":
            return "ms35" if mod.required_level == TOP_SPEED_LEVEL else "ms"
        return "other"

    return label


def exact(outcomes, label) -> dict[str, float]:
    distribution = outcomes.distribution(label)
    assert sum(distribution.values()) == 1

    def chance(wanted) -> float:
        return float(sum((p for outcome, p in distribution.items() if wanted(dict(outcome))), Fraction(0)))

    return {
        "high": chance(lambda c: c.get("high", 0) >= 1),
        "ms35": chance(lambda c: c.get("ms35", 0) >= 1),
        "any_ms": chance(lambda c: c.get("ms35", 0) + c.get("ms", 0) >= 1),
        "high_ms35": chance(lambda c: c.get("high", 0) >= 1 and c.get("ms35", 0) >= 1),
        "high_any_ms": chance(lambda c: c.get("high", 0) >= 1 and c.get("ms35", 0) + c.get("ms", 0) >= 1),
    }


ROUTES = {
    "R08": ("Sorcerer Boots", ("Dense Fossil", "Shuddering Fossil"), HIGH_ES, R08),
    "R09": ("Two-Toned Boots", ("Pristine Fossil", "Shuddering Fossil"), HIGH_LIFE, R09),
}


@pytest.mark.parametrize("route", ROUTES)
def test_the_chances_per_use_of_the_guides(data, route):
    base, fossils, high, pinned = ROUTES[route]
    action = ApplyFossils(fossils)
    assert action.resonator == "Potent Chaotic Resonator"
    outcomes = action.outcomes(data, empty_rare(data, base))
    assert len(outcomes.components) == 1
    assert exact(outcomes, labelled(high)) == pytest.approx(pinned, rel=1e-12)


@pytest.mark.parametrize("route", ROUTES)
def test_the_sampler_agrees_with_the_exact_chance(data, route):
    base, fossils, high, pinned = ROUTES[route]
    outcomes = ApplyFossils(fossils).outcomes(data, empty_rare(data, base))
    label = labelled(high)
    runs, hits = 20_000, 0
    rng = random.Random(61)
    for _ in range(runs):
        counts = Counter(label(data.mods[entry.mod_id]) for entry in outcomes.sample(rng).mods)
        hits += counts["high"] >= 1 and counts["ms35"] >= 1
    chance = pinned["high_ms35"]
    assert abs(hits / runs - chance) < 5 * (chance * (1 - chance) / runs) ** 0.5


def test_how_many_fossil_actions_a_boots_item_has(data):
    item = empty_rare(data, "Sorcerer Boots")
    actions = fossil_actions(data, item)
    assert Counter(len(action.fossils) for action in actions) == {1: 24, 2: 275, 3: 2002, 4: 10395}
    assert len(actions) == 12_696  # 24 usable fossils (all but Bloodstained), without Hollow + Glyphic sets
    assert len(set(actions)) == len(actions)


def test_a_tangled_resonator_is_a_mixture_of_the_tag_pairs_that_differ_on_the_item(data):
    outcomes = ApplyFossils(("Dense Fossil", "Tangled Fossil")).outcomes(data, empty_rare(data, "Sorcerer Boots"))
    assert sum(p for p, _ in outcomes.components) == 1
    assert 1 < len(outcomes.components) <= 420
