"""The corrupting actions sampled from the claims, against the hand oracles and against the solver (ticket #264, ADR-0039, ADR-0019 layer 2).

The samplers (`simulator.SampledVaalOrb`, `SampledLocus`, `SampledBloodstained`) are written from the registry claims and read nothing of
`actions.corruption`, `actions.locus`, `actions.bloodstained` or `actions.corrupted_pool`. Here they meet two things written apart from them:

1. *One use against the hand oracles.* The ends of 6,000 sampled uses (the implicits the item holds, nothing, or the dead end) against the
   plain fractions of `corruption_support.oracle`, `locus_support.oracle` and `bloodstained_support.implicit_cases`, each end within five
   binomial standard errors; the pool against the hand pools; the values of a drawn implicit uniform over each stat's integers.
2. *A policy against the solver* ("Done when" of #264). "Corrupt, restart on a miss": the solver's value of the chain whose chance of a hit is
   the exact chance the action gives (`chance_all` of the corrupted implicit wanted), and the simulator's mean of the same policy on concrete
   items with the claims' samplers, within five standard errors. On the toy amulet (W = 1,950) and on the real ring of item level 84
   (W = 31,850, ADR-0039's first row: 0.785% per Vaal Orb, 1.686% per use of the Locus).

The chain is built from the action's exact chance, not from `Abstraction.kernel`: for a target that asks for a corrupted implicit the kernel
counts every corrupted outcome that keeps the explicit mods as the goal (issue #750), so its value is not the one ADR-0039 gives.
`test_the_kernel_goal_mass_of_a_vaal_orb_agrees_with_the_claims` shows that at layer 2 and is expected to fail until #750 lands.

Seeds are fixed, so a run is repeatable. The real ring needs the cached 3.29.3.3 dump (`CRAFTING_CACHE_DIR`) and skips cleanly without it.
"""

import math
import random
from collections import Counter
from fractions import Fraction

import bloodstained_support as blood
import corruption_support as vaal
import locus_support as locus
import pytest
from abstraction_support import real_game_data

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import LocusOfCorruption, VaalOrb
from crafting_system.items import Item, Rarity
from crafting_system.rules import get_rule
from crafting_system.simulator import SampledBloodstained, SampledLocus, SampledVaalOrb, Step, corrupted_pool, simulate
from crafting_system.simulator._corruption import CLAIMS
from crafting_system.solver import Action, TabularModel, solve

USES = 6_000
RING_ALL_RES = "V2AllResistancesCorrupted"
QUARTER = Fraction(1, 4)


def corrupted_ids(data, item) -> list[str]:
    return [entry.mod_id for entry in item.implicits if data.mods[entry.mod_id].generation_type == "corrupted"]


def end_of(data, start: Item, result: Item):
    """What one use left, in the words of the hand oracles: nothing, the dead end, or the implicits the item holds."""
    assert result.corrupted
    if result == start.changed(data, corrupted=True):
        return "nothing"
    if not corrupted_ids(data, result):
        assert result.rarity is Rarity.RARE and result.implicits == start.implicits
        assert result.mods == tuple(entry for entry in start.mods if entry.fractured)
        return "dead"
    assert result.mods == start.mods and result.rarity is start.rarity  # the implicit outcomes touch no explicit mod
    return ("implicits", frozenset(entry.mod_id for entry in result.implicits))


def assert_within_five_errors(seen: Counter, expected: dict, uses: int) -> None:
    assert set(seen) <= set(expected), set(seen) - set(expected)
    for end, chance in expected.items():
        share, p = seen[end] / uses, float(chance)
        assert abs(share - p) <= 5 * math.sqrt(p * (1 - p) / uses) + 1e-12, (end, share, p)


def sampled_ends(data, action, start, seed, uses=USES) -> Counter:
    outcomes = action.outcomes(data, start)
    rng = random.Random(seed)
    return Counter(end_of(data, start, outcomes.sample(rng)) for _ in range(uses))


# --- the claims and the pool -----------------------------------------------------------------------------


def test_every_claim_the_samplers_name_is_in_the_registry():
    assert {get_rule(rule_id).id for rule_id in CLAIMS} == CLAIMS


@pytest.mark.parametrize("level", [vaal.LEVEL, 60])
@pytest.mark.parametrize("base", ["amulet", "boots", "belt"])
def test_the_pool_is_the_hand_pool_of_the_vaal_world(base, level):
    item = {"amulet": vaal.amulet(item_level=level), "boots": vaal.on(vaal.BOOTS, item_level=level), "belt": vaal.on(vaal.BELT, item_level=level)}[base]
    assert {mod.id: weight for mod, weight in corrupted_pool(vaal.DATA, item)} == vaal.pool_weights(level)


def test_the_pool_of_a_jewel_is_its_domain_s():
    assert {mod.id: w for mod, w in corrupted_pool(vaal.DATA, vaal.on(vaal.COBALT))} == vaal.pool_weights(vaal.LEVEL, vaal.JEWEL_POOL)
    assert {mod.id: w for mod, w in corrupted_pool(vaal.DATA, vaal.on(vaal.ABYSS))} == vaal.pool_weights(vaal.LEVEL, vaal.ABYSS_POOL)


def test_a_base_with_no_pool_and_a_corrupted_item_are_refused():
    with pytest.raises(ValueError):
        corrupted_pool(vaal.DATA, vaal.on(vaal.NO_POOL_BASE, rarity=Rarity.NORMAL))
    with pytest.raises(ValueError):
        SampledVaalOrb().outcomes(vaal.DATA, vaal.amulet().changed(vaal.DATA, corrupted=True))
    with pytest.raises(ValueError):
        SampledLocus().outcomes(locus.DATA, vaal.amulet().changed(vaal.DATA, corrupted=True))


@pytest.mark.parametrize("share", [Fraction(0), Fraction(3, 2), Fraction(-1, 4)])
def test_a_locus_share_outside_zero_to_one_is_refused(share):
    with pytest.raises(ValueError):
        SampledLocus(share).outcomes(locus.DATA, vaal.starts()["none"])


def test_a_bloodstained_resonator_on_an_empty_pool_is_this_sampler_s_value_error():
    jewel = blood.boots(base=blood.JEWEL, item_level=30, rarity=Rarity.NORMAL)
    with pytest.raises(ValueError, match="no corrupted implicit"):
        SampledBloodstained(blood.bloodstained()).outcomes(blood.DATA, jewel)


def test_the_real_ring_pool_is_adr_0039_s():
    data = real_game_data()
    ring = next(base for base in data.base_items.values() if base.item_class == "Ring" and not base.implicits)
    pool = dict((mod.id, weight) for mod, weight in corrupted_pool(data, Item.build(data, base_id=ring.id, item_level=84, rarity=Rarity.RARE)))
    assert sum(pool.values()) == 31_850 and pool[RING_ALL_RES] == 1000 and len(pool) == 39


# --- one use against the hand oracles --------------------------------------------------------------------


@pytest.mark.parametrize("name", ["none", "one", "two", "belt-stored", "belt-replaced", "fractured", "normal", "magic"])
def test_a_sampled_vaal_orb_follows_the_hand_oracle(name):
    start = vaal.starts()[name]
    hand = vaal.oracle(
        [entry.mod_id for entry in start.implicits], vaal.pool_weights(start.item_level), dead_chance=QUARTER, nothing_chance=2 * QUARTER
    )
    expected = {("implicits", end[1]) if isinstance(end, tuple) else end: chance for end, chance in hand.items()}

    seen = sampled_ends(vaal.DATA, SampledVaalOrb(), start, seed=26400 + len(name))

    assert_within_five_errors(seen, expected, USES)


@pytest.mark.parametrize(("base_id", "unique"), [(vaal.COBALT, True), (vaal.PRISMATIC, False)])
def test_a_sampled_vaal_orb_on_a_jewel_follows_the_hand_oracle(base_id, unique):
    start = vaal.on(base_id, rarity=Rarity.NORMAL)  # a normal jewel: its dead end (a rare) and "nothing" differ
    hand = vaal.oracle(
        [], vaal.pool_weights(start.item_level, vaal.JEWEL_POOL),
        dead_chance=2 * QUARTER if unique else QUARTER, nothing_chance=QUARTER if unique else 2 * QUARTER,
    )  # fmt: skip
    expected = {("implicits", end[1]) if isinstance(end, tuple) else end: chance for end, chance in hand.items()}
    seen = sampled_ends(vaal.DATA, SampledVaalOrb(), start, seed=26450)

    assert_within_five_errors(seen, expected, USES)


def three_belt():
    """A normal belt with three implicits of its own, so that its dead end (a rare) and "nothing" differ."""
    return Item.build(locus.DATA, base_id=locus.THREE_BELT, item_level=vaal.LEVEL, rarity=Rarity.NORMAL)


@pytest.mark.parametrize("name", ["none", "one", "two", "belt-stored", "fractured", "three"])
def test_a_sampled_locus_follows_the_hand_oracle(name):
    start = three_belt() if name == "three" else vaal.starts()[name]
    hand = locus.oracle([entry.mod_id for entry in start.implicits], start.item_level)
    expected = {("implicits", end[1]) if isinstance(end, tuple) else end: chance for end, chance in hand.items()}

    seen = sampled_ends(locus.DATA, SampledLocus(), start, seed=26500 + len(name))

    assert_within_five_errors(seen, expected, USES)


def test_the_locus_share_is_the_owner_s_decision_and_can_be_set():
    start = vaal.starts()["none"]
    seen = sampled_ends(locus.DATA, SampledLocus(Fraction(1, 10)), start, seed=26550)
    implicits = sum(count for end, count in seen.items() if isinstance(end, tuple))
    p = 0.1
    assert abs(implicits / USES - p) <= 5 * math.sqrt(p * (1 - p) / USES)
    assert abs(seen["nothing"] / USES - 0.3) <= 5 * math.sqrt(0.3 * 0.7 / USES)
    assert get_rule("corruption.locus_two_implicit_share_decision").value["share"] == 0.25


@pytest.mark.parametrize("others", [(), ("Scorched",), ("Gilded",)], ids=lambda others: "+".join(("Bloodstained", *others)))
@pytest.mark.parametrize("name", ["none", "one", "two", "base-implicit"])
def test_a_sampled_bloodstained_resonator_follows_the_hand_implicit_cases(others, name):
    start = blood.starts()[name]
    resonator = blood.bloodstained(*others)
    hand: dict = {}
    for chance, held in blood.implicit_cases([entry.mod_id for entry in start.implicits], blood.pool_weights(start.item_level), "Gilded" in others):
        hand[held] = hand.get(held, Fraction(0)) + chance
    outcomes = SampledBloodstained(resonator).outcomes(blood.DATA, start)
    rng = random.Random(26600 + len(name) + 7 * len(others))
    seen = Counter()
    for _ in range(USES // 4):
        result = outcomes.sample(rng)
        result.validate(blood.DATA)
        assert result.corrupted and len(corrupted_ids(blood.DATA, result)) == 1  # never fails, never two
        seen[frozenset(entry.mod_id for entry in result.implicits)] += 1

    assert_within_five_errors(seen, hand, USES // 4)


def test_a_bloodstained_sampler_needs_the_bloodstained_fossil():
    with pytest.raises(ValueError):
        SampledBloodstained(blood.plain("Scorched")).outcomes(blood.DATA, blood.starts()["none"])


def test_each_stat_of_a_drawn_implicit_rolls_uniformly_over_its_integers():
    start = vaal.starts()["none"]
    outcomes = SampledVaalOrb().outcomes(vaal.DATA, start)
    rng = random.Random(26700)
    values = Counter()
    drawn = 0
    for _ in range(USES * 2):
        result = outcomes.sample(rng)
        for entry in result.implicits:
            if entry.mod_id == vaal.SECOND:
                drawn += 1
                values.update((index, value) for index, value in enumerate(entry.values))
    # SECOND has the stats (3-5) and (8-9)
    for index, low, high in ((0, 3, 5), (1, 8, 9)):
        width = high - low + 1
        assert {value for (at, value) in values if at == index} == set(range(low, high + 1))
        for value in range(low, high + 1):
            p = 1 / width
            assert abs(values[(index, value)] / drawn - p) <= 5 * math.sqrt(p * (1 - p) / drawn)


# --- a policy against the solver ("Done when") ------------------------------------------------------------


class Fresh:
    """The restart: a new start item, bought at the price of the step."""

    def __init__(self, item):
        self.item = item

    def outcomes(self, data, item):
        return self

    def sample(self, rng):
        return self.item


class Cached:
    """An action whose `outcomes` are built once per item (the samplers compute the pool from the whole game data)."""

    def __init__(self, action):
        self.action, self.cache = action, {}

    def outcomes(self, data, item):
        if item not in self.cache:
            self.cache[item] = self.action.outcomes(data, item)
        return self.cache[item]


def solver_value(chance: Fraction, use: float, restart: float) -> float:
    """The solver's value of "corrupt, restart on a miss" from a fresh item, the chain's hit chance being `chance`."""
    scale = chance.denominator
    table = {
        "fresh": [Action("corrupt", use, (("goal", chance.numerator), ("dead", scale - chance.numerator)))],
        "dead": [Action("restart", restart, (("fresh", 1),))],
    }
    value = solve(TabularModel(["goal"], table), ["fresh"]).values["fresh"]
    assert value == pytest.approx((use + float(1 - chance) * restart) / float(chance), rel=1e-9)  # V = use + (1 - p)(restart + V)
    return value


def simulated(data, sampler, start, wanted, use, restart, runs, seed):
    corrupt, fresh = Step(Cached(sampler), use), Step(Fresh(start), restart)

    def policy(item):
        return fresh if item.corrupted else corrupt

    def is_goal(item):
        return item.corrupted and wanted <= {entry.mod_id for entry in item.implicits}

    return simulate(data, policy, start, is_goal, runs=runs, seed=seed)


def assert_agrees(report, value):
    assert report.successes == report.runs
    assert abs(report.cost.value - value) <= 5 * report.cost.standard_error, (report.cost.value, value, report.cost.standard_error)


TOY = {
    # name: (data, start, sampler, the planner's action, wanted corrupted implicits, the exact chance by hand)
    "vaal-amulet": (vaal.DATA, vaal.starts()["none"], SampledVaalOrb(), VaalOrb(), {vaal.ALL_RES}, QUARTER * Fraction(1000, 1950)),
    "vaal-boots-two-implicits": (
        vaal.DATA, vaal.starts()["two"], SampledVaalOrb(), VaalOrb(), {vaal.SECOND, vaal.EXARCH}, QUARTER * Fraction(1, 2) * Fraction(500, 1950),
    ),
    "locus-amulet": (locus.DATA, vaal.starts()["none"], SampledLocus(), LocusOfCorruption(), {vaal.ALL_RES}, None),
}  # fmt: skip


@pytest.mark.parametrize("name", TOY)
def test_a_simulated_corrupt_and_restart_agrees_with_the_solver_on_the_toy(name):
    data, start, sampler, action, wanted, hand = TOY[name]
    # `implicit_chances` counts every implicit of the finished item, the Eldritch one that must stay included
    chance = action.outcomes(data, start).implicit_chances(sorted(wanted))
    if hand is None:  # ADR-0038: the share times the chance of a pair that holds ALL_RES (TWIN shares its group, so never both)
        hand = QUARTER * sum(locus.pair_chance(vaal.ALL_RES, other) for other in locus.pool() if other != vaal.ALL_RES)
    assert chance == hand
    value = solver_value(chance, use=1.0, restart=3.0)

    report = simulated(data, sampler, start, wanted, use=1.0, restart=3.0, runs=1_500, seed=26800 + len(name))

    assert_agrees(report, value)


@pytest.mark.parametrize("which", ["vaal", "locus"])
def test_a_simulated_corrupt_and_restart_agrees_with_the_solver_on_the_real_ring(which):
    data = real_game_data()
    ring = next(base for base in data.base_items.values() if base.item_class == "Ring" and not base.implicits)
    start = Item.build(data, base_id=ring.id, item_level=84, rarity=Rarity.RARE)
    sampler, action, per_use = {"vaal": (SampledVaalOrb(), VaalOrb(), 0.00785), "locus": (SampledLocus(), LocusOfCorruption(), 0.01686)}[which]
    chance = action.outcomes(data, start).chance_all([RING_ALL_RES])
    assert float(chance) == pytest.approx(per_use, abs=5e-6)  # ADR-0039's first row
    value = solver_value(chance, use=1.0, restart=2.0)

    report = simulated(data, sampler, start, {RING_ALL_RES}, use=1.0, restart=2.0, runs=2_000, seed=26900 + len(which))

    assert_agrees(report, value)


# --- the kernel itself (issue #750) -----------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason="#750: the kernel counts every corrupted outcome that keeps the explicit mods as the goal")
def test_the_kernel_goal_mass_of_a_vaal_orb_agrees_with_the_claims():
    start = vaal.starts()["none"]
    ab = Abstraction(vaal.DATA, Goal((Wanted(frozenset({vaal.LIFE_1})),), asks_corrupted=True), start.base_id, start.item_level, [VaalOrb()])
    kernel = ab.kernel(ab.compress(start), VaalOrb())
    goal_mass = sum((chance for state, chance in kernel.items() if ab.is_goal(state)), Fraction(0))
    seen = sampled_ends(vaal.DATA, SampledVaalOrb(), start, seed=27000)
    share = seen[("implicits", frozenset({vaal.ALL_RES}))] / USES  # the target asks for ALL_RES as its corrupted implicit
    p = float(goal_mass)

    assert abs(share - p) <= 5 * math.sqrt(p * (1 - p) / USES)
