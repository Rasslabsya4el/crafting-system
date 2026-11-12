"""The Vaal Orb's brick as a full-item fill for a target that only allows corruption (ticket #260, ADR-0037, ADR-0036).

A target that allows a corrupted item and asks for no corrupted implicit gets the Vaal Orb whose brick is a draw: the item becomes a rare
of the same base, its fractured mods and the mods of a side locked by `Prefixes/Suffixes Cannot Be Changed` stay (the wiki's reading, the
plan), and it is filled with ordinary draws to a full item (six mods, four on a jewel). Craft of Exile's reading removes the fractured mods
and ignores the locks; it is the second value of the rule axis `corruption.vaal_brick`. A target that asks for a corrupted implicit keeps
the Orb of ticket #259, whose brick is one dead end.

"Done when" of the ticket, and where each line is tested:

1. *Enumeration on a small pool equals the kernel.* `test_the_kernel_equals_the_enumeration`: the hand ends of the Orb (`corruption_support.oracle`)
   with the brick's quarter spread over every full item that `abstraction_oracle.finished_items` enumerates draw by draw, compressed and
   compared with the kernel, at both readings; `test_a_locked_side_stays_and_its_open_slots_fill` does the same for a locked item.
2. *A fractured or locked item differs between the two readings and a plain item does not.* `test_the_readings_differ_only_on_a_fractured_or_locked_item`.
3. *The answer lists the brick claim among its approximate inputs.* `test_the_answer_lists_the_brick_claim_among_its_approximate_inputs`.
"""

import dataclasses
import random
from fractions import Fraction

import pytest
from abstraction_oracle import assert_same_distribution, compressed_distribution, finished_items
from abstraction_pool import CRAFTED, LIFE_1, LIFE_2, MANA_1, RESIST_2, RESISTS
from contract_support import _roll, check_action, finished
from corruption_support import BELT, COBALT, DATA, JEWEL_POOL, PRISMATIC, amulet, on, oracle, pool_weights, starts
from implicits_support import BOOTS

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import Reading, VaalOrb, catalog, model_readings
from crafting_system.actions.corruption import BRICK_AXIS
from crafting_system.cli._marking import approximate_inputs_of
from crafting_system.cli._offers import offers_for
from crafting_system.items import ImplicitMod, Item, Rarity, is_corrupted_implicit

QUARTER = Fraction(1, 4)
FILL = VaalOrb(brick_fills=True)
WIKI = Reading.of({BRICK_AXIS.name: "wiki"})
COE = Reading.of({BRICK_AXIS.name: "coe"})
GOAL = Goal((Wanted(RESISTS), Wanted(frozenset({LIFE_1, LIFE_2}))), allow_corrupted=True)
STARTS = starts()


def locked() -> Item:
    """A rare amulet whose suffixes are locked: the resistance (a suffix) stays, the life (a prefix) and the metamod (a prefix) go."""
    return amulet(_roll(RESIST_2), _roll(LIFE_1), _roll(CRAFTED, crafted=True))


def brick_start(item: Item, reading: str) -> Item:
    """What the brick keeps, written out by hand: a corrupted rare holding the fractured mods (wiki) or nothing (Craft of Exile)."""
    kept = tuple(entry for entry in item.mods if entry.fractured) if reading == "wiki" else ()
    return Item.build(
        DATA, base_id=item.base_id, item_level=item.item_level, rarity=Rarity.RARE, mods=kept, implicits=item.implicits, corrupted=True,
        influences=item.influences,
    )


def hand_items(item: Item, reading: str, full: int = 6, kept: Item | None = None) -> list[tuple[Item, Fraction]]:
    """Every finished item of the Orb by hand: the oracle's implicit and nothing ends, and the brick's quarter over its full fills."""
    listed = []
    jewel = item.base_id in (COBALT, PRISMATIC)
    unique = item.base_id == COBALT
    pool = pool_weights(item.item_level, JEWEL_POOL) if jewel else pool_weights(item.item_level)
    nothing = QUARTER if jewel and unique else (QUARTER if jewel else 2 * QUARTER)
    dead = QUARTER if unique else Fraction(0)  # the unique jewel stays a dead end; the brick is spread below
    ends = oracle([entry.mod_id for entry in item.implicits], pool, dead_chance=QUARTER + dead, nothing_chance=nothing)
    for end, chance in ends.items():
        if end == "nothing":
            listed.append((dataclasses.replace(item, corrupted=True), chance))
        elif end == "dead":
            if dead:  # the unique jewel: a corrupted rare with the fractured mods, as ticket #259 left it
                listed.append((item.changed(DATA, rarity=Rarity.RARE, corrupted=True, mods=item.fractured_mods), dead))
        else:
            held = {entry.mod_id: entry for entry in item.implicits}
            implicits = tuple(
                held.get(mod_id) or ImplicitMod(mod_id, 0, tuple(min(stat.min, stat.max) for stat in DATA.mods[mod_id].stats))
                for mod_id in sorted(end[1])
            )
            listed.append((dataclasses.replace(item, corrupted=True, implicits=implicits), chance))
    start = brick_start(item, reading) if kept is None else kept
    for result, chance in finished_items(DATA, start, totals={full: Fraction(1)}, keep_all=kept is not None):
        listed.append((result, QUARTER * chance))
    assert sum(chance for _, chance in listed) == 1
    return listed


def kernel(item: Item, reading: Reading, goal: Goal = GOAL):
    ab = Abstraction(DATA, goal, item.base_id, item.item_level, [FILL], reading=reading, metamods=bool(item.crafted_mods))
    return ab, ab.kernel(ab.compress(item), FILL)


# --- which Orb a target gets ------------------------------------------------------------------------------


def test_a_target_that_only_allows_gets_the_filling_brick_and_one_that_asks_keeps_the_dead_one():
    start = STARTS["none"]
    for goal, wanted in (
        (Goal((Wanted(RESISTS),), allow_corrupted=True), FILL),
        (Goal((Wanted(RESISTS),), asks_corrupted=True), VaalOrb()),
        (Goal((Wanted(RESISTS),), asks_corrupted=True, allow_corrupted=True), VaalOrb()),  # it asks: the brick can never be its goal
    ):
        found = [offer.action for offer in offers_for(DATA, goal, start.base_id, start).offers if offer.label == "Vaal Orb"]
        assert found == [wanted], goal
    assert VaalOrb() in catalog(DATA, start) and FILL not in catalog(DATA, start)  # the catalog lists the Orb of #259
    assert FILL.label(DATA) == VaalOrb().label(DATA) == "Vaal Orb"


def test_only_the_filling_brick_reads_the_axis_and_the_plan_is_the_wiki():
    assert VaalOrb().rule_axes(DATA) == ()  # a target that asks: the brick is a dead end at any reading
    assert FILL.rule_axes(DATA) == (BRICK_AXIS,)
    assert BRICK_AXIS.readings == ("wiki", "coe") and BRICK_AXIS.plan == "wiki"
    assert [reading[BRICK_AXIS.name] for reading in model_readings(DATA, [FILL])] == ["wiki", "coe"]
    item = STARTS["fractured"]
    assert finished(FILL.outcomes(DATA, item), DATA) == finished(FILL.outcomes(DATA, item, WIKI), DATA)  # no reading is the plan's


def test_the_filling_brick_declares_that_it_can_reach_the_goal_by_other_mods():
    adds = FILL.adds(DATA)
    assert adds.corrupts and adds.implicits and adds.draws and not adds.keeps_mods and not adds.asked_only
    assert adds.erases_fractured  # Craft of Exile's reading
    old = VaalOrb().adds(DATA)
    assert old.keeps_mods and not old.draws and not old.erases_fractured  # ticket #259's Orb is as it was
    assert FILL.reads(DATA) == VaalOrb().reads(DATA)
    assert FILL.claims(DATA) == VaalOrb().claims(DATA)
    assert FILL.strand_use(DATA) == VaalOrb().strand_use(DATA)


# --- Done when 1: the kernel equals the enumeration -----------------------------------------------------


KERNEL_STARTS = ["none", "fractured", "normal", "magic", "one", "belt-stored"]


@pytest.mark.parametrize("reading", ["wiki", "coe"])
@pytest.mark.parametrize("name", KERNEL_STARTS)
def test_the_kernel_equals_the_enumeration(name, reading):
    item = STARTS[name]
    ab, found = kernel(item, Reading.of({BRICK_AXIS.name: reading}))
    assert_same_distribution(found, compressed_distribution(hand_items(item, reading), ab.compress))
    assert all(state.flags.corrupted for state in found)  # a corrupted item is final


@pytest.mark.parametrize("name", KERNEL_STARTS)
def test_the_finished_items_are_the_enumeration(name):
    """The same at the level of concrete items: every full fill with its chance, the mods drawn at their lowest values."""
    item = STARTS[name]

    def key(result: Item):
        return (
            result.rarity, result.corrupted,
            tuple(sorted((entry.mod_id, entry.fractured, entry.crafted) for entry in result.mods)),
            tuple(sorted(entry.mod_id for entry in result.implicits)),
        )

    expected: dict = {}
    for result, chance in hand_items(item, "wiki"):
        expected[key(result)] = expected.get(key(result), Fraction(0)) + chance
    listed: dict = {}
    for chance, result in finished(FILL.outcomes(DATA, item), DATA):
        listed[key(result)] = listed.get(key(result), Fraction(0)) + chance
    assert listed == expected


def test_a_brick_is_a_full_item_with_three_mods_a_side():
    item = STARTS["none"]
    bricks = [result for _, result in finished(FILL.outcomes(DATA, item), DATA) if result.rarity is Rarity.RARE and len(result.mods) != len(item.mods)]
    assert bricks and all(len(result.mods) == 6 for result in bricks)
    assert all(result.corrupted and result.implicits == item.implicits for result in bricks)  # the brick touches no implicit


def test_a_locked_side_stays_and_its_open_slots_fill():
    """Wiki: the locked suffix stays and the item is filled to six around it (the open suffix slots too, as a Chaos Orb fills them)."""
    item = locked()
    kept = Item.build(DATA, base_id=item.base_id, item_level=item.item_level, rarity=Rarity.RARE, mods=(_roll(RESIST_2),), corrupted=True)
    ab, found = kernel(item, WIKI)
    assert_same_distribution(found, compressed_distribution(hand_items(item, "wiki", kept=kept), ab.compress))
    for _, result in finished(FILL.outcomes(DATA, item), DATA):
        if result.rarity is Rarity.RARE and len(result.mods) == 6:
            assert RESIST_2 in {entry.mod_id for entry in result.mods}


@pytest.mark.parametrize("base_id", [PRISMATIC, COBALT])
def test_a_jewel_brick_fills_to_four(base_id):
    """Two prefixes and two suffixes (`corruption.jewel_brick_fills_to_limit`); the fixture jewels have no explicit pool, so the fill ends empty."""
    item = on(base_id, rarity=Rarity.MAGIC)
    outcomes = FILL.outcomes(DATA, item)
    share, brick = outcomes.components[-1]
    assert share == QUARTER and dict(brick.totals) == {4: 1}
    assert brick.retained.rarity is Rarity.RARE and brick.retained.corrupted and not brick.retained.mods
    assert sum(chance for chance, _ in finished(outcomes, DATA)) == 1


def test_a_real_jewel_brick_fills_to_four():
    from abstraction_support import real_game_data

    data = real_game_data()
    base = next(base for base in data.base_items.values() if base.name == "Crimson Jewel")
    item = Item.build(data, base_id=base.id, item_level=84, rarity=Rarity.MAGIC)
    share, brick = FILL.outcomes(data, item).components[-1]
    assert share == QUARTER and dict(brick.totals) == {4: 1} and sum(brick.free.values()) == 4
    rng = random.Random(4)
    assert {len(brick.sample(rng).mods) for _ in range(50)} == {4}


# --- Done when 2: the two readings ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "differs"),
    [("none", False), ("normal", False), ("magic", False), ("one", False), ("fractured", True), ("locked", True)],
)
def test_the_readings_differ_only_on_a_fractured_or_locked_item(name, differs):
    item = locked() if name == "locked" else STARTS[name]
    by_reading = {}
    for label, reading in (("wiki", WIKI), ("coe", COE)):
        listed: dict = {}
        for chance, result in finished(FILL.outcomes(DATA, item, reading), DATA):
            listed[result] = listed.get(result, Fraction(0)) + chance
        by_reading[label] = listed
    assert (by_reading["wiki"] != by_reading["coe"]) is differs
    _, wiki = kernel(item, WIKI)
    _, coe = kernel(item, COE)
    assert (wiki != coe) is differs


def test_craft_of_exile_s_reading_removes_the_fractured_mod_and_the_wiki_keeps_it():
    item = STARTS["fractured"]
    fractured = item.fractured_mods[0].mod_id
    wiki = FILL.outcomes(DATA, item, WIKI)
    coe = FILL.outcomes(DATA, item, COE)
    for chance, result in finished(wiki, DATA):
        assert fractured in {entry.mod_id for entry in result.fractured_mods}
    bricks = [result for _, result in finished(coe, DATA) if not result.fractured_mods]
    assert bricks and all(len(result.mods) == 6 for result in bricks)
    assert wiki.chance_all([fractured]) == 1 and coe.chance_all([fractured]) < 1


# --- Done when 3: the approximate inputs --------------------------------------------------------------


def test_the_answer_lists_the_brick_claim_among_its_approximate_inputs():
    from types import SimpleNamespace

    class Plan:  # the part of a plan that the list of approximate inputs reads
        abstraction = SimpleNamespace(enchantment=None)
        target = SimpleNamespace(base_id=STARTS["none"].base_id)
        starts = None

        def offer_of(self, action):
            return SimpleNamespace(offer=SimpleNamespace(action=action))

    start = STARTS["none"]
    offered = next(offer.action for offer in offers_for(DATA, GOAL, start.base_id, start).offers if offer.label == "Vaal Orb")
    listed = {entry.claim: entry for entry in approximate_inputs_of(Plan(), [offered], DATA)}
    assert "corruption.vaal_brick_rare_six_mods" in listed
    assert "Craft of Exile" in listed["corruption.vaal_brick_rare_six_mods"].reason


# --- the rest: values, the contract ---------------------------------------------------------------------


def test_the_brick_s_chances_sum_with_the_rest_and_chance_all_is_the_enumeration():
    item = STARTS["fractured"]
    outcomes = FILL.outcomes(DATA, item)
    listed = finished(outcomes, DATA)
    assert sum(chance for chance, _ in listed) == 1
    for mod_id in (LIFE_1, MANA_1, *RESISTS):
        by_hand = sum((chance for result, chance in hand_items(item, "wiki") if mod_id in {entry.mod_id for entry in result.mods}), Fraction(0))
        assert outcomes.chance_all([mod_id]) == by_hand, mod_id
    corrupted = next(mod_id for mod_id in DATA.mods if is_corrupted_implicit(DATA.mods[mod_id]) and outcomes.chance_all([mod_id]))
    assert outcomes.chance_all([corrupted]) == VaalOrb().outcomes(DATA, item).chance_all([corrupted])  # the implicit quarter is untouched


def test_the_sampler_gives_full_bricks_with_rolled_values():
    item = STARTS["none"]
    outcomes = FILL.outcomes(DATA, item)
    rng = random.Random(260)
    full = 0
    for _ in range(2000):
        result = outcomes.sample(rng)
        result.validate(DATA)
        assert result.corrupted
        if len(result.mods) == 6:
            full += 1
    assert full / 2000 == pytest.approx(0.25, abs=0.04)


@pytest.mark.parametrize("name", ["none", "fractured", "normal", "magic", "two", "belt-replaced", "cobalt", "prismatic", "stranded"])
def test_the_contract_suite_passes_on_the_filling_brick(name):
    items = {
        **STARTS,
        "cobalt": on(COBALT, rarity=Rarity.MAGIC),
        "prismatic": on(PRISMATIC),
        "stranded": amulet(_roll(RESIST_2), _roll(LIFE_1), memory_strands=40),
    }
    assert check_action(FILL, items[name], DATA, GOAL)


def test_the_filling_brick_on_boots_and_a_belt_keeps_their_implicits():
    for item in (on(BOOTS, _roll(RESIST_2)), on(BELT, _roll(RESIST_2), implicits=STARTS["belt-stored"].implicits)):
        for _, result in finished(FILL.outcomes(DATA, item), DATA):
            if not any(is_corrupted_implicit(DATA.mods[entry.mod_id]) for entry in result.implicits):
                assert result.implicits == item.implicits


# --- the planner answers an allow-only target at the plan's reading -------------------------------------


def test_the_planner_answers_a_target_that_only_allows_corruption_at_the_wiki_reading():
    """The brick's axis is planned (OR-11): one exact answer at the wiki, not a refusal; a target that asks gets the dead brick as before."""
    import datetime

    from targets_corrupted_support import DATA as RING_DATA
    from targets_corrupted_support import parse

    from crafting_system.cli import make_plan
    from crafting_system.prices import PriceEntry, PriceFile

    assert BRICK_AXIS.planned
    prices = PriceFile("Test", datetime.datetime(2026, 11, 12, tzinfo=datetime.UTC), 300.0, {"Vaal Orb": PriceEntry(1.0, "test")})
    # a bought normal ring: the pool's only explicit mod is the cold resistance, so a brick holds it (the fill ends when the pool is empty), a
    # quarter of the uses; any other outcome buys the ring again. Each try costs the orb and a ring: V = 4 * (1 + 2) - 2 = 10 from the ring in hand
    plan = make_plan(RING_DATA, parse("allow_corrupted: true\nactions: [vaal]\n", start="bought"), prices, start_price=2.0)
    offered = [priced.offer.action for priced in plan.offers if priced.label == "Vaal Orb"]
    assert offered == [FILL]
    assert plan.abstraction.reading is None  # the plan's reading: the wiki
    assert plan.solution.values[plan.start] == pytest.approx(10.0)
    asking = parse("implicits:\n  - stat: '+#% to all Elemental Resistances'\n    corrupted: true\nactions: [vaal]\n", start="bought")
    found = offers_for(RING_DATA, Goal.from_target(asking), asking.base_id, asking.start_item, asking.actions).offers
    assert [offer.action for offer in found if offer.label == "Vaal Orb"] == [VaalOrb()]  # the planner refuses it today (implicits), the filter keeps the dead brick
