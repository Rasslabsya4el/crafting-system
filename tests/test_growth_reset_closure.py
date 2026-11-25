"""The growth's reset closure (#1600, hypothesis H57 of #1434; OR-42): where the start item is bought, every group the growth names holds the
reset path back to the start (when it costs less than buying the start again) and the plain reroll of the start's rarity.

Each case is a hand-made table (`test_growth._table`): the offers declare their kinds, the rarities their outcomes have, whether they wipe the
item (`Entry.wipes`: an Orb of Scouring) and whether they force a mod (`Entry.forces`: an essence). Prices are R13's (the magic belt): the
start 17.4 c, Scouring 0.346 c, Transmutation 0.011 c, Alteration 0.178 c, Augmentation 0.052 c; the reset (0.357 c) beats the rebuy.
Then the declarations read from the toy boots of `listing_support` with the real orbs, and the plan of that toy: with the Alteration beside
the reset, the reset is never the reroll (the fault of #1201's wipe and of th59's control, where the group lacked the Alteration).
"""

import dataclasses
from fractions import Fraction

from listing_support import magic_toy, prices
from test_growth import _entry, _names, _table

from crafting_system.planner._growth import Grower

from crafting_system.abstraction._goal import Goal
from crafting_system.actions import unopened_listing
from crafting_system.items import Rarity
from crafting_system.planner import RESTART, _plan, plan_target
from crafting_system.planner._plan import offers_for, price_offers
from crafting_system.prices import PriceEntry
from crafting_system.targets import start_price_key

MAGIC, RARE, NORMAL = Rarity.MAGIC, Rarity.RARE, Rarity.NORMAL
A, B = 0, 1
START = 17.4  # R13's belt listing
SCOUR, TRANSMUTE, ALTERATION, AUGMENT, ALCHEMY, CHAOS = 0.346, 0.011, 0.178, 0.052, 0.2, 1.0


def _wipe(cost=SCOUR, lands=NORMAL, at=(MAGIC, RARE)):
    return _entry("scour", cost, kind="reroll", leads={shape: frozenset({lands}) for shape in at}, wipes=True, draws=False)


def _move(label, cost, to, **declared):
    return dataclasses.replace(_entry(label, cost, kind="reroll", leads={NORMAL: frozenset({to})}, **declared), kinds={NORMAL: "reroll"})


def _reroll(label, cost, at=MAGIC, **declared):
    return _entry(label, cost, kind="reroll", chance={A: Fraction(1, 10)}, at=at, leads={at: frozenset({at})}, **declared)


def _magic_start(rebuy=START):
    table = _table(
        _entry("augment", AUGMENT, chance={A: Fraction(1, 2), B: Fraction(1, 2)}, leads={MAGIC: frozenset({MAGIC})}),
        _wipe(),
        _move("transmute", TRANSMUTE, MAGIC),
        _move("alchemy", ALCHEMY, RARE),
        _reroll("alteration", ALTERATION),
        _reroll("dear alteration", 5.0),
        _entry("regal", 0.3, kind="add", leads={MAGIC: frozenset({RARE})}),
    )
    table.rebuy = rebuy
    return table


def test_a_reset_cheaper_than_the_rebuy_comes_with_the_plain_reroll_in_every_group_the_growth_names():
    table = _magic_start()
    assert _names(table, table.reset_path()) == {"scour", "transmute"}  # 0.357 c against 17.4 c
    assert _names(table, table.plain_reroll()) == {"alteration"}  # the cheapest reroll that keeps the item magic
    assert _names(table, table.closure({0})) == {"augment", "scour", "transmute", "alteration"}
    assert table.closure(set()) == set()  # an empty group stays empty


def test_a_rebuy_cheaper_than_the_reset_keeps_the_rebuy_and_the_plain_reroll_still_comes():
    table = _magic_start(rebuy=0.3)  # under Scouring + Transmutation
    assert table.reset_path() == set()
    assert _names(table, table.closure({0})) == {"augment", "alteration"}


def test_a_start_that_is_not_bought_has_no_reset_closure():
    table = _magic_start(rebuy=None)
    assert table.reset_closure() == frozenset() and _names(table, table.closure({0})) == {"augment"}


def test_a_rare_start_takes_the_chaos_orb_and_the_alchemy_never_an_essence_that_forces_its_mod():
    table = _table(
        _entry("exalt", 2.0, at=RARE, chance={A: Fraction(1, 8)}, leads={RARE: frozenset({RARE})}),
        _wipe(),
        _move("essence at normal", 0.05, RARE, forces=True),  # cheaper than the Alchemy, but its mod is on every outcome
        _move("alchemy", ALCHEMY, RARE),
        _move("transmute", TRANSMUTE, MAGIC),
        _reroll("essence", 0.5, at=RARE, forces=True),  # cheaper than the Chaos Orb, same reason
        _reroll("chaos", CHAOS, at=RARE),
    )
    table.start_rarity, table.rebuy = RARE, 40.0
    assert _names(table, table.reset_path()) == {"scour", "alchemy"}
    assert _names(table, table.plain_reroll()) == {"chaos"}
    assert _names(table, table.closure({0})) == {"exalt", "scour", "alchemy", "chaos"}


def test_a_reroll_that_guarantees_a_tag_is_no_plain_reroll():
    from types import SimpleNamespace

    table = _table(_reroll("harvest reforge", 0.5, at=RARE), _reroll("chaos", CHAOS, at=RARE))
    table.start_rarity, table.rebuy = RARE, 40.0
    reforge = table.entries[0]
    declared = SimpleNamespace(named=frozenset(), crafted=False, draws=True, fractures=False, tag="life", veils=False)
    action = SimpleNamespace(adds=lambda *_: declared, reads=lambda *_: SimpleNamespace(needs_veiled=False, needs_crafted=False, families=()), imprint_move=lambda: None)
    table.data = SimpleNamespace(mods={})
    table._read_declarations(reforge, SimpleNamespace(offer=SimpleNamespace(action=action)), None)
    assert reforge.forces and _names(table, table.plain_reroll()) == {"chaos"}


def test_the_seed_holds_the_reset_and_the_plain_reroll_though_no_wanted_mod_ranks_them():
    table = _table(
        _entry("augment", AUGMENT, chance={A: Fraction(1, 2), B: Fraction(1, 2)}, leads={MAGIC: frozenset({MAGIC})}),
        _entry("craft A", 2.5, kind="craft", chance={A: 1}),
        _entry("craft B", 2.5, kind="craft", chance={B: 1}),
        _wipe(),
        _move("transmute", TRANSMUTE, MAGIC),
        _entry("alteration", ALTERATION, kind="reroll", leads={MAGIC: frozenset({MAGIC})}),  # no chance on A or B worth ranking
    )
    table.rebuy = START
    assert _names(table, table.seed()) == {"augment", "craft A", "craft B"}
    positions, _words = Grower(table, ()).seed()
    assert _names(table, positions) == {"augment", "craft A", "craft B", "scour", "transmute", "alteration"}
    table.rebuy, table._reset = None, None  # a start not bought: the seed is the ranking alone
    assert _names(table, Grower(table, ()).seed()[0]) == {"augment", "craft A", "craft B"}


def test_a_fractured_start_is_reset_by_the_wipe_alone_and_rerolled_by_the_alteration_not_by_the_wipe():
    # a magic start holding a fractured mod: the Scouring keeps it, so the item stays magic and no Transmutation follows
    table = _table(
        _entry("augment", AUGMENT, chance={A: Fraction(1, 2)}, leads={MAGIC: frozenset({MAGIC})}),
        _wipe(lands=MAGIC, at=(MAGIC,)),
        _move("transmute", TRANSMUTE, MAGIC),
        _reroll("alteration", ALTERATION),
    )
    table.rebuy = START
    assert _names(table, table.reset_path()) == {"scour"}
    assert _names(table, table.plain_reroll()) == {"alteration"}  # the wipe draws no mod: it is no reroll


def test_a_normal_start_has_no_reroll_so_its_closure_holds_nothing_though_the_wipe_beats_the_rebuy():
    # R17's Talisman (#1637): the Scouring lands on the start itself and the Transmutation follows it, a magic reroll of 0.357 c beside no
    # Alteration in the group; the closure holds nothing, and the Alteration a magic item has does not make it hold the wipe
    table = _table(
        _entry("augment", AUGMENT, chance={A: Fraction(1, 2)}, leads={MAGIC: frozenset({MAGIC})}),
        _wipe(),
        _move("transmute", TRANSMUTE, MAGIC),
        _reroll("alteration", ALTERATION),
    )
    table.start_rarity, table.rebuy = NORMAL, 533.0
    assert _names(table, table.reset_path()) == {"scour"}  # 0.346 c against 533 c: cheaper, yet
    assert table.plain_reroll() == set()  # nothing rerolls a Normal item
    assert table.reset_closure() == frozenset()
    assert _names(table, table.closure({0})) == {"augment"}


def test_a_magic_start_whose_reroll_is_held_back_holds_no_wipe_in_that_group():
    table = _magic_start()
    table.held_back = frozenset({4, 5})  # both Alterations wait for a later group
    assert _names(table, table.reset_path()) == {"scour", "transmute"}
    assert table.reset_closure() == frozenset()
    table.held_back = frozenset()
    assert _names(table, table.reset_closure()) == {"scour", "transmute", "alteration"}


def test_a_wipe_held_back_or_a_reset_dearer_than_the_rebuy_is_not_named():
    table = _magic_start()
    table.held_back = frozenset({1})
    assert table.reset_path() == set()
    table = _magic_start(rebuy=SCOUR + TRANSMUTE)  # equal: buying again is as cheap, the rebuy stays the restart
    assert table.reset_path() == set()


# the declarations read from the real orbs on the toy boots of `listing_support`
METHODS = ("alteration-orb", "augmentation-orb", "regal-orb", "transmutation-orb", "scouring-orb")


def _toy(mods=""):
    from listing_support import target

    data = magic_toy()
    aim = target(data, actions=", ".join(METHODS), mods=mods)
    entries = prices(start_price_key(data, aim))
    entries.prices["Orb of Scouring"] = PriceEntry(1.0, "fixture")
    return data, aim, entries


def test_the_real_orbs_declare_their_parts_and_the_grower_s_table_holds_the_rebuy():
    data, aim, entries = _toy()
    goal = Goal.from_target(aim)
    priced, _dropped = price_offers(offers_for(data, goal, aim.base_id, aim.start_item, aim.actions).offers, entries, "test")
    grower = _plan.rounds_grower(data, goal, aim, priced, unopened_listing(data, aim.start_item), (), 10.0)
    table = grower.table
    by = {entry.label: entry for entry in table.entries}
    assert [label for label, entry in by.items() if entry.wipes] == ["Orb of Scouring"]
    assert not any(entry.forces for entry in table.entries)
    assert table.rebuy == 10.0
    assert _names(table, table.reset_closure()) == {"Orb of Scouring", "Orb of Transmutation", "Orb of Alteration"}
    seed = grower.seed()
    assert {"Orb of Scouring", "Orb of Transmutation", "Orb of Alteration"} <= _names(table, seed[0])
    assert _plan.rounds_grower(data, goal, aim, priced, None, ()).table.reset_closure() == frozenset()  # a start not bought


def test_a_normal_toy_start_bought_has_no_reset_closure_from_the_real_orbs():
    from listing_support import target

    data = magic_toy()
    aim = target(data, rarity="normal", actions=", ".join(METHODS))
    entries = prices(start_price_key(data, aim))
    entries.prices["Orb of Scouring"] = PriceEntry(1.0, "fixture")
    goal = Goal.from_target(aim)
    priced, _dropped = price_offers(offers_for(data, goal, aim.base_id, aim.start_item, aim.actions).offers, entries, "test")
    grower = _plan.rounds_grower(data, goal, aim, priced, unopened_listing(data, aim.start_item), (), 10.0)
    table = grower.table
    assert table.start_rarity is NORMAL
    assert _names(table, table.reset_path()) == {"Orb of Scouring"}  # 1 c against the 10 c listing
    assert table.plain_reroll() == set()  # the Alteration rerolls a magic item, not the Normal start
    assert table.reset_closure() == frozenset()  # so the wipe is not put in every group


def _scourings_at_magic(plan) -> int:
    """The states of the plan's policy, magic ones, where it uses the Orb of Scouring (the reset standing in for a reroll)."""
    return sum(1 for state, decision in plan.policy.items() if decision.label == "Orb of Scouring" and state.flags.rarity is MAGIC)


def test_with_the_alteration_beside_the_reset_the_plan_never_rerolls_by_resetting_and_it_does_when_the_alteration_is_dearer():
    data, aim, entries = _toy()
    plan = plan_target(data, aim, entries)
    assert _scourings_at_magic(plan) == 0  # Scouring + Transmutation is 1.2 c a reroll against the Alteration's 1.0 c
    entries.prices["Orb of Alteration"] = PriceEntry(5.0, "fixture")
    dear = plan_target(data, aim, entries)
    assert _scourings_at_magic(dear) > 0  # the test can see it: with the Alteration dearer the reset is the reroll
    assert dear.mean_remaining > plan.mean_remaining


def test_a_fractured_toy_start_is_reset_by_the_scouring_alone():
    data, aim, entries = _toy(mods="  mods:\n    - mod: ToyA\n      values: [1]\n      fractured: true\n")
    goal = Goal.from_target(aim)
    priced, _dropped = price_offers(offers_for(data, goal, aim.base_id, aim.start_item, aim.actions).offers, entries, "test")
    table = _plan.rounds_grower(data, goal, aim, priced, unopened_listing(data, aim.start_item), (), 10.0).table
    assert _names(table, table.reset_path()) == {"Orb of Scouring"}
    assert _names(table, table.plain_reroll()) == {"Orb of Alteration"}



# the page words of #1595 for a restart on the same item, carried over to the ordinary orbs (OR-42): a toy whose Regal Orb misses into a rare
# item no orb mends, so the craft starts over (A, B prefixes and C suffix wanted; Scouring 1 c, Transmutation 0.2 c, the listing 10 c)
THREE = """\
base: Toy Listing Boots
item_level: 86
start_item:
  rarity: magic
{mods}start: bought
requirements:
  - family: ToyA
    min_tier: any
  - family: ToyB
    min_tier: any
  - family: ToyC
    min_tier: any
"""
FRACTURED_A = "  mods:\n    - mod: ToyA\n      values: [1]\n      fractured: true\n"


def _three(mods="", start="bought"):
    from crafting_system.targets import parse_target

    data = magic_toy()
    text = THREE.format(mods=mods).replace("start: bought", f"start: {start}")
    aim = dataclasses.replace(parse_target(text, data, source="toy-reset.yaml"), actions=(*METHODS[:3], "transmutation-orb", "scouring-orb"))
    entries = prices(start_price_key(data, aim) if start == "bought" else None)
    entries.prices["Orb of Scouring"] = PriceEntry(1.0, "fixture")
    return data, aim, entries


def _toy_plans():
    data, aim, entries = _three()
    plan = plan_target(data, aim, entries)
    del entries.prices["Orb of Scouring"]
    return data, plan, plan_target(data, aim, entries)


def _page_text(mods="", start="bought"):
    import html
    import re

    from crafting_system.cli import build_report
    from crafting_system.cli._route_view import route_page

    data, aim, entries = _three(mods, start)
    plan = plan_target(data, aim, entries)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", route_page(build_report(plan, data), data))))


def test_the_page_titles_a_scouring_whose_next_step_is_the_start_s_own_draw_as_starting_over_on_the_same_item():
    text = _page_text()
    assert "6. Start over on the same item: Orb of Scouring, then Orb of Transmutation Cost per use 1 × Orb of Scouring 1 c" in text
    assert "with an unwanted suffix, then Start over on the same item: Orb of Scouring, then Orb of Transmutation" in text  # the Regal's miss
    assert "7. Orb of Transmutation" in text and "Restart: buy" not in text  # the reset is cheaper than the listing: nothing is bought again


def test_the_page_titles_the_scouring_of_a_fractured_start_as_starting_over_alone():
    text = _page_text(FRACTURED_A)
    assert "Start over on the same item: Orb of Scouring Reached from" in text
    assert "Start over on the same item: Orb of Scouring, then" not in text


def test_a_start_whose_own_mods_a_wipe_takes_off_is_never_titled_as_starting_over():
    text = _page_text("  mods:\n    - mod: ToyA\n      values: [1]\n", start="given")
    assert "Start over on the same item" not in text


def test_with_the_reset_priced_the_toy_never_buys_the_listing_again_and_costs_less():
    data, plan, no_scouring = _toy_plans()
    assert not any(decision.label == RESTART for decision in plan.policy.values())
    assert any(decision.label == RESTART for decision in no_scouring.policy.values())
    # each restart costs 1.2 c (Scouring + Transmutation) in place of the 10 c listing: the plan is cheaper, by less than 8.8 c a restart
    assert 0 < no_scouring.mean_remaining - plan.mean_remaining
