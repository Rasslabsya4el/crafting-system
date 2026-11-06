"""The Chromatic Orb, the Omen of Trichromatism and the bench's colour crafts (ticket #229, B6 S3; ADR-0047).

"Done when", test by test:

* the model lies inside the 95% interval in each of the eight aggregated cells of Siveran's data
  (`test_the_model_lies_inside_the_95_percent_interval_of_each_siveran_cell`; the cells are a fixture of counts in `sockets_colour_support.py`, not the CSV);
* a one-socket item is always coloured (`test_a_one_socket_item_is_always_coloured`);
* the result never equals the current colours and the kernel sums to 1 (`test_the_result_never_equals_the_current_colours_and_the_kernel_sums_to_one`);
* on a four-socket dexterity-intelligence helmet of item level 84 at 20% quality red, green and blue together come with 1.28% (about 78 orbs) and with the Omen
  with certainty (`test_the_helmet_gets_red_green_and_blue_with_one_in_78_orbs_and_with_the_omen_for_certain`);
* the Omen is not offered below three sockets (`test_the_omen_is_not_offered_below_three_sockets`);
* the contract suite passes for each action on the colour fixtures (`test_each_colour_action_meets_the_contract_on_every_colour_fixture`; the shared suite asks
  them too, through `contract_fixtures_sockets_colour.py`) and the claim marks are those of ADR-0047 (`test_the_claims_of_each_colour_action_carry_the_marks_of_adr_0047`).

The Whetstone and the Scrap are in `test_actions_quality_currency.py`.
"""

import dataclasses
import math
from collections import defaultdict
from fractions import Fraction

import pytest
from abstraction_pool import LIFE_1, RESIST_2
from contract_support import check_action, extra_fixture_items
from items_support import AMULET, BODY
from sockets_colour_support import (
    BENCH_COLOUR_COSTS,
    CHI_SQUARED_95,
    SIVERAN_CELLS,
    best_log_likelihood,
    chance_of,
    colour_data,
    log_likelihood,
    nonwhite_count_chances,
)
from sockets_support import HELMET, SWORD, B, G, R, W, abyss_data, socketed, sockets_of, white, ABYSS_MOD

from crafting_system.actions import (
    CHROMATIC_FORCED_COLOUR,
    BenchSocketColours,
    ChromaticOrb,
    NotApplicableError,
    OutOfScopeError,
    Reading,
    catalog,
    colour_weights,
    kinds,
    model_readings,
    nonwhite_chance,
    roll_colours,
)
from crafting_system.items import ExplicitMod, Item, PlainQuality, Rarity, SocketColour
from crafting_system.prices.price_names import CHROMATIC_ORB, OMEN_OF_TRICHROMATISM
from crafting_system.rules import load_registry, rule_by_id

DATA = colour_data()
COLOUR_KINDS = ("chromatic-orb", "bench-socket-colours")
SECOND = Reading.of({"chromatic_forced_colour": "flatter_second_reading"})
EXTRA = extra_fixture_items()
COLOUR_ITEMS = sorted(name for name in EXTRA if name.startswith("colours_"))


def chromatic(item, *, omen=False, reading=None):
    return ChromaticOrb(omen=omen).outcomes_under(DATA, item, reading)


def non_white(colours) -> int:
    return sum(colour is not SocketColour.WHITE for colour in colours)


def six_white(item_level, quality, requirements):
    """Six white sockets on a body armour whose base asks `requirements` (strength, dexterity, intelligence), at the plain quality (the cap of 30 applies to the item)."""
    base = dataclasses.replace(DATA.base_items[BODY], id="Metadata/Items/Armours/BodyArmours/CellBody", attribute_requirements=requirements)
    data = dataclasses.replace(DATA, base_items={**DATA.base_items, base.id: base})
    held = PlainQuality(min(quality, 30)) if quality else None
    return data, Item.build(data, base_id=base.id, item_level=item_level, rarity=Rarity.RARE, mods=(), sockets=white(6), quality=held)


# --- the roll against Siveran's data ----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("cell", SIVERAN_CELLS, ids=lambda cell: f"ilvl{cell[0]}-q{cell[1]}")
def test_the_model_lies_inside_the_95_percent_interval_of_each_siveran_cell(cell):
    """The count of non-white sockets of the action's own kernel against the cell's rows: 2 (log-likelihood at the best p - at the model's p) < 3.841."""
    item_level, quality, requirements, rows, histogram = cell
    assert sum(histogram.values()) == rows
    data, item = six_white(item_level, quality, requirements)
    model: dict[int, float] = defaultdict(float)
    for sockets, chance in ChromaticOrb().outcomes(data, item).by_sockets.items():
        model[non_white(sockets.colours)] += float(chance)
    p = float(nonwhite_chance(item_level, quality))
    for k, chance in nonwhite_count_chances(6, p).items():  # the kernel is the roll-then-force law of the formula's p
        assert model[k] == pytest.approx(chance, abs=1e-12)
    deviance = 2 * (best_log_likelihood(histogram) - log_likelihood(histogram, model))
    assert -1e-9 <= deviance <= CHI_SQUARED_95, f"the cell lies outside the 95% interval (deviance {deviance:.2f})"


def test_the_nonwhite_chance_is_siverans_formula_and_the_quality_cap_binds_at_30():
    assert nonwhite_chance(84, 20) == Fraction(315, 1000)  # 0.00375 * 70 * 1.2
    assert nonwhite_chance(1, 0) == nonwhite_chance(15, 0) == Fraction(375, 100_000)  # max(item level - 14, 1)
    assert nonwhite_chance(100, 30) == nonwhite_chance(100, 60) == Fraction(375, 100_000) * 86 * Fraction(13, 10)
    assert nonwhite_chance(100, 0) < nonwhite_chance(100, 20) < nonwhite_chance(100, 30)


@pytest.mark.parametrize(
    "requirements,expected",
    [
        ((145, 0, 0), (Fraction(9, 10) * Fraction(155, 165), Fraction(1, 20) + Fraction(9, 10) * Fraction(5, 165), Fraction(1, 20) + Fraction(9, 10) * Fraction(5, 165))),
        ((0, 0, 160), (Fraction(1, 20) + Fraction(9, 10) * Fraction(5, 180), Fraction(1, 20) + Fraction(9, 10) * Fraction(5, 180), Fraction(9, 10) * Fraction(170, 180))),
        ((53, 0, 53), (Fraction(9, 20), Fraction(1, 10), Fraction(9, 20))),
        ((139, 65, 0), (Fraction(9, 10) * Fraction(139, 204), Fraction(9, 10) * Fraction(65, 204), Fraction(1, 10))),
        ((1, 2, 3), (Fraction(1, 6), Fraction(1, 3), Fraction(1, 2))),
    ],
)
def test_the_colour_weights_follow_the_requirements(requirements, expected):
    assert colour_weights(requirements) == expected and sum(expected) == 1
    assert [round(float(weight), 3) for weight in colour_weights((145, 0, 0))] == [0.845, 0.077, 0.077]  # the research: red share 0.815 and 0.841 observed
    assert round(float(colour_weights((0, 0, 160))[2]), 3) == 0.850


def test_a_base_that_asks_for_no_attribute_has_no_weights():
    with pytest.raises(ValueError, match="at least one attribute"):
        colour_weights((0, 0, 0))
    data, item = six_white(84, 20, (0, 0, 0))
    with pytest.raises(OutOfScopeError, match="no attribute"):
        ChromaticOrb().outcomes(data, item)


# --- the rules of the Chromatic Orb -----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("start", [W, R, G, B])
def test_a_one_socket_item_is_always_coloured(start):
    outcome = chromatic(socketed(sockets_of(start), item_level=2, quality=0))  # at item level 2 a socket rolls non-white with 0.4%: the forced rule decides
    assert not any(colours == (W,) for colours in (sockets.colours for sockets in outcome.by_sockets))
    assert all(non_white(sockets.colours) == 1 for sockets in outcome.by_sockets) and (start,) not in {s.colours for s in outcome.by_sockets}
    weights = dict(zip((R, G, B), colour_weights((0, 0, 17)), strict=True))  # the body armour of the contract data asks 17 intelligence
    rest = 1 - weights.get(start, 0)
    for colour in (R, G, B):
        if colour is not start:
            assert chance_of(outcome, (colour,)) == weights[colour] / rest  # the roll conditioned on differing from the current colour


def test_a_white_one_socket_item_takes_the_natural_weights():
    outcome = chromatic(socketed(white(1)))
    assert [chance_of(outcome, (colour,)) for colour in (R, G, B)] == list(colour_weights((0, 0, 17)))


@pytest.mark.parametrize(
    "colours",
    [(W,) * 6, (R, G, B), (W, W, W), (R, R, W, W), (G, W), (R,), (B, B, B, B, B, B), (W, R, W, G, W, B)],
    ids=lambda colours: "".join(c.value for c in colours),
)
def test_the_result_never_equals_the_current_colours_and_the_kernel_sums_to_one(colours):
    item = socketed(sockets_of(*colours))
    outcome = chromatic(item)
    assert sum(outcome.by_sockets.values()) == 1 and sum(chance for chance, _ in outcome.results) == 1
    assert all(sockets.colours != colours for sockets in outcome.by_sockets)
    assert all(result.sockets.links == item.sockets.links and result.sockets.count == item.sockets.count for _, result in outcome.results)
    assert all(non_white(sockets.colours) >= 1 for sockets in outcome.by_sockets)  # the forced rule: never all white


def test_the_exclusion_is_the_roll_conditioned_on_differing_from_the_current_colours():
    white_start = chromatic(socketed(white(3)))
    for current in ((R, W, W), (G, B, W)):
        outcome = chromatic(socketed(sockets_of(*current)))
        base_chance = chance_of(white_start, current)
        for sockets in white_start.by_sockets:
            if sockets.colours != current:
                assert chance_of(outcome, sockets.colours) == chance_of(white_start, sockets.colours) / (1 - base_chance)
        assert chance_of(outcome, current) == 0


def test_the_roll_follows_the_formula_independently_per_socket_and_forces_the_first_socket_only_when_all_are_white():
    p = nonwhite_chance(84, 20)
    weights = colour_weights((0, 0, 17))
    outcome = chromatic(socketed(white(3)))
    # one coloured socket anywhere in the list: its colour times p times (1 - p)^2, plus (for the first socket) the forced chance
    for colour, weight in zip((R, G, B), weights, strict=True):
        assert chance_of(outcome, (colour, W, W)) == (p * (1 - p) ** 2 + (1 - p) ** 3) * weight
        assert chance_of(outcome, (W, colour, W)) == p * (1 - p) ** 2 * weight
    two = chance_of(outcome, (R, G, W))
    assert two == p**2 * (1 - p) * weights[0] * weights[1]


def test_the_chromatic_orb_changes_the_colours_and_nothing_else():
    item = socketed(sockets_of(R, W, G, W, links=(2, 1, 1)), mods=(RESIST_2, LIFE_1))
    for _, result in chromatic(item).results:
        assert dataclasses.replace(result, sockets=item.sockets) == item
        assert result.sockets.links == (2, 1, 1) and result.sockets.count == 4


def test_quality_raises_the_nonwhite_chance_with_the_cap_of_30():
    low = chromatic(socketed(white(6), quality=0)).chance_non_white(2)
    mid = chromatic(socketed(white(6), quality=20)).chance_non_white(2)
    high = chromatic(socketed(white(6), quality=30)).chance_non_white(2)
    assert low < mid < high
    assert high.__class__ is low.__class__ and chromatic(socketed(white(6), quality=0)).chance_non_white(2) == low  # a pure function of the item


def test_the_attributes_of_the_base_set_the_colours():
    body = chromatic(socketed(white(1)))  # intelligence 17
    sword = chromatic(socketed(white(1), base_id=SWORD))  # strength 8, dexterity 8
    assert chance_of(body, (B,)) == Fraction(9, 10) * Fraction(27, 37) and chance_of(body, (R,)) == chance_of(body, (G,))
    assert chance_of(sword, (B,)) == Fraction(1, 10) and chance_of(sword, (R,)) == chance_of(sword, (G,)) == Fraction(9, 20)


# --- the two readings of the forced colour ---------------------------------------------------------------------------------------------


def test_the_forced_colour_is_an_axis_of_the_orb_and_the_plan_reading_is_the_default():
    action = ChromaticOrb()
    assert action.rule_axes(DATA) == (CHROMATIC_FORCED_COLOUR,)
    assert CHROMATIC_FORCED_COLOUR.readings == ("siveran_weights", "flatter_second_reading") and CHROMATIC_FORCED_COLOUR.plan == "siveran_weights"
    assert len(model_readings(DATA, [action])) == 2
    assert ChromaticOrb(omen=True).rule_axes(DATA) == () and len(model_readings(DATA, [ChromaticOrb(omen=True)])) == 1
    item = socketed(white(1))
    assert action.outcomes_under(DATA, item).by_sockets == action.outcomes_under(DATA, item, Reading()).by_sockets  # the plan is the default


@pytest.mark.parametrize(
    "requirements,observed",
    [((180, 0, 0), (0.478, 0.276, 0.246)), ((25, 0, 0), (0.468, 0.262, 0.269)), ((0, 65, 0), (0.24, 0.52, 0.24))],
)
def test_the_second_reading_stays_within_four_points_of_the_forced_socket_cells(requirements, observed):
    data, one = six_white(2, 0, requirements)
    one = one.changed(data, sockets=sockets_of(W))
    plan = ChromaticOrb().outcomes_under(data, one)
    second = ChromaticOrb().outcomes_under(data, one, SECOND)
    weights = colour_weights(requirements)
    natural = nonwhite_chance(2, 0)  # the socket rolls non-white by itself with this chance (then the natural weights); otherwise it is forced
    assert [chance_of(plan, (c,)) for c in (R, G, B)] == list(weights)
    for colour, weight, seen in zip((R, G, B), weights, observed, strict=True):
        assert chance_of(second, (colour,)) == (1 - natural) * (weight / 3 + Fraction(2, 9)) + natural * weight  # one third of the weights plus two thirds uniform, when forced
        assert abs(float(chance_of(second, (colour,))) - seen) <= 0.04
    assert sum(chance_of(second, (c,)) for c in (R, G, B)) == 1


def test_the_readings_differ_only_for_a_forced_result_so_only_a_one_coloured_socket_target_sees_them():
    item = socketed(white(3))
    plan, second = chromatic(item), chromatic(item, reading=SECOND)
    for sockets in plan.by_sockets:
        if non_white(sockets.colours) >= 2:
            assert chance_of(plan, sockets.colours) == chance_of(second, sockets.colours)
    assert plan.chance_non_white(2) == second.chance_non_white(2)
    assert chance_of(plan, (B, W, W)) != chance_of(second, (B, W, W))


# --- the Omen of Trichromatism ------------------------------------------------------------------------------------------------------


def helmet(colours=(W, W, W, W), links=None, **fields):
    return socketed(sockets_of(*colours, links=links), base_id=HELMET, **fields)


def test_the_helmet_gets_red_green_and_blue_with_one_in_78_orbs_and_with_the_omen_for_certain():
    item = helmet()  # a dexterity-intelligence helmet, four white sockets, item level 84, 20% quality
    assert item.item_level == 84 and item.quality == PlainQuality(20)
    plain = chromatic(item)
    chance = plain.chance_colours(R, G, B)
    assert round(float(chance) * 100, 2) == 1.28
    assert round(1 / float(chance)) == 78  # the expected number of plain Chromatic Orbs
    omen = chromatic(item, omen=True)
    assert omen.chance_colours(R, G, B) == 1
    assert ChromaticOrb(omen=True).resources(DATA) == {CHROMATIC_ORB: 1, OMEN_OF_TRICHROMATISM: 1}  # one orb and the Omen


def test_the_omen_is_the_roll_conditioned_on_red_green_and_blue():
    item = sockets_of(R, G, B, links=(3,))
    outcome = chromatic(socketed(item), omen=True)
    permutations = {s.colours for s in outcome.by_sockets}
    assert permutations == {(R, B, G), (G, R, B), (G, B, R), (B, R, G), (B, G, R)}  # (R, G, B) is the current colours: never repeated
    assert set(outcome.by_sockets.values()) == {Fraction(1, 5)}  # the three weights multiply the same in any order
    four = chromatic(helmet((R, W, W, W)), omen=True)
    assert all({R, G, B} <= set(s.colours) for s in four.by_sockets) and all((R, W, W, W) != s.colours for s in four.by_sockets)
    p, weights = nonwhite_chance(84, 20), colour_weights((0, 61, 61))
    ratio = chance_of(four, (R, G, B, W)) / chance_of(four, (R, G, B, G))
    assert ratio == (1 - p) / (p * weights[1])  # the conditioned roll keeps the independent chances of each socket


@pytest.mark.parametrize("count", [1, 2])
def test_the_omen_is_not_offered_below_three_sockets(count):
    item = socketed(white(count))
    labels = [action.label(DATA) for action in catalog(DATA, item)]
    assert "Chromatic Orb" in labels and "Chromatic Orb with Omen of Trichromatism" not in labels
    with pytest.raises(NotApplicableError, match="needs 3 sockets"):
        ChromaticOrb(omen=True).outcomes(DATA, item)


@pytest.mark.parametrize("count", [3, 4, 6])
def test_the_omen_is_offered_from_three_sockets(count):
    item = socketed(white(count))
    assert "Chromatic Orb with Omen of Trichromatism" in [action.label(DATA) for action in catalog(DATA, item)]
    assert chromatic(item, omen=True).chance_colours(R, G, B) == 1


# --- refusals -----------------------------------------------------------------------------------------------------------------------------


def test_the_chromatic_orb_refusals():
    with pytest.raises(NotApplicableError, match="corrupted"):
        chromatic(socketed(white(2), corrupted=True))
    with pytest.raises(NotApplicableError, match="takes no sockets"):
        ChromaticOrb().outcomes(DATA, Item.build(DATA, base_id=AMULET, item_level=84, rarity=Rarity.RARE, mods=()))
    with pytest.raises(OutOfScopeError, match="states no sockets"):
        chromatic(socketed(None))
    abyss = abyss_data()
    held = Item.build(abyss, base_id=BODY, item_level=84, rarity=Rarity.RARE, mods=(ExplicitMod(ABYSS_MOD, (1,)),), sockets=white(2))
    with pytest.raises(OutOfScopeError, match="Abyssal"):
        ChromaticOrb().outcomes(dataclasses.replace(DATA, mods=abyss.mods), held)


# --- the bench's colour crafts -----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("minimum,price", list(BENCH_COLOUR_COSTS.items()))
def test_a_bench_colour_craft_costs_its_chromatic_orbs(minimum, price):
    action = BenchSocketColours(minimum)
    assert action.resources(DATA) == {CHROMATIC_ORB: price} and action.label(DATA) == f"Bench craft {minimum} coloured sockets"
    with pytest.raises(ValueError, match="needs the data"):
        action.resources(None)
    with pytest.raises(ValueError, match="no option"):
        BenchSocketColours(5).resources(DATA)


@pytest.mark.parametrize("minimum", [2, 3, 4])
def test_a_bench_colour_craft_is_the_roll_conditioned_on_at_least_that_many_coloured_sockets(minimum):
    item = helmet()
    outcome = BenchSocketColours(minimum).outcomes(DATA, item)
    p = float(nonwhite_chance(84, 20))
    counts: dict[int, float] = defaultdict(float)
    for sockets, chance in outcome.by_sockets.items():
        counts[non_white(sockets.colours)] += float(chance)
    total = sum(math.comb(4, k) * p**k * (1 - p) ** (4 - k) for k in range(minimum, 5))
    assert set(counts) == set(range(minimum, 5)) and sum(counts.values()) == pytest.approx(1)
    for k in range(minimum, 5):
        assert counts[k] == pytest.approx(math.comb(4, k) * p**k * (1 - p) ** (4 - k) / total)
    assert outcome.chance_non_white(minimum) == 1
    assert all(result.sockets.links == item.sockets.links for _, result in outcome.results)


def test_a_bench_colour_craft_excludes_no_colours_and_forces_no_socket():
    item = helmet((R, G, W, W))
    outcome = BenchSocketColours(2).outcomes(DATA, item)
    assert chance_of(outcome, (R, G, W, W)) > 0  # the repeat exclusion is the orb's, not the bench's
    plain = roll_colours(4, nonwhite_chance(84, 20), colour_weights((0, 61, 61)), None)
    kept = sum(chance for colours, chance in plain.items() if non_white(colours) >= 2)
    for colours, chance in plain.items():
        if non_white(colours) >= 2:
            assert chance_of(outcome, colours) == chance / kept


def test_the_bench_colour_craft_refusals():
    with pytest.raises(NotApplicableError, match="so 3 of them cannot be coloured"):
        BenchSocketColours(3).outcomes(DATA, socketed(white(2)))
    with pytest.raises(NotApplicableError, match="corrupted"):
        BenchSocketColours(2).outcomes(DATA, socketed(white(3), corrupted=True))
    with pytest.raises(OutOfScopeError, match="states no sockets"):
        BenchSocketColours(2).outcomes(DATA, socketed(None))
    assert BenchSocketColours(2).outcomes(DATA, socketed(white(2))).chance_non_white(2) == 1  # two sockets: both coloured


def test_the_kinds_list_the_colour_actions_only_for_a_class_that_takes_sockets():
    by_name = {entry.name: entry for entry in kinds()}
    for name in COLOUR_KINDS:
        assert not by_name[name].planner and "ADR-0045" in by_name[name].why_not and by_name[name].applies_only_to == "weapon and armour"
    assert by_name["chromatic-orb"].reads_item_state_while_not_planner == by_name["bench-socket-colours"].reads_item_state_while_not_planner == "quality"
    labels = [action.label(DATA) for action in catalog(DATA, socketed(white(4)))]
    assert [label for label in labels if label.startswith("Bench craft") and "coloured" in label] == [f"Bench craft {n} coloured sockets" for n in (2, 3, 4)]
    amulet = Item.build(DATA, base_id=AMULET, item_level=84, rarity=Rarity.RARE, mods=())
    assert not any(type(a) in {ChromaticOrb, BenchSocketColours} for a in catalog(DATA, amulet))
    planner = {type(action) for action in catalog(DATA, socketed(white(4)), planner_only=True)}
    assert not planner & {ChromaticOrb, BenchSocketColours}


# --- declarations and the contract suite ---------------------------------------------------------------------------------------


DECLARED = {
    # action: (reads: count, links, colours; adds: count, links, colours)
    ChromaticOrb(): ((True, False, True), (False, False, True)),
    ChromaticOrb(omen=True): ((True, False, True), (False, False, True)),
    BenchSocketColours(2): ((True, False, False), (False, False, True)),
}


@pytest.mark.parametrize("action", list(DECLARED), ids=lambda action: action.label(DATA))
def test_each_colour_action_declares_what_it_reads_and_sets(action):
    reads, adds = action.reads(DATA), action.adds(DATA, None)
    wanted_reads, wanted_adds = DECLARED[action]
    assert (reads.socket_count, reads.socket_links, reads.socket_colours) == wanted_reads
    assert (adds.socket_count, adds.socket_links, adds.socket_colours) == wanted_adds
    assert adds.only_sockets and reads.quality and not (reads.implicits or reads.offer)  # it reads the plain quality: the non-white chance
    assert reads.junk and reads.families == frozenset() and not reads.block_invariant


@pytest.mark.parametrize("name", COLOUR_ITEMS)
@pytest.mark.parametrize("kind_name", COLOUR_KINDS)
def test_each_colour_action_meets_the_contract_on_every_colour_fixture(kind_name, name):
    extra = EXTRA[name]
    entry = next(entry for entry in kinds() if entry.name == kind_name)
    for action in entry.members(extra.data, extra.item):
        assert isinstance(check_action(action, extra.item, extra.data), bool)  # False where the game refuses it: the check then holds the refusal


@pytest.mark.parametrize("minimum", [2, 3, 4])
@pytest.mark.parametrize("name", ["colours_body_three", "colours_helmet_four", "colours_bow_five_plain", "colours_body_white_six"])
def test_the_bench_colour_crafts_pass_the_contract_suite_at_every_minimum(name, minimum):
    extra = EXTRA[name]
    check_action(BenchSocketColours(minimum), extra.item, extra.data)


def test_the_colour_actions_apply_where_the_game_lets_them():
    wanted = {
        "chromatic-orb": {"colours_body_three", "colours_body_white_six", "colours_body_one", "colours_body_two", "colours_helmet_four",
                          "colours_sword_three_stranded", "colours_bow_five_plain"},
        "bench-socket-colours": {"colours_body_three", "colours_body_white_six", "colours_body_two", "colours_helmet_four", "colours_sword_three_stranded",
                                 "colours_bow_five_plain"},
    }
    for kind_name, names in wanted.items():
        entry = next(entry for entry in kinds() if entry.name == kind_name)
        for name in COLOUR_ITEMS:
            extra, applied = EXTRA[name], []
            for action in entry.members(extra.data, extra.item):
                try:
                    action.outcomes_under(extra.data, extra.item)
                    applied.append(action)
                except (NotApplicableError, OutOfScopeError):
                    pass
            assert bool(applied) == (name in names), f"{kind_name} on {name}"


def test_every_colour_action_declares_it_neither_cuts_nor_spends_and_works_on_a_stranded_item():
    stranded = EXTRA["colours_sword_three_stranded"].item
    assert stranded.memory_strands == 45
    for action in DECLARED:
        use = action.strand_use(DATA)
        assert use is not None and not use.cuts and use.spend is None and use.claims
        assert action.strand_claims(DATA) == use.claims
    result = ChromaticOrb().outcomes_under(DATA, stranded)
    assert all(found.memory_strands == 45 for _, found in result.results)


# --- claims -------------------------------------------------------------------------------------------------------------------------


def approximate(action) -> set[str]:
    return {rule_id.removeprefix("sockets.") for rule_id in action.claims(None) if rule_by_id(rule_id).approximate}


def test_the_claims_of_each_colour_action_carry_the_marks_of_adr_0047():
    """ADR-0047, "Marks and claims": the forced colour, the repeat exclusion and the requirement mods are `approximate`; the Siveran inputs and the prices are not."""
    assert approximate(ChromaticOrb()) == {
        "chromatic_forced_socket_colour", "chromatic_never_repeats_the_current_colours", "chromatic_ignores_requirement_mods", "class_maximum_sockets",
    }
    assert approximate(ChromaticOrb(omen=True)) == {
        "chromatic_never_repeats_the_current_colours", "chromatic_ignores_requirement_mods", "class_maximum_sockets", "omen_of_trichromatism_conditions_the_roll",
        "omen_of_trichromatism_below_three_sockets",
    }
    assert approximate(BenchSocketColours(2)) == {"chromatic_ignores_requirement_mods", "class_maximum_sockets", "bench_at_least_n_non_white_is_a_conditioned_roll"}
    plain = ChromaticOrb().claims(None)
    assert {"sockets.chromatic_roll_then_force", "sockets.chromatic_nonwhite_chance", "sockets.chromatic_natural_colour_weights",
            "sockets.chromatic_one_socket_always_coloured", "sockets.chromatic_orb_cost"} <= plain
    assert {"sockets.omen_of_trichromatism", "sockets.omen_of_trichromatism_cost"} <= ChromaticOrb(omen=True).claims(None)
    assert "sockets.chromatic_forced_socket_colour" not in ChromaticOrb(omen=True).claims(None)
    assert {"sockets.bench_colour_cost", "sockets.bench_on_corrupted_costs_vaal"} <= BenchSocketColours(3).claims(None)


def test_every_claim_a_colour_action_names_is_in_the_registry_and_the_costs_are_the_price_names():
    registry = load_registry()
    for action in (*DECLARED, BenchSocketColours(3), BenchSocketColours(4)):
        assert action.claims(None) <= set(registry)
        assert action.strand_claims(None) <= set(registry)
    assert dict(registry["sockets.chromatic_orb_cost"].value) == {CHROMATIC_ORB: 1}
    assert dict(registry["sockets.omen_of_trichromatism_cost"].value) == {OMEN_OF_TRICHROMATISM: 1}
    assert ChromaticOrb().resources(None) == {CHROMATIC_ORB: 1}
    assert not registry["sockets.chromatic_orb_cost"].approximate and not registry["sockets.omen_of_trichromatism_cost"].approximate
