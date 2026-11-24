"""Starting over costs the cheaper of buying the start item again or wiping the same item (OR-42, #1201).

A toy boots base worked by hand (`listing_support`): a bought Magic listing (10 c), Alterations and Augmentations to two of the three wanted mods
(prefixes A, B; suffix C), then a Regal Orb for the third. A Regal that misses leaves a Rare holding D, which no offered orb mends, so the craft
starts over. A player wipes that Rare with an Orb of Scouring and an Orb of Transmutation (1.0 + 0.2 = 1.2 c): the Scouring leaves the Normal
base, and the Transmutation draws 1 or 2 mods at the game weights, the same law as the listing's own draw (`OpenListing`), so the wipe ends where a
new listing does, in the unopened start. So the plan that wipes is, state for state, the plan of a start that costs 1.2 c to buy again.
"""

import dataclasses
import itertools
import textwrap

import pytest
from listing_support import AUGMENTATION, LISTING, magic_toy, mean_after_alteration, prices

from crafting_system.actions import start_over_wipe, unopened_listing
from crafting_system.items import ExplicitMod, Item, Rarity
from crafting_system.planner import RESTART, BuyStartItem, WipeStartItem, plan_target
from crafting_system.planner._offers import DRAW_COST_SHARE
from crafting_system.planner._prune import wipe_lands
from crafting_system.prices import PriceEntry
from crafting_system.targets import parse_target, start_price_key

DATA = magic_toy()
SCOURING = 1.0
TRANSMUTATION = 0.2
REGAL = 2.0
WIPE = SCOURING + TRANSMUTATION
WIPE_LABEL = "Start over on the same item: Orb of Scouring, then Orb of Transmutation"

TARGET = """\
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


def target(mods: str = ""):
    text = textwrap.dedent(TARGET.format(mods=mods))
    return dataclasses.replace(parse_target(text, DATA, source="toy-wipe.yaml"), actions=("alteration-orb", "augmentation-orb", "regal-orb"))


def price_file(aim, listing: float = LISTING):
    entries = prices(start_price_key(DATA, aim))
    entries.prices[start_price_key(DATA, aim)] = PriceEntry(listing, "trade-api")
    entries.prices["Orb of Scouring"] = PriceEntry(SCOURING, "fixture")
    entries.prices["Orb of Transmutation"] = PriceEntry(TRANSMUTATION, "fixture")
    entries.prices["Regal Orb"] = PriceEntry(REGAL, "fixture")
    return entries


def restarts_taken(plan) -> set[str]:
    """The labels of the ways the plan starts over (the restart, or a wipe) at the states its policy reaches."""
    return {decision.label for decision in plan.policy.values() if decision.label == RESTART or decision.label.startswith("Start over on the same item")}


def expected_uses(plan, label: str) -> float:
    """How many times a craft run by the plan's policy uses `label` on average: the visits of the absorbing chain from the start (N = (I - Q)^-1)."""
    from fractions import Fraction

    states = list(plan.policy)
    index = {state: k for k, state in enumerate(states)}
    size = len(states)
    matrix = [[Fraction(int(i == j)) for j in range(size)] for i in range(size)]
    for state in states:
        decision = plan.policy[state]
        offer = next(p for p in plan.offers if p.label == decision.label)
        kernel = {plan.start: Fraction(1)} if isinstance(offer.offer.action, BuyStartItem) else plan.abstraction.kernel(state, offer.offer.action)
        for after, chance in kernel.items():
            if after in index:
                matrix[index[after]][index[state]] -= Fraction(chance)
    # visits v solve (I - Q^T) v = e_start, by Gauss-Jordan on exact fractions
    rhs = [Fraction(int(state == plan.start)) for state in states]
    for col in range(size):
        pivot = next(r for r in range(col, size) if matrix[r][col] != 0)
        matrix[col], matrix[pivot], rhs[col], rhs[pivot] = matrix[pivot], matrix[col], rhs[pivot], rhs[col]
        for r in range(size):
            if r != col and matrix[r][col] != 0:
                factor = matrix[r][col] / matrix[col][col]
                matrix[r] = [a - factor * b for a, b in zip(matrix[r], matrix[col])]
                rhs[r] -= factor * rhs[col]
    visits = {state: rhs[k] / matrix[k][k] for k, state in enumerate(states)}
    return float(sum(v for state, v in visits.items() if plan.policy[state].label == label))


def no_wipe(aim, listing: float):
    """The price file without the Orb of Scouring: no wipe can be priced, so starting over buys the listing again."""
    entries = price_file(aim, listing)
    del entries.prices["Orb of Scouring"]
    return entries


def test_a_start_dearer_than_the_wipe_starts_over_by_wiping_and_the_mean_falls_by_the_difference():
    aim = target()
    plan = plan_target(DATA, aim, price_file(aim))
    wipe = next(p for p in plan.offers if isinstance(p.offer.action, WipeStartItem))
    as_if = plan_target(DATA, aim, no_wipe(aim, WIPE))  # a listing that costs what the wipe does
    rebuys = plan_target(DATA, aim, no_wipe(aim, LISTING))

    assert wipe.label == WIPE_LABEL and wipe.cost == pytest.approx(WIPE) and wipe.parts[0][:3] == ("Orb of Scouring", 1, SCOURING)
    assert restarts_taken(plan) == {WIPE_LABEL} and restarts_taken(rebuys) == {RESTART}  # every restart of the plan is a wipe
    assert {s for s, d in plan.policy.items() if d.label == WIPE_LABEL} == {s for s, d in rebuys.policy.items() if d.label == RESTART}
    assert plan.solution.values[plan.start] == pytest.approx(as_if.solution.values[as_if.start], rel=1e-12)
    # the mean falls by 8.8 c a restart. Each plan is optimal at its own price of starting over, so with N_r the restarts of the plan that buys
    # again and N_w the wipes of the plan that wipes (each counted on its policy's own chain), 8.8 N_r <= fall <= 8.8 N_w; here the cheaper
    # restart also makes the plan aim for the Regal more often (N_r = 2.742..., N_w = 26/9 = 2.888...)
    fall = rebuys.solution.values[rebuys.start] - plan.solution.values[plan.start]
    n_r, n_w = expected_uses(rebuys, RESTART), expected_uses(plan, WIPE_LABEL)
    assert n_w == pytest.approx(26 / 9, rel=1e-12) and 1 < n_r < n_w
    assert n_r * (LISTING - WIPE) - 1e-9 <= fall <= n_w * (LISTING - WIPE) + 1e-9


def test_a_start_cheaper_than_the_wipe_is_bought_again():
    aim = target()
    cheap = 0.5  # under the 1.2 c of the Scouring and the Transmutation
    plan = plan_target(DATA, aim, price_file(aim, listing=cheap))

    assert not any(isinstance(p.offer.action, WipeStartItem) for p in plan.offers)
    assert restarts_taken(plan) == {RESTART}
    assert plan.solution.values[plan.start] == pytest.approx(plan_target(DATA, aim, no_wipe(aim, cheap)).solution.values[plan.start], rel=1e-12)


def test_the_wipe_of_a_listing_is_a_scouring_then_the_orb_of_its_rarity_and_gives_back_the_unopened_listing():
    start = Item.build(DATA, base_id=target().base_id, item_level=86, rarity=Rarity.MAGIC)
    listing = unopened_listing(DATA, start)
    wipe = start_over_wipe(DATA, start, listing)

    assert [orb.label(DATA) for orb in wipe.orbs] == ["Orb of Scouring", "Orb of Transmutation"]
    assert wipe.scoured.rarity is Rarity.NORMAL and not wipe.scoured.unopened and not wipe.scoured.mods
    assert [orb.label(DATA) for orb in start_over_wipe(DATA, start, listing, paid=True).orbs] == ["Orb of Scouring"]  # a Normal base's price: the draw is the orb already


def test_a_fractured_start_keeps_its_fractured_mod_through_the_wipe():
    aim = target(mods="  mods:\n    - mod: ToyA\n      values: [1]\n      fractured: true\n")
    plan = plan_target(DATA, aim, price_file(aim))
    wipe = next(p for p in plan.offers if isinstance(p.offer.action, WipeStartItem))

    assert [orb.label(DATA) for orb in wipe.offer.action.wipe.orbs] == ["Orb of Scouring"]  # a Magic item holding the fractured mod: the Scouring leaves it so
    assert [entry.mod_id for entry in wipe.offer.action.sample(None).fractured_mods] == ["ToyA"]
    assert plan.start.fractured and restarts_taken(plan) == {"Start over on the same item: Orb of Scouring"}
    for state, decision in plan.policy.items():
        if decision.label == wipe.label:
            assert state.fractured == plan.start.fractured and wipe_lands(plan.abstraction, wipe.offer.action, state)


def test_a_corrupted_item_is_never_wiped():
    aim = target()
    plan = plan_target(DATA, aim, price_file(aim))
    wipe = next(p for p in plan.offers if isinstance(p.offer.action, WipeStartItem))
    failed = Item.build(
        DATA, base_id=aim.base_id, item_level=86, rarity=Rarity.RARE,
        mods=(ExplicitMod("ToyA", (1,)), ExplicitMod("ToyC", (1,)), ExplicitMod("ToyD", (1,))),
    )  # fmt: skip
    corrupted = dataclasses.replace(failed, corrupted=True)

    assert wipe_lands(plan.abstraction, wipe.offer.action, plan.abstraction.compress(failed))
    assert not wipe_lands(plan.abstraction, wipe.offer.action, plan.abstraction.compress(corrupted))
    assert start_over_wipe(DATA, corrupted, None) is None and start_over_wipe(DATA, corrupted, unopened_listing(DATA, failed)) is None


def test_the_page_names_the_wipe_as_a_step_with_its_cost():
    import html
    import re

    from crafting_system.cli import build_report
    from crafting_system.cli._route_view import route_page

    aim = target()
    plan = plan_target(DATA, aim, price_file(aim))
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", route_page(build_report(plan, DATA), DATA))))

    assert f"6. {WIPE_LABEL} Cost per use 1 × Orb of Scouring 1 c 1 × Orb of Transmutation 0.2 c total 1.2 c" in text  # its own step, with its cost
    assert "the item is started over: wiped with Orb of Scouring, then Orb of Transmutation for 1.2 c" in text  # the Regal's failure goes there
    assert "Next step the start item again, the same item wiped → step 2" in text
    assert "Restart: buy" not in text  # no restart buys the listing again
