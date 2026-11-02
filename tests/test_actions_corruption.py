"""The Vaal Orb as an exact action (ticket #259, ADR-0037), against the hand oracle of `corruption_support.py` and on the real 3.29.3.3 export.

"Done when" of the ticket, and where each line is tested:

1. *The contract suite passes.* `test_actions_contract.py` asks the kind about the items of `contract_fixtures_corruption.py` (an amulet, a
   fractured one, a normal and a magic item, boots and a belt with Eldritch and base implicits, two jewels, a stranded and a corrupted item) and runs every
   check of `contract_support.check_action`, the kernel against the brute force and the declarations included. Here only `test_the_contract_suite_runs_on_the_kind`
   says that it does.
2. *`chance_all` equals brute-force enumeration over concrete items in exact fractions (every pool implicit, every replaced implicit).*
   `test_the_finished_items_are_the_hand_oracle_s` lists every finished item with its chance and compares them, end by end, with `corruption_support.oracle`
   for every start (no implicit, one, two, a base implicit stored or not, a normal and a magic item, a fractured one); `test_chance_all_of_every_pool_implicit_is_a_quarter_of_its_share`
   and `test_the_chance_of_the_implicits_that_stay_is_the_hand_chance` give the two chances in fractions, and `test_the_kernel_equals_the_hand_items` the kernel.
3. *The ring all-resistances case gives 1000/31,850/4.* `test_the_ring_all_resistances_case_on_the_real_export`.
4. *A brick merges into one dead state (enumeration on fixtures).* `test_a_brick_merges_into_one_dead_state`.

The rest: the refusals, the jewels, the sampler, the declarations and the strands.
"""

import dataclasses
import random
from collections import Counter
from fractions import Fraction

import pytest
from abstraction_oracle import assert_same_distribution, compressed_distribution
from abstraction_pool import LIFE_1, LIFE_2, RESIST_2, RESISTS
from abstraction_support import real_game_data
from contract_support import CONTRACT_DATA, _roll, check_action
from corruption_support import (
    ABYSS,
    ABYSS_A,
    ABYSS_POOL,
    ALL_RES,
    COBALT,
    CRIMSON,
    DATA,
    EATER,
    EXARCH,
    FLASK,
    JEWEL_A,
    JEWEL_LATE,
    JEWEL_POOL,
    JEWELS,
    LATE,
    LEVEL,
    PRISMATIC,
    SECOND,
    VIRIDIAN,
    amulet,
    on,
    oracle,
    pool_weights,
    starts,
)

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import (
    Action,
    NotApplicableError,
    OutOfScopeError,
    VaalOrb,
    catalog,
    kinds,
)
from crafting_system.actions.corruption import VaalOutcomes, dead_end
from crafting_system.cli._offers import offers_for
from crafting_system.items import ImplicitMod, Item, Rarity, UnknownBaseError, is_corrupted_implicit, spawn_weight

QUARTER = Fraction(1, 4)
STARTS = starts()


def nothing_of(item: Item) -> Item:
    """The item only corrupted, written out by hand."""
    return dataclasses.replace(item, corrupted=True)


def dead_of(item: Item) -> Item:
    """What a brick leaves for the plan, written out by hand: a corrupted rare with the fractured mods only."""
    return Item.build(
        DATA,
        base_id=item.base_id,
        item_level=item.item_level,
        rarity=Rarity.RARE,
        mods=tuple(entry for entry in item.mods if entry.fractured),
        implicits=item.implicits,
        corrupted=True,
        influences=item.influences,
    )


def unstored_of(item: Item) -> list[str]:
    stored = {entry.mod_id for entry in item.implicits}
    return [mod_id for mod_id in DATA.base_items[item.base_id].implicits if mod_id not in stored]


def ends_of(item: Item, outcomes: VaalOutcomes) -> dict:
    """The finished items of the Orb, by kind of end: the implicits an item holds, nothing, or the dead end."""
    nothing, dead = nothing_of(item), dead_of(item)
    assert nothing != dead  # a rare with no mod but the fractured ones would be both
    ends: dict = {}
    for chance, result in outcomes.results:
        assert result.corrupted
        if result == nothing:
            key = "nothing"
        elif result == dead:
            key = "dead"
        else:
            assert any(is_corrupted_implicit(DATA.mods[entry.mod_id]) for entry in result.implicits)
            assert result.mods == item.mods and result.rarity is item.rarity  # the implicit outcome touches no explicit mod
            key = ("implicit", frozenset(entry.mod_id for entry in result.implicits))
        ends[key] = ends.get(key, Fraction(0)) + chance
    return ends


def hand_ends(item: Item, level: int | None = None) -> dict:
    return oracle(
        [entry.mod_id for entry in item.implicits],
        unstored_of(item),
        pool_weights(item.item_level if level is None else level),
        dead_chance=QUARTER,
        nothing_chance=2 * QUARTER,
    )


# --- Done when 2: chance_all and the finished items are the hand oracle's --------------------------------------


@pytest.mark.parametrize("name", STARTS)
def test_the_finished_items_are_the_hand_oracle_s(name):
    item = STARTS[name]
    outcomes = VaalOrb().outcomes(DATA, item)
    assert ends_of(item, outcomes) == hand_ends(item)
    assert sum(chance for chance, _ in outcomes.results) == 1


@pytest.mark.parametrize("name", STARTS)
def test_chance_all_of_every_pool_implicit_is_a_quarter_of_its_share(name):
    item = STARTS[name]
    outcomes = VaalOrb().outcomes(DATA, item)
    whole = sum(pool_weights().values())
    for mod_id, weight in pool_weights().items():
        assert outcomes.chance_all([mod_id]) == QUARTER * Fraction(weight, whole)  # whatever implicit it replaces: the draw happens in any case
        assert outcomes.chance_all([mod_id]) == sum(
            (chance for end, chance in hand_ends(item).items() if isinstance(end, tuple) and mod_id in end[1]), Fraction(0)
        )
    assert outcomes.chance_all([LATE]) == QUARTER * Fraction(200, 1950)
    assert outcomes.chance_all([ALL_RES, SECOND]) == 0  # one corrupted implicit only
    assert outcomes.chance_all([]) == 1
    with pytest.raises(ValueError, match="not in the game data"):
        outcomes.chance_all(["NoSuchMod"])


@pytest.mark.parametrize("name", STARTS)
def test_the_chance_of_the_implicits_that_stay_is_the_hand_chance(name):
    item = STARTS[name]
    outcomes = VaalOrb().outcomes(DATA, item)
    ends = hand_ends(item)
    kept = [entry.mod_id for entry in item.implicits]
    for mod_id in kept:
        by_hand = sum((chance for end, chance in ends.items() if end in ("nothing", "dead") or mod_id in end[1]), Fraction(0))
        assert outcomes.implicit_chances([mod_id]) == by_hand
        # an implicit stays through the three outcomes that do not replace it and, in the implicit one, when another is the one that goes
        candidates = len(kept) + len(unstored_of(item))
        assert by_hand == Fraction(3, 4) + QUARTER * Fraction(candidates - 1, candidates)
    for mod_id in unstored_of(item):  # the base's own implicit that the item does not store is on no finished item (the fixture amulet's is not even a mod of the data)
        if mod_id in DATA.mods:
            assert outcomes.implicit_chances([mod_id]) == 0
    assert outcomes.implicit_chances(kept) == sum((c for e, c in ends.items() if e in ("nothing", "dead") or set(kept) <= e[1]), Fraction(0))


def test_the_item_level_gates_the_pool_and_the_chances_follow():
    item = amulet(_roll(RESIST_2), _roll(LIFE_1), item_level=60)
    outcomes = VaalOrb().outcomes(DATA, item)
    assert outcomes.chance_all([LATE]) == 0  # required level 75
    assert outcomes.chance_all([ALL_RES]) == QUARTER * Fraction(1000, 1750)
    assert ends_of(item, outcomes) == hand_ends(item)
    high = VaalOrb().outcomes(DATA, amulet(item_level=75))
    assert high.chance_all([LATE]) == QUARTER * Fraction(200, 1950)


def test_the_kernel_equals_the_hand_items():
    goal = Goal((Wanted(RESISTS), Wanted(frozenset({LIFE_1, LIFE_2}))), asks_corrupted=True)
    for name, item in STARTS.items():
        ab = Abstraction(DATA, goal, item.base_id, item.item_level, [VaalOrb()])
        listed = []
        for end, chance in hand_ends(item).items():
            if end == "nothing":
                built = nothing_of(item)
            elif end == "dead":
                built = dead_of(item)
            else:
                held = {entry.mod_id: entry for entry in item.implicits}
                implicits = tuple(
                    held.get(mod_id) or ImplicitMod(mod_id, 0, tuple(min(stat.min, stat.max) for stat in DATA.mods[mod_id].stats))
                    for mod_id in sorted(end[1])
                )
                built = dataclasses.replace(item, corrupted=True, implicits=implicits)
            listed.append((built, chance))
        assert_same_distribution(ab.kernel(ab.compress(item), VaalOrb()), compressed_distribution(listed, ab.compress)), name


# --- Done when 3: the ring ------------------------------------------------------------------------------


def test_the_ring_all_resistances_case_on_the_real_export():
    data = real_game_data()
    ring = next(base for base in data.base_items.values() if base.item_class == "Ring" and not base.implicits)
    item = Item.build(data, base_id=ring.id, item_level=84, rarity=Rarity.RARE)
    outcomes = VaalOrb().outcomes(data, item)
    all_resistances = "V2AllResistancesCorrupted"

    assert outcomes.chance_all([all_resistances]) == Fraction(1000, 31850) / 4  # 0.785% per orb, 127.4 orbs for one hit
    assert float(outcomes.chance_all([all_resistances])) == pytest.approx(0.00785, abs=1e-5)
    assert 1 / float(outcomes.chance_all([all_resistances])) == pytest.approx(127.4, abs=0.01)
    pool = [entry for entry in data.mods.values() if is_corrupted_implicit(entry) and entry.domain == "item" and outcomes.chance_all([entry.id])]
    assert len(pool) == 39 and sum(outcomes.chance_all([entry.id]) for entry in pool) == QUARTER  # one corrupted implicit in a quarter of the uses
    assert sum(chance for chance, _ in outcomes.results) == 1


@pytest.mark.parametrize(
    ("item_class", "mods", "weight"), [("Ring", 39, 31850), ("Amulet", 30, 28500), ("Belt", 19, 18500)]
)
def test_the_real_pool_of_a_class_gives_each_mod_its_share_of_a_quarter(item_class, mods, weight):
    data = real_game_data()
    base = next(base for base in data.base_items.values() if base.item_class == item_class and base.release_state == "released")
    outcomes = VaalOrb().outcomes(data, Item.build(data, base_id=base.id, item_level=100, rarity=Rarity.RARE))
    drawn = Counter()
    for chance, result in outcomes.results:
        for entry in result.implicits:
            if is_corrupted_implicit(data.mods[entry.mod_id]):
                drawn[entry.mod_id] += chance
    assert len(drawn) == mods
    assert sum(drawn.values()) == QUARTER
    for mod_id, chance in drawn.items():
        assert chance * 4 * weight == spawn_weight(data.mods[mod_id], base.tags)  # the weight of the first spawn tag the base matches


# --- Done when 4: the brick ------------------------------------------------------------------------------


def test_a_brick_merges_into_one_dead_state():
    """Whatever the item held, the brick is one corrupted rare with the fractured mods: one state, never the goal of a target that asks."""
    goal = Goal((Wanted(RESISTS), Wanted(frozenset({LIFE_1, LIFE_2}))), asks_corrupted=True)
    dead_states = {}
    for name in ("none", "magic", "normal"):  # items that hold different junk (and a different rarity) and no fractured mod
        item = STARTS[name]
        ab = Abstraction(DATA, goal, item.base_id, item.item_level, [VaalOrb()])
        kernel = ab.kernel(ab.compress(item), VaalOrb())
        dead = ab.compress(dead_of(item))
        assert kernel[dead] == QUARTER  # the brick lands in the state the dead item compresses to, and nowhere else
        assert not ab.is_goal(dead)
        dead_states[name] = dead
        corrupted = [state for state in kernel if state.flags.corrupted]
        assert corrupted == list(kernel)  # a corrupted item is final: no continuing state
    assert len(set(dead_states.values())) == 1  # the same state for any item that held no fractured mod

    fractured = STARTS["fractured"]
    ab = Abstraction(DATA, goal, fractured.base_id, fractured.item_level, [VaalOrb()])
    assert ab.compress(dead_of(fractured)) != dead_states["none"]  # the fractured mod stays, as the contract requires
    assert ab.kernel(ab.compress(fractured), VaalOrb())[ab.compress(dead_of(fractured))] == QUARTER


def test_the_brick_keeps_what_it_does_not_touch():
    item = amulet(_roll(RESIST_2, fractured=True), _roll(LIFE_1), memory_strands=12, implicits=(), influences=frozenset())
    brick = dead_end(DATA, item)
    assert [entry.mod_id for entry in brick.mods] == [RESIST_2] and brick.mods[0].fractured
    assert (brick.rarity, brick.corrupted, brick.memory_strands, brick.sockets) == (Rarity.RARE, True, 12, None)
    with_implicits = on(STARTS["belt-stored"].base_id, implicits=STARTS["belt-stored"].implicits)
    assert dead_end(DATA, with_implicits).implicits == with_implicits.implicits  # the brick adds no corrupted implicit and touches none


# --- the refusals ----------------------------------------------------------------------------------------


def test_a_corrupted_item_takes_no_vaal_orb():
    with pytest.raises(NotApplicableError, match="corrupted"):
        VaalOrb().outcomes(DATA, STARTS["none"].changed(DATA, corrupted=True))


def test_a_base_whose_class_has_no_pool_is_refused_and_not_listed():
    flask = Item.build(DATA, base_id=FLASK, item_level=LEVEL, rarity=Rarity.NORMAL)
    with pytest.raises(NotApplicableError, match="no corrupted implicit pool"):
        VaalOrb().outcomes(DATA, flask)
    assert VaalOrb() not in catalog(DATA, flask)


def test_an_unknown_base_is_refused_by_the_item_model_before_the_orb_sees_it():
    ghost = Item(base_id="No/Such/Base", item_level=LEVEL, rarity=Rarity.RARE)
    with pytest.raises(UnknownBaseError):
        VaalOrb().outcomes(DATA, ghost)
    assert [action for entry in kinds() if entry.name == "vaal" for action in entry.members(DATA, ghost)] == []


def test_an_empty_pool_at_the_item_level_is_out_of_scope():
    data = dataclasses.replace(DATA, mods={**DATA.mods, ABYSS_A: dataclasses.replace(DATA.mods[ABYSS_A], required_level=50)})
    item = Item.build(data, base_id=ABYSS, item_level=30, rarity=Rarity.RARE)
    with pytest.raises(OutOfScopeError, match="empty at item level 30"):
        VaalOrb().outcomes(data, item)


def test_cluster_and_timeless_jewels_are_out_of_scope():
    data = real_game_data()
    timeless = next(base for base in data.base_items.values() if base.name == "Timeless Jewel")
    cluster = next(base for base in data.base_items.values() if base.domain == "affliction_jewel")
    for base in (timeless, cluster):
        item = Item.build(data, base_id=base.id, item_level=84, rarity=Rarity.RARE)
        with pytest.raises(OutOfScopeError, match="not checked"):
            VaalOrb().outcomes(data, item)
        assert VaalOrb() not in catalog(data, item)


@pytest.mark.parametrize("name", ["none", "normal", "magic", "fractured", "one", "belt-stored"])
def test_the_orb_takes_normal_magic_and_rare_items_and_is_listed_for_them(name):
    assert VaalOrb() in catalog(DATA, STARTS[name])
    VaalOrb().outcomes(DATA, STARTS[name])


def test_a_corrupted_item_is_not_listed_and_the_listing_names_the_kind_once():
    assert VaalOrb() not in catalog(DATA, STARTS["none"].changed(DATA, corrupted=True))
    assert sum(1 for action in catalog(DATA, STARTS["none"]) if isinstance(action, VaalOrb)) == 1
    assert [entry for entry in kinds() if entry.name == "vaal"][0].corrupting


# --- the jewels ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("base_id", "unique"), [(COBALT, True), (CRIMSON, True), (VIRIDIAN, True), (PRISMATIC, False)])
def test_a_jewel_has_four_equal_outcomes_and_its_unique_is_a_dead_end_on_three_bases(base_id, unique):
    item = on(base_id, rarity=Rarity.MAGIC)  # a magic jewel: the brick (a rare) differs from "nothing" even with no mod on it
    outcomes = VaalOrb().outcomes(DATA, item)
    ends = ends_of(item, outcomes)
    pool = pool_weights(LEVEL, JEWEL_POOL)
    assert ends == oracle(
        [], [], pool, dead_chance=2 * QUARTER if unique else QUARTER, nothing_chance=QUARTER if unique else 2 * QUARTER
    )
    assert sum(chance for end, chance in ends.items() if isinstance(end, tuple)) == QUARTER
    assert outcomes.chance_all([JEWEL_A]) == QUARTER * Fraction(1000, sum(pool.values()))


def test_a_jewel_draws_from_the_pool_of_its_domain_and_level():
    low = VaalOrb().outcomes(DATA, on(COBALT, item_level=39))
    assert low.chance_all([JEWEL_LATE]) == 0 and low.chance_all([JEWEL_A]) == QUARTER  # required level 40
    abyss = VaalOrb().outcomes(DATA, on(ABYSS))
    assert abyss.chance_all([ABYSS_A]) == QUARTER and abyss.chance_all([JEWEL_A]) == 0  # an abyss jewel does not get the ordinary jewel mods
    assert ends_of(on(ABYSS, rarity=Rarity.MAGIC), VaalOrb().outcomes(DATA, on(ABYSS, rarity=Rarity.MAGIC))) == oracle([], [], pool_weights(LEVEL, ABYSS_POOL), dead_chance=QUARTER, nothing_chance=2 * QUARTER)
    ring_like = VaalOrb().outcomes(DATA, STARTS["none"])
    assert ring_like.chance_all([JEWEL_A]) == 0 and ring_like.chance_all([ABYSS_A]) == 0  # nor does an amulet


def test_a_real_jewel_of_the_three_bases_has_a_unique_and_the_others_do_not():
    data = real_game_data()
    chances = {}
    for base in data.base_items.values():
        if base.item_class in ("Jewel", "AbyssJewel") and base.name != "Timeless Jewel" and base.domain in ("misc", "abyss_jewel"):
            item = Item.build(data, base_id=base.id, item_level=84, rarity=Rarity.MAGIC)
            ends = ends_of_data(data, item, VaalOrb().outcomes(data, item))
            chances[base.name] = ends["dead"]
    assert {name for name, chance in chances.items() if chance == 2 * QUARTER} == {"Cobalt Jewel", "Crimson Jewel", "Viridian Jewel"}
    assert {chance for name, chance in chances.items() if name not in JEWELS} == {QUARTER}
    assert chances["Prismatic Jewel"] == QUARTER


def ends_of_data(data, item, outcomes) -> dict:
    nothing = dataclasses.replace(item, corrupted=True)
    dead = item.changed(data, rarity=Rarity.RARE, corrupted=True, mods=item.fractured_mods)
    ends = {"dead": Fraction(0), "nothing": Fraction(0)}
    for chance, result in outcomes.results:
        key = "nothing" if result == nothing else "dead" if result == dead else "implicit"
        ends[key] = ends.get(key, Fraction(0)) + chance
    return ends


# --- the sampler -----------------------------------------------------------------------------------------


def test_the_sampler_rolls_each_stat_of_the_drawn_implicit_uniformly_and_independently():
    outcomes = VaalOrb().outcomes(DATA, STARTS["none"])
    rng = random.Random(259)
    pairs = Counter()
    for _ in range(6000):
        finished = outcomes.sample(rng)
        finished.validate(DATA)
        drawn = [entry for entry in finished.implicits if entry.mod_id == SECOND]
        if drawn:
            pairs[drawn[0].values] += 1
    assert set(pairs) == {(a, b) for a in range(3, 6) for b in range(8, 10)}  # both stats cover their whole integer range, and every pair shows
    total = sum(pairs.values())
    for count in pairs.values():
        assert count / total == pytest.approx(1 / 6, abs=0.04)


def test_the_sampler_replaces_one_implicit_at_random_and_keeps_the_explicit_mods():
    item = STARTS["two"]
    outcomes = VaalOrb().outcomes(DATA, item)
    rng = random.Random(7)
    seen = Counter()
    for _ in range(4000):
        finished = outcomes.sample(rng)
        assert finished.corrupted
        ids = frozenset(entry.mod_id for entry in finished.implicits)
        if any(is_corrupted_implicit(DATA.mods[mod_id]) for mod_id in ids):
            assert finished.mods == item.mods and len(ids) == 2  # one of the two is replaced
            seen[tuple(sorted(ids & {EXARCH, EATER}))] += 1
    assert seen[(EATER,)] > 0 and seen[(EXARCH,)] > 0  # either goes
    assert seen[(EATER,)] / sum(seen.values()) == pytest.approx(0.5, abs=0.05)


# --- the declarations ------------------------------------------------------------------------------------


def test_the_orb_declares_that_it_corrupts_and_keeps_the_mods_and_is_offered_to_a_target_that_takes_corruption():
    adds, reads = VaalOrb().adds(DATA), VaalOrb().reads(DATA)
    assert adds.corrupts and adds.keeps_mods and adds.implicits and not adds.asked_only  # a target that only allows corruption gets it too
    assert reads.implicits and reads.junk and not reads.quality and not reads.offer
    assert dict(VaalOrb().resources(DATA)) == {"Vaal Orb": 1}
    assert VaalOrb().label(DATA) == "Vaal Orb"
    start = STARTS["none"]
    for goal, offered in (
        (Goal((Wanted(RESISTS),), asks_corrupted=True), True),
        (Goal((Wanted(RESISTS),), allow_corrupted=True), True),
        (Goal((Wanted(RESISTS),)), False),  # an item never arrives corrupted unasked
    ):
        labels = [offer.label for offer in offers_for(DATA, goal, start.base_id, start).offers]
        assert ("Vaal Orb" in labels) is offered, goal


def test_the_claims_are_the_orb_s_and_not_the_resonator_s():
    claims = VaalOrb().claims(DATA)
    assert {
        "corruption.vaal_equipment_four_outcomes",
        "corruption.implicit_replaces_existing",
        "corruption.implicit_pool_by_item_class",
        "corruption.jewel_vaal_outcomes",
        "vaal_orb.cost",
        "eldritch.vaal_replaces_one_implicit",
        "corruption.vaal_brick_rare_six_mods",  # approximate
    } <= claims
    assert not claims & {"corruption.bloodstained_fossil_implicit", "corruption.bloodstained_never_fails", "fossils.bloodstained_gilded_replaces_all_implicits"}


def test_the_orb_neither_cuts_nor_spends_strands_and_the_brick_keeps_the_count():
    use = VaalOrb().strand_use(DATA)
    assert not use.cuts and use.spend is None
    item = amulet(_roll(RESIST_2), _roll(LIFE_1), memory_strands=40)
    outcomes = VaalOrb().outcomes(DATA, item)
    assert {result.memory_strands for _, result in outcomes.results} == {40}
    assert VaalOrb().outcomes(DATA, amulet(_roll(RESIST_2), _roll(LIFE_1))).results[0][0] == VaalOrb().outcomes(DATA, item).results[0][0]  # the same chances


def test_the_contract_suite_runs_on_the_kind():
    """`test_actions_contract.py` finds the kind by the catalog; here the checks run on the amulet world directly as well."""
    for name in ("none", "fractured", "normal", "belt-unstored"):
        assert check_action(VaalOrb(), STARTS[name], DATA)
    assert not check_action(VaalOrb(), STARTS["none"].changed(DATA, corrupted=True), DATA)  # refused, and the kernel refuses it too


def test_the_orb_is_not_an_action_of_the_contract_data_amulet():
    amulet_item = Item.build(CONTRACT_DATA, base_id=STARTS["none"].base_id, item_level=LEVEL, rarity=Rarity.RARE)
    assert VaalOrb() not in catalog(CONTRACT_DATA, amulet_item)  # no corrupted mod spawns on it: `applies_only_to`
    assert isinstance(VaalOrb(), Action)
