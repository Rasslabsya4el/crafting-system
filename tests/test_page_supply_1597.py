"""R17's page as a player reads it (#1597): the supply a market showed beside what a step buys, goods paid at a stand-in price named as the
goods, a restore rolls no tier, conditions that read one way, a rarely reached step's uses, and the guide's figure when it is 0 or a hair
below the plan's.

Hand figures from R17's saved plan (`t1637/mech-R17`): step 9 buys a Fenumal Plagued Arachnid on each of ≈435 uses, the plan ≈435 in all.
poe.ninja's daily row of the beast in the week-one file counts 399 listings, its cap (#930): the market held that many or more, so the page
says whether it holds 435 is not known. The R17 file of 2026-11-10 reads the beast's stash line at 246 observations: under 435, said as more
than the market showed. The Farric Wolf Alpha's ≈316 stay under their count.
"""

from types import SimpleNamespace

from items_support import DATA

from crafting_system.actions import ChaosOrb
from crafting_system.actions.beast_mods import BeastSideSwap
from crafting_system.actions.imprint import Restore
from crafting_system.cli import _route_tiers
from crafting_system.cli._price_marks import PriceUse, supply_words, use_line
from crafting_system.cli._route_view import _Column, _rare_uses, _View, _words, priced_lines
from crafting_system.items import Side
from crafting_system.planner._offers import Offer, PricedOffer
from crafting_system.planner._proof_words import _guide_words
from crafting_system.prices.provenance import HISTORY, OBSERVATIONS, TRADE, Provenance

FENUMAL = "Fenumal Plagued Arachnid"


def priced_of(action, parts):
    return PricedOffer(Offer(action.label(DATA), action, dict(action.resources(DATA))), sum(chaos for _, _, chaos, _ in parts), tuple(parts))


def use(name, uses, depth=246.0, supply="246 listings seen that day"):
    return PriceUse(name, 95.0, "poe.ninja daily rows, Allflame, 2026-07-31", depth, uses, (), None, supply)


def test_the_supply_a_reading_saw_is_said_by_what_it_counts():
    assert supply_words(Provenance(HISTORY, "Allflame", "2026-11-10", 246.0, OBSERVATIONS)) == "246 listings seen that day"
    assert supply_words(Provenance(HISTORY, "Allflame", "2026-07-31", 399.0, OBSERVATIONS)) == "at least 399 listings seen that day (poe.ninja counts no further)"
    assert supply_words(Provenance(HISTORY, "Allflame", "2026-07-31", 33_076.0)) == "33,076 units traded that day"
    assert supply_words(Provenance(TRADE, "Allflame", "2026-11-10", 5.0, listings=5)) == "5 units listed"
    assert supply_words(Provenance(TRADE, "Allflame", "2026-11-10")) is None
    line = use_line(use(FENUMAL, 435.07))
    assert line == f"{FENUMAL}: 95 Chaos, poe.ninja daily rows, Allflame, 2026-07-31, 246 listings seen that day, the plan buys about 435"


def test_a_step_that_buys_more_than_the_market_showed_says_so_and_one_within_it_says_nothing():
    restore = Restore(1)  # any action: only the parts are read
    priced = priced_of(restore, [(FENUMAL, 1, 95.0, "poe.ninja")])
    supply = {FENUMAL: use(FENUMAL, 435.07)}
    lines = priced_lines(DATA, priced, supply, 435.07)
    assert lines[0] == f"1 × {FENUMAL} 95 c"
    assert lines[1] == (
        f"{FENUMAL}: this step buys about 435 in a run, the plan about 435 in all, against 246 listings seen that day in the market reading "
        "of its price: more than that market showed, so the price may not hold"
    )
    capped = use(FENUMAL, 435.07, 399.0, supply_words(Provenance(HISTORY, "Allflame", "2026-07-31", 399.0, OBSERVATIONS)))
    assert priced_lines(DATA, priced, {FENUMAL: capped}, 435.07)[1].endswith(
        "against at least 399 listings seen that day (poe.ninja counts no further) in the market reading of its price: whether the market holds that many is not known"
    )
    assert priced_lines(DATA, priced, {FENUMAL: use(FENUMAL, 216.0)}, 216.0) == [f"1 × {FENUMAL} 95 c"]
    assert priced_lines(DATA, priced, {FENUMAL: use(FENUMAL, 435.07, None, None)}, 435.07) == [f"1 × {FENUMAL} 95 c"]  # no depth: nothing to compare


def test_rare_beasts_of_any_kind_are_named_as_beasts_and_their_price_as_a_stand_in_with_no_supply():
    swap = BeastSideSwap(Side.PREFIX)
    priced = priced_of(swap, [("Farric Wolf Alpha", 1, 2.0, "poe.ninja"), ("Chaos Orb", 3, 3.0, "a setting")])
    lines = priced_lines(DATA, priced, {}, 316.0)
    assert lines[1].startswith("3 × rare beast of any kind 3 c, paid as 3 × Chaos Orb: approximate, a fixed price the planner sets")
    assert lines[1].endswith("and no supply is known")
    assert all("Chaos Orb 3 c" not in line for line in lines)
    stand_in = PriceUse("rare beast of any kind", 1.0, "a fixed price the planner sets: no price list holds them", None, 947.3, (), paid_as="Chaos Orb")
    assert use_line(stand_in).startswith(
        "rare beast of any kind: 1 Chaos each, paid as Chaos Orbs, a fixed price the planner sets: no price list holds them, no supply known, "
        "the plan buys about 947"
    )
    assert ChaosOrb().stand_ins(DATA) == {}


def test_a_restore_rolls_no_tier(monkeypatch):
    monkeypatch.setattr(_route_tiers, "wanted_families", lambda ab, influences: [SimpleNamespace(ladder=("x",))])
    ab = SimpleNamespace(data=DATA)
    state = SimpleNamespace(flags=SimpleNamespace(influences=frozenset()))
    assert _route_tiers.tier_lines(ab, Restore(1), [state], [1.0]) == []


def test_conditions_read_one_way():
    rare = _Column("", "a rare item", (0, 0))
    life = _Column("with", "Life T1", (1, 0))
    gems = _Column("without", "+1 Gems T1", (2, 0))
    light = _Column("without", "+1 Lightning T1", (2, 1))
    assert _words([gems, light]) == "without +1 Gems T1 or +1 Lightning T1"  # neither, not "without A; B"
    assert _words([light, life, rare, gems]) == "a rare item with Life T1 and without +1 Gems T1 or +1 Lightning T1"
    assert "," not in _words([rare, life, gems])  # the ", or " between kinds of item is the only comma


def test_a_step_few_runs_reach_says_the_mean_of_every_run_first():
    # R17's step 4: ≈0.0557 uses in a run, ≈0.026% of runs come, each ≈215 times
    text = _View.uses_text(0.0557, 0.000259, True)
    assert text == "≈0.026% of runs come to this step, and such a run brings an item here ≈215 times, 1 use each time; 0.0557 in a run on average"
    assert _rare_uses(2.0, 0.5, 4.0, "1 use each time") == "50% of runs come to this step, and such a run brings an item here 4 times, 1 use each time; 2 in a run on average"
    assert _View.uses_text(3.0, 1.0, True) == "an item comes to this step 3 times in a run that reaches it, 1 use each time"


def test_the_guide_at_0_and_a_hair_below_the_plan_read_by_their_difference():
    assert _guide_words(10.0, 0.0) == " It costs 10.00 Chaos in all, 10.00 Chaos more than the guide's route at 0.00 Chaos: this plan is dearer than the guide's."
    words = _guide_words(1_002.0, 1_000.0)
    assert "1.00 times" not in words and "2.00 Chaos more than the guide's route at 1,000.00 Chaos (0.20% more)" in words
    assert "1.80 times" in _guide_words(59_734.75, 33_140.41)


def test_a_beast_count_at_poe_ninjas_cap_is_a_least_number_and_a_stash_line_is_read_as_it_is():
    from crafting_system.prices.provenance import STASH, capped
    from crafting_system.prices.week_snapshot import _seen

    assert _seen(399) == "at least 399" and _seen(246) == "246"
    assert capped(Provenance(HISTORY, "Allflame", "2026-07-31", 399.0, OBSERVATIONS))
    assert not capped(Provenance(STASH, "Allflame", "2026-11-10", 1_200.0, OBSERVATIONS))  # a base's stash line: not shown to be capped (#930)
    assert supply_words(Provenance(STASH, "Allflame", "2026-11-10", 1_200.0, OBSERVATIONS)) == "1,200 listings seen that day"
