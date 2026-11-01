"""The ends of the cost rule of a recombination (`Recombinator.resource_bounds`, ticket #221, ADR-0035).

The claims `recombinator_cost.dust_per_combine_reports_3_26`, `...gold_per_combine_reports_3_26` and `...junk_craft_halves_dust_3_26` carry the
point the plan uses and the low and high ends the reports give; the bounds are the same cost rule with each end in turn, so the answer can
tell what the cost rule alone does to the mean. The factor of an influenced input and the Gold of the two junk mods have no interval.
"""

import pytest
from test_actions_recombinator import DATA, make
from test_actions_recombinator_cost import COLD, DUST_NAME, GOLD_NAME, SHAPER, bench_currencies, junk, pair

from crafting_system.actions import Recombinator
from crafting_system.items import Rarity


def test_the_plain_cost_runs_from_the_low_to_the_high_end_of_each_claim_and_the_point_lies_between():
    _, donor = pair()
    action = Recombinator(donor)
    low, high = action.resource_bounds(DATA)
    assert low == {DUST_NAME: 25_000, GOLD_NAME: 8_000}
    assert high == {DUST_NAME: 250_000, GOLD_NAME: 20_000}
    point = action.resources(DATA)
    assert all(low[name] <= point[name] <= high[name] for name in point)


def test_an_influenced_input_scales_both_ends_by_one_and_a_half():
    donor = make(["RP25", "RS500"], Rarity.MAGIC, influences=SHAPER)
    low, high = Recombinator(donor).resource_bounds(DATA)
    assert low == {DUST_NAME: 37_500, GOLD_NAME: 12_000}
    assert high == {DUST_NAME: 375_000, GOLD_NAME: 30_000}


def test_the_junk_craft_takes_the_dust_factor_at_each_end_the_gold_gains_the_same_two_mods_and_the_bench_is_exact():
    _, donor = pair()
    low, high = junk(donor).resource_bounds(DATA)
    bench = bench_currencies(COLD, COLD)
    assert low == {DUST_NAME: 2_750, GOLD_NAME: 8_647, **bench}  # 25,000 x 0.11; 8,000 + 2 x 323.5
    assert high == {DUST_NAME: 125_000, GOLD_NAME: 20_647, **bench}  # 250,000 x 0.5; 20,000 + 647
    point = junk(donor).resources(DATA)
    assert all(low[name] <= point[name] <= high[name] for name in point)


def test_the_junk_ends_need_the_data():
    _, donor = pair()
    with pytest.raises(ValueError, match="needs the data"):
        junk(donor).resource_bounds(None)
    low, high = Recombinator(donor).resource_bounds(None)  # the plain cost needs none
    assert low[DUST_NAME] < high[DUST_NAME]
