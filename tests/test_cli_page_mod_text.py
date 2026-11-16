"""How the route page names a mod and draws an item card (#980, #991, #963, #962; OR-15, OR-17, OR-31).

* #980: an influence's own mod is drawn by its own text and tier. R14's Hunter prefix "(90-94)% increased Chaos Damage over Time" is tier 1
  of its own ladder on a Hunter bow; the page read the tiers of the plain base, found no mod of the leaf there and drew another mod of its
  family ("Physical Damage over Time"). The plan was never wrong: the target accepts tier 1 alone, and the planner's goal holds it.
* #991: a range is written low to high, `(24-30)% reduced Effect of Chill and Shock on you` where the data writes `(30-24)%`, and a limit
  that leaves out many bench crafts is one short statement with the crafts in a closed element.
* #963: a base jewel has no tiers: its mods carry no tier note and its tier chances no ladder, in the one mod format with ranges.
* #962: a Magic item's card draws one prefix and one suffix slot.

The plans are made through the planner's entry (`make_plan`, not solved) on hand-made items; they need the cached dump and skip without it.
"""

import re
from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system.actions.bench import bench_crafts
from crafting_system.cli import make_plan
from crafting_system.cli._benchmark import DOT_TIERS, GEMS, MULTIMOD, NO_ATTACK, SPEED
from crafting_system.cli._benchmark_outcomes import rolled
from crafting_system.cli._route_card import Slot, _leaf_slot, _StateReader, card_of_item, card_of_states, card_of_target, mod_text, page_tiers
from crafting_system.cli._route_html import _more
from crafting_system.cli._route_tiers import tier_lines
from crafting_system.cli._route_view import BENCH_LABEL, _View, limit_line
from crafting_system.items import Item, Rarity, natural_tiers
from crafting_system.items.words import ranges_low_first
from crafting_system.planner import Limit
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-07-31.json"
VENDOR = ROOT / "tests" / "fixtures" / "prices" / "vendor-v01-2026-11-01.json"
CHAOS_DOT = "(90-94)% increased Chaos Damage over Time"
RANGE = re.compile(r"\((-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)\)")
DOT_MULTI, SUPPORT = "JunMaster2ChaosDamageOverTimeMultiplier3", "JunMaster2LocalIncreaseSocketedSupportGemLevel2"


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def plan_of(data, name: str, prices: Path):
    return make_plan(data, load_target(ROOT / "examples" / "targets" / name, data), load_price_file(prices), solve_it=False)


@pytest.fixture(scope="module")
def r14(data):
    return plan_of(data, "r14-hunter-bow.yaml", ROUTES)


def bow(data, plan, held, crafted=()):
    """A rare Hunter bow of R14's target with the mods `held` and the crafted mods `crafted`, each at the low end of its range."""
    target = plan.target
    mods = (*(rolled(data, mod_id) for mod_id in held), *(rolled(data, mod_id, crafted=True) for mod_id in crafted))
    return Item.build(data, base_id=target.base_id, item_level=target.item_level, rarity=Rarity.RARE, influences=target.start_item.influences, mods=mods)


def lines_of(card):
    return [(slot.text, slot.note) for slot in (*card.prefixes, *card.suffixes)]


# -- #980: the Hunter's Chaos Damage over Time ---------------------------------------------------------------------------------------


def test_the_planners_goal_holds_the_hunter_chaos_damage_over_time_at_tier_1_and_no_lower_tier(data, r14):
    ab = r14.abstraction
    finished = [SPEED, GEMS, DOT_TIERS[3]]
    crafted = [MULTIMOD, DOT_MULTI, SUPPORT]

    assert ab.is_goal(ab.compress(bow(data, r14, finished, crafted)))  # tier 1 of four: the target's
    for lower in DOT_TIERS[:3]:
        assert not ab.is_goal(ab.compress(bow(data, r14, [SPEED, GEMS, lower], crafted)))


def test_the_goal_card_says_the_hunter_mod_by_its_own_text_and_tier_never_another_mod_of_its_family(data, r14):
    card = card_of_target(data, r14.target)

    assert (CHAOS_DOT, "T1") in lines_of(card)
    assert not any("Physical" in text for text, _ in lines_of(card))


def test_a_step_card_says_the_hunter_mod_at_the_target_tier_and_a_lower_tier_as_too_low(data, r14):
    ab = r14.abstraction
    reader = _StateReader(ab, r14.target.start_item, None, r14.target.influences)
    crafted = [MULTIMOD, DOT_MULTI, SUPPORT]

    top = lines_of(card_of_states(ab, [ab.compress(bow(data, r14, [SPEED, GEMS, DOT_TIERS[3]], crafted))], reader))
    low = lines_of(card_of_states(ab, [ab.compress(bow(data, r14, [SPEED, GEMS, DOT_TIERS[0]], crafted))], reader))

    assert (CHAOS_DOT, "T1") in top
    assert ("#% increased Chaos Damage over Time", "tier too low") in low
    assert not any("Physical" in text for text, _ in (*top, *low))


def test_the_exalted_orb_gives_each_tier_of_the_hunter_mod_and_marks_tier_1_alone(data, r14):
    ab = r14.abstraction
    exalted = next(priced for priced in r14.offers if priced.label == "Exalted Orb")
    state = ab.compress(bow(data, r14, [SPEED, GEMS], [MULTIMOD, NO_ATTACK]))  # the second forced Exalted Orb

    lines = {line.text: line for line in tier_lines(ab, exalted.offer.action, [state], [1.0])}

    assert set(lines) == {"#% increased Chaos Damage over Time"}
    line = lines["#% increased Chaos Damage over Time"]
    assert [share.tier for share in line.tiers] == [1, 2, 3, 4]
    assert [share.wanted for share in line.tiers] == [True, False, False, False]
    assert line.none == pytest.approx(0.0, abs=1e-12)  # the only prefix left: some tier of it comes every time


# -- #991: ranges low to high, and the left-out bench crafts said shortly -------------------------------------------------------------


def test_a_range_is_written_low_to_high_for_every_mod_of_the_data(data):
    assert ranges_low_first("(30-24)% reduced Effect of Chill and Shock on you") == "(24-30)% reduced Effect of Chill and Shock on you"
    assert ranges_low_first("+(-5--10) to x / (1.5-0.5)% y") == "+(-10--5) to x / (0.5-1.5)% y"
    for mod in data.mods.values():
        text = mod_text(mod)
        for low, high in RANGE.findall(text):
            assert float(low) <= float(high), (mod.id, text)


def test_every_bench_craft_is_labelled_with_its_ranges_low_to_high(data):
    labels = [craft.label(data) for craft in bench_crafts(data)]

    assert "Bench craft (24-30)% reduced Effect of Chill and Shock on you" in labels
    for label in labels:
        for low, high in RANGE.findall(label):
            assert float(low) <= float(high), label


def test_many_left_out_bench_crafts_read_as_one_statement_with_the_crafts_folded():
    crafts = tuple(f"{BENCH_LABEL}+({n}-{n + 5}) to thing {n}" for n in range(146))
    limit = Limit("crafts", "Not offered", "its mod counts toward no requirement", "The plan is unaffected.", crafts)

    line = limit_line(limit)

    assert line.text == "Not offered: 146 bench crafts, each because its mod counts toward no requirement. The plan is unaffected."
    assert line.more == tuple(label.removeprefix(BENCH_LABEL) for label in crafts)
    assert _more(line).startswith("<details><summary>which crafts</summary>+(0-5) to thing 0, ")


def test_a_short_limit_and_one_of_other_actions_still_name_their_first_labels():
    few = Limit("crafts", "Not offered", "", "The plan is unaffected.", (f"{BENCH_LABEL}a", f"{BENCH_LABEL}b"))
    orbs = Limit("kinds", "Not offered", "", "The plan is unaffected.", ("Exalted Orb", "Chaos Orb", "Regal Orb", "Divine Orb"))

    assert limit_line(few).text == "Not offered: Bench craft a, Bench craft b. The plan is unaffected."
    assert limit_line(orbs).text.startswith("Not offered, 4 in all: Exalted Orb, Chaos Orb, Regal Orb and 1 more")
    assert limit_line(orbs).more == ("Divine Orb",)


# -- #963: a base jewel has no tiers ------------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def j01(data):
    return plan_of(data, "j01-cobalt-life-attack-speed.yaml", ROUTES)


def test_a_jewels_goal_card_writes_no_tier(data, j01):
    lines = lines_of(card_of_target(data, j01.target))

    assert ("(5-7)% increased maximum Life", "") in lines
    assert all(note == "" for text, note in lines if text not in ("any mod or empty", "empty"))


def test_a_jewels_tier_chances_have_no_ladder_and_write_the_mod_with_its_ranges(data, j01):
    ab = j01.abstraction
    chaos = next(priced for priced in j01.offers if priced.label == "Chaos Orb")

    lines = tier_lines(ab, chaos.offer.action, [ab.compress(j01.target.start_item)], [1.0])

    assert {line.text for line in lines} == {
        "(5-7)% increased maximum Life",
        "(3-5)% increased Attack Speed",
        "(6-8)% increased Attack Speed with Wands",
    }
    for line in lines:
        text = _View.tier_text(line)
        assert not line.tiered and "T1" not in text and "every tier" not in text and "#" not in text
        assert text.startswith(f"{line.text}: ") and " · none " in text


# -- #962: a Magic item draws one prefix and one suffix ------------------------------------------------------------------------------


def test_a_magic_items_card_draws_one_prefix_and_one_suffix_and_a_rare_three_of_each(data, r14):
    target = r14.target
    magic = Item.build(
        data, base_id=target.base_id, item_level=target.item_level, rarity=Rarity.MAGIC, influences=target.start_item.influences,
        mods=(rolled(data, SPEED),),
    )  # fmt: skip
    card = card_of_item(data, magic, tiers=True, rolled=False)

    assert (len(card.prefixes), len(card.suffixes)) == (1, 1)
    assert card.suffixes == (Slot("(17-19)% increased Attack Speed", "mod", (), "T1"),)
    rare = card_of_item(data, bow(data, r14, [SPEED]))
    assert (len(rare.prefixes), len(rare.suffixes)) == (3, 3)


def test_a_magic_state_after_a_step_draws_one_prefix_and_one_suffix(data):
    plan = plan_of(data, "v01-minion-helmet.yaml", VENDOR)
    ab, target = plan.abstraction, plan.target
    magic = Item.build(data, base_id=target.base_id, item_level=target.item_level, rarity=Rarity.MAGIC)

    card = card_of_states(ab, [ab.compress(magic)])

    assert (len(card.prefixes), len(card.suffixes)) == (1, 1)
    assert card.properties[0] == "Magic"


def test_a_step_of_several_magic_states_draws_one_prefix_and_one_suffix(data):
    plan = plan_of(data, "v01-minion-helmet.yaml", VENDOR)
    ab, target = plan.abstraction, plan.target
    tiers = page_tiers(data, target.base_id)
    life = next(mod_id for mod_id in sorted(natural_tiers(data, target.base_id, tiers)) if "to maximum Life" in mod_text(data.mods[mod_id]) and tiers[mod_id] == 3)
    bare = Item.build(data, base_id=target.base_id, item_level=target.item_level, rarity=Rarity.MAGIC)
    held = Item.build(data, base_id=target.base_id, item_level=target.item_level, rarity=Rarity.MAGIC, mods=(rolled(data, life),))

    card = card_of_states(ab, [ab.compress(bare), ab.compress(held)])

    assert (len(card.prefixes), len(card.suffixes)) == (1, 1)


# -- one rung on a base with ladders, and several tierless candidates -----------------------------------------------------------------


def test_a_mod_alone_on_its_ladder_on_a_bow_keeps_its_tier_on_the_card_and_in_the_tier_chances(data, r14):
    ab = r14.abstraction
    exalted = next(priced for priced in r14.offers if priced.label == "Exalted Orb")
    state = ab.compress(bow(data, r14, [SPEED], [MULTIMOD, NO_ATTACK]))  # the first forced Exalted Orb: +1 gems or the Chaos Damage over Time

    lines = {line.text: line for line in tier_lines(ab, exalted.offer.action, [state], [1.0])}

    gems = lines["+1 to Level of Socketed Gems"]
    assert gems.tiered and _View.tier_text(gems).startswith("+1 to Level of Socketed Gems: T1 ")  # the same tier as its mod line
    assert lines["#% increased Chaos Damage over Time"].tiered
    assert card_of_target(data, r14.target).prefixes[0] == Slot("+1 to Level of Socketed Gems", "wanted", (), "T1")  # the mod line keeps its tier


def test_a_leaf_of_several_mods_on_a_base_with_no_tiers_writes_each_with_its_ranges(data, j01):
    base = j01.target.base_id
    tiers = page_tiers(data, base)
    two = sorted(mod_id for mod_id in natural_tiers(data, base, tiers) if data.mods[mod_id].generation_type == "suffix")[:2]

    _, text, note = _leaf_slot(data, base, tiers, frozenset(two), None)

    assert tiers.tierless and note == ""
    assert text == " or ".join(mod_text(data.mods[mod_id]) for mod_id in two) and "#" not in text
