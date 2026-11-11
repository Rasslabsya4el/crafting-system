"""A bought start item whose mods the target does not name is the item the market sells: a draw of the orb that makes its rarity (#640, ADR-0064; OR-4, OR-6, OR-17).

Toy boots whose pool is worked by hand (`listing_support`): a Magic listing is what an Orb of Alteration leaves (1 or 2 mods, 1/2 each, at the game
weights), a Rare one what an Orb of Alchemy leaves (4, 5 or 6 mods, 8:3:1), exact `Fraction`s against a walk of every draw order. The planner opens
with that draw and decides on each outcome: an Augmentation where the item holds one wanted mod, an Alteration where it holds two.
"""

import dataclasses
import itertools
from fractions import Fraction

import pytest
from listing_support import (
    ALTERATION,
    AUGMENTATION,
    BOOTS_ID,
    ITEM_LEVEL,
    LISTING,
    magic_sets,
    magic_toy,
    prices,
    rare_sets,
    rare_toy,
    target,
)

from crafting_system.abstraction import Status
from crafting_system.actions import DRAW_LABEL, AlterationOrb, NotApplicableError, OpenListing, unopened_listing
from crafting_system.cli import evaluate_route, make_plan, parse_route
from crafting_system.cli._offers import DRAW_COST_SHARE, RESTART
from crafting_system.cli._plan import PlanError
from crafting_system.items import Item, ItemError, Rarity
from crafting_system.items.quality import PlainQuality
from crafting_system.items.sockets import SocketColour, Sockets
from crafting_system.targets import StartKind, start_price_key

MAGIC = magic_toy()
RARE = rare_toy()


def listing_of(data, rarity: Rarity, **fields) -> Item:
    return Item.build(data, base_id=BOOTS_ID, item_level=ITEM_LEVEL, rarity=rarity, **fields)


def by_mod(outcomes) -> dict[frozenset[str], Fraction]:
    """The distribution of the sets of mods the draw leaves (the toy has one mod to a family, so the family names the mod)."""
    found: dict[frozenset[str], Fraction] = {}
    for outcome, chance in outcomes.distribution(lambda mod: mod.id).items():
        assert all(count == 1 for _, count in outcome)
        key = frozenset(name for name, _ in outcome)
        found[key] = found.get(key, Fraction(0)) + chance
    return found


# --- the draw: exact odds against the hand ------------------------------------------------------------------------------------------


def test_the_hand_oracle_of_the_magic_toy_is_a_distribution():
    assert sum(magic_sets().values()) == 1
    assert magic_sets()[frozenset({"ToyA", "ToyC"})] == Fraction(1, 8)  # 1/2 * (3/10 * 2/6 + 2/10 * 3/4)
    assert magic_sets()[frozenset({"ToyB"})] == Fraction(1, 20)  # 1/2 * 1/10


def test_a_magic_listing_is_what_an_alteration_leaves_with_the_game_weights():
    listing = unopened_listing(MAGIC, listing_of(MAGIC, Rarity.MAGIC))
    opened = OpenListing(Rarity.MAGIC).outcomes(MAGIC, listing)

    assert by_mod(opened) == magic_sets()
    assert opened.totals == {1: Fraction(1, 2), 2: Fraction(1, 2)}
    assert opened.retained.rarity is Rarity.MAGIC and not opened.retained.unopened
    assert by_mod(opened) == by_mod(AlterationOrb().outcomes(MAGIC, listing_of(MAGIC, Rarity.MAGIC)))  # the orb on the item opened: the same law


def test_a_rare_listing_is_what_an_alchemy_orb_leaves_with_the_game_weights():
    listing = unopened_listing(RARE, listing_of(RARE, Rarity.RARE))
    opened = OpenListing(Rarity.RARE).outcomes(RARE, listing)

    assert by_mod(opened) == rare_sets()
    assert sum(rare_sets().values()) == 1
    assert opened.totals == {4: Fraction(2, 3), 5: Fraction(1, 4), 6: Fraction(1, 12)}
    assert opened.retained.rarity is Rarity.RARE and not opened.retained.unopened
    sizes = {len(each) for each in rare_sets()}
    assert sizes == {4, 5, 6} and rare_sets()[frozenset({"ToyP1", "ToyP2", "ToyP3", "ToyS1", "ToyS2", "ToyS3"})] == Fraction(1, 12)


def test_the_influence_of_the_listing_is_kept_by_the_draw(request):
    listing = unopened_listing(MAGIC, listing_of(MAGIC, Rarity.MAGIC))

    assert listing.rarity is Rarity.NORMAL and listing.unopened and not listing.mods
    assert OpenListing(Rarity.MAGIC).outcomes(MAGIC, listing).retained.influences == listing.influences


# --- the properties of the listing are kept by the draw, as the game's Alteration and Alchemy keep them (ADR-0064) ---------------------


PROPERTIES = {
    "quality": {"quality": PlainQuality(20)},
    "memory strands": {"memory_strands": 40},
    "sockets": {"sockets": Sockets((SocketColour.RED, SocketColour.WHITE), (2,))},
}


@pytest.mark.parametrize("rarity, toy", [(Rarity.MAGIC, MAGIC), (Rarity.RARE, RARE)], ids=["magic", "rare"])
@pytest.mark.parametrize("name", sorted(PROPERTIES))
def test_a_bought_start_with_quality_strands_or_sockets_is_drawn_and_keeps_them(rarity, toy, name):
    fields = PROPERTIES[name]
    listing = unopened_listing(toy, listing_of(toy, rarity, **fields))

    assert listing is not None and listing.unopened  # drawn: the rule asks for no mod, nothing corrupted, no imprint and no offer, nothing else
    opened = OpenListing(rarity).outcomes(toy, listing)
    for field, held in fields.items():
        assert getattr(listing, field) == held and getattr(opened.retained, field) == held  # the orb does not touch them, so neither does the draw
    assert (by_mod(opened) == magic_sets()) if rarity is Rarity.MAGIC else (by_mod(opened) == rare_sets())  # the odds are those of the bare item


@pytest.mark.parametrize("rarity", [Rarity.MAGIC, Rarity.RARE])
def test_a_bought_start_with_an_enchantment_is_drawn_and_keeps_it(rarity):
    from enchant_support import ARMOUR_EXTRA_SLOT, BODY, DATA

    start = Item.build(DATA, base_id=BODY, item_level=84, rarity=rarity, enchantment=ARMOUR_EXTRA_SLOT)
    listing = unopened_listing(DATA, start)

    assert listing is not None and listing.enchantment == ARMOUR_EXTRA_SLOT
    assert OpenListing(rarity).outcomes(DATA, listing).retained.enchantment == ARMOUR_EXTRA_SLOT


def test_a_plan_from_a_bought_magic_start_with_quality_and_sockets_opens_with_the_draw():
    aim = target(MAGIC)
    held = dataclasses.replace(aim, start_item=aim.start_item.changed(MAGIC, **PROPERTIES["quality"], **PROPERTIES["sockets"]))
    plan = make_plan(MAGIC, held, prices(start_price_key(MAGIC, held)))

    assert plan.start.flags.unopened and plan.policy[plan.start].label == DRAW_LABEL
    assert plan.abstraction.compress(plan.target.start_item).flags.unopened is False  # the item the draw opens to is the start item as written


def test_a_bought_start_with_memory_strands_is_refused_plainly_before_any_solve():
    aim = target(MAGIC)
    held = dataclasses.replace(aim, start_item=aim.start_item.changed(MAGIC, **PROPERTIES["memory strands"]))

    with pytest.raises(PlanError, match="Memory Strands are on .* which the planner cannot plan yet"):  # the same plain refusal as for any start with strands
        make_plan(MAGIC, held, prices(start_price_key(MAGIC, held)))

# --- the rule: which starts are drawn ----------------------------------------------------------------------------------------------


def test_only_a_magic_or_rare_start_without_a_mod_is_a_listing():
    assert unopened_listing(MAGIC, listing_of(MAGIC, Rarity.NORMAL)) is None  # normal: no mods, as before
    assert unopened_listing(MAGIC, listing_of(MAGIC, Rarity.MAGIC)) is not None
    assert unopened_listing(MAGIC, listing_of(MAGIC, Rarity.RARE)) is not None
    named = listing_of(MAGIC, Rarity.MAGIC, mods=(MAGIC_MOD(),))
    assert unopened_listing(MAGIC, named) is None  # the target names a mod: no draw
    assert unopened_listing(MAGIC, listing_of(MAGIC, Rarity.MAGIC, corrupted=True)) is None


def MAGIC_MOD():
    from crafting_system.items import ExplicitMod

    return ExplicitMod("ToyA", (1,))


def test_an_unopened_item_is_a_normal_item_with_no_mod():
    with pytest.raises(ItemError):
        listing_of(MAGIC, Rarity.MAGIC, unopened=True)
    with pytest.raises(ItemError):
        listing_of(MAGIC, Rarity.NORMAL, unopened=True, mods=(MAGIC_MOD(),))


def test_only_the_draw_works_on_an_unopened_item_and_the_draw_works_on_nothing_else():
    data = MAGIC
    plan = make_plan(data, target(data), prices(start_price_key(data, target(data))))
    ab = plan.abstraction
    alteration = next(p.offer.action for p in plan.offers if p.label == "Orb of Alteration")
    draw = next(p.offer.action for p in plan.offers if p.offer.action.opens_listing)

    assert plan.start.flags.unopened and plan.start.flags.rarity is Rarity.NORMAL
    with pytest.raises(NotApplicableError):
        ab.kernel(plan.start, alteration)
    opened = next(state for state in ab.kernel(plan.start, draw))
    assert not opened.flags.unopened
    with pytest.raises(NotApplicableError):
        ab.kernel(opened, draw)  # not a free reroll: the listing is reached by the restart only


# --- the planner: one rule, the first decision on each outcome ----------------------------------------------------------------------


def test_the_plan_opens_with_the_draw_and_follows_the_rule_on_each_outcome():
    data = MAGIC
    aim = target(data)
    plan = make_plan(data, aim, prices(start_price_key(data, aim)))
    draw = plan.policy[plan.start]
    kernel = plan.abstraction.kernel(plan.start, next(p.offer.action for p in plan.offers if p.offer.action.opens_listing))

    assert draw.label == DRAW_LABEL
    assert sum(kernel.values()) == 1
    chosen = {}
    for state in kernel:
        mods = len(state.slots)  # the junk is kept as slots while an enabled action adds mods, so a slot is a mod
        wanted = sum(status is Status.PASSING for status in state.status)
        chosen[(mods, wanted)] = {plan.policy[state].label if state in plan.policy else "goal"} | chosen.get((mods, wanted), set())
    assert chosen[(1, 1)] == {"Orb of Augmentation"}  # one mod and it is wanted: the Augmentation keeps it and adds the other
    assert chosen[(1, 0)] == {"Orb of Alteration"}  # one mod that is not wanted: nothing to keep
    assert chosen[(2, 0)] == {"Orb of Alteration"} and chosen[(2, 1)] == {"Orb of Alteration"}  # two mods: an Augmentation is not legal
    assert chosen[(2, 2)] == {"goal"}


def test_the_mean_is_the_hand_solved_one_plus_the_price_of_the_draw():
    """The values of the outcomes by hand: u is the mean cost after an Alteration has landed; the planner's start value is that plus the draw."""
    data = MAGIC
    aim = target(data)
    plan = make_plan(data, aim, prices(start_price_key(data, aim)))
    sets = magic_sets()
    a, g = Fraction(ALTERATION), Fraction(AUGMENTATION)
    goal = frozenset({"ToyA", "ToyC"})

    def mean_after_alteration(augment_a: bool, augment_c: bool) -> Fraction:
        # u = sum P(O) f(O); f = 0 at the goal, 1 Alteration + u elsewhere, and where one wanted mod is held and an Augmentation is chosen,
        # the Augmentation (it adds the other side's mod in proportion to the weights) and then an Alteration + u unless it lands the goal
        coefficient, constant = Fraction(0), Fraction(0)
        for held, chance in sets.items():
            if held == goal:
                continue
            if held == frozenset({"ToyA"}) and augment_a:  # adds a suffix: C with 2/6 lands the goal, D with 4/6 gives {A, D}, an Alteration away
                coefficient += chance * Fraction(4, 6)
                constant += chance * (g + Fraction(4, 6) * a)
            elif held == frozenset({"ToyC"}) and augment_c:  # adds a prefix: A with 3/4 lands the goal, B with 1/4 gives {B, C}
                coefficient += chance * Fraction(1, 4)
                constant += chance * (g + Fraction(1, 4) * a)
            else:
                coefficient += chance
                constant += chance * a
        return constant / (1 - coefficient)

    hand = min(mean_after_alteration(x, y) for x, y in itertools.product((False, True), repeat=2))
    draw_cost = DRAW_COST_SHARE * AUGMENTATION  # the cheapest offer that costs something

    assert plan.solution.values[plan.start] == pytest.approx(float(hand) + draw_cost, rel=1e-9)
    assert hand == mean_after_alteration(True, True)  # both Augmentations pay: they are cheaper and keep a wanted mod


def test_the_restart_buys_the_listing_again_and_draws_again():
    data = MAGIC
    aim = target(data)
    plan = make_plan(data, aim, prices(start_price_key(data, aim)))
    restart = next(p for p in plan.offers if p.label == RESTART)

    assert restart.cost == LISTING and plan.start_price.chaos == LISTING
    assert restart.offer.action.sample(None).unopened  # the item that comes back is the unopened listing


def test_a_given_start_item_and_a_start_that_names_a_mod_are_not_drawn():
    data = MAGIC
    given = make_plan(data, dataclasses.replace(target(data), start=StartKind.GIVEN), prices(None))
    assert not given.start.flags.unopened and not any(p.offer.action.opens_listing for p in given.offers)

    normal = target(data, rarity="normal", actions="transmutation-orb, alteration-orb, augmentation-orb")
    plan = make_plan(data, normal, prices(start_price_key(data, normal)) )
    assert not plan.start.flags.unopened and not any(p.offer.action.opens_listing for p in plan.offers)

    named = target(data, mods="  mods:\n    - mod: ToyB\n      values: [1]\n")
    plan = make_plan(data, named, prices(start_price_key(data, named)))
    assert not plan.start.flags.unopened and not any(p.offer.action.opens_listing for p in plan.offers)


def test_a_rare_start_is_drawn_like_an_alchemy_orb_and_the_plan_goes_on_from_each_outcome():
    data = RARE
    aim = target(data, rarity="rare", actions="chaos-orb", wanted=("ToyP3", "ToyS3"))
    entries = prices(start_price_key(data, aim))
    entries.prices["Chaos Orb"] = type(entries.prices["Orb of Alteration"])(1.0, "fixture")
    plan = make_plan(data, aim, entries)

    assert plan.start.flags.unopened
    assert plan.policy[plan.start].label == DRAW_LABEL
    assert {p.label for p in plan.offers} >= {DRAW_LABEL, "Chaos Orb", RESTART}


# --- a given route takes the draw first, whatever it says --------------------------------------------------------------------------


def test_a_given_route_takes_the_draw_first_and_needs_no_rule_for_it():
    data = MAGIC
    aim = target(data)
    plan = make_plan(data, aim, prices(start_price_key(data, aim)), judges_route=True)
    route = parse_route(
        "rules:\n  - when: {rarity: magic}\n    do: Orb of Alteration\n", plan, data
    )  # the guide: roll Alterations until the goal; it says nothing of buying

    result = evaluate_route(plan, route, data)

    assert route.rules[0].do == DRAW_LABEL and result.gaps == ()
    assert result.risk.success_probability.value == pytest.approx(1.0)
    assert plan.solution.values[plan.start] <= result.risk.mean.value + 1e-9  # the solver is no dearer than the guide's Alteration spam


# --- the simulator starts from the unopened listing ----------------------------------------------------------------------------------


def test_a_simulated_craft_starts_from_the_listing_and_agrees_with_the_computed_mean():
    from crafting_system.cli._verify import verify

    data = MAGIC
    aim = target(data)
    plan = make_plan(data, aim, prices(start_price_key(data, aim)))

    assert plan.simulated_start.unopened and not aim.start_item.unopened
    check = verify(data, plan, runs=4000, seed=7)
    assert check.agrees, check.reason


def test_the_bound_pruning_bounds_the_offers_on_the_opened_item_and_keeps_the_draw(monkeypatch):
    """The pruning of many offers (R08, R09) sees the unopened start as the item it opens into: the same values as the unpruned solve."""
    from crafting_system.cli import _plan

    data = RARE
    aim = target(data, rarity="rare", actions="chaos-orb", wanted=("ToyP3", "ToyS3"))
    entries = prices(start_price_key(data, aim))
    entries.prices["Chaos Orb"] = type(entries.prices["Orb of Alteration"])(1.0, "fixture")
    whole = make_plan(data, aim, entries, solver="object")  # the bound pruning is the object solver's path (#535)
    monkeypatch.setattr(_plan, "MIN_OFFERS_TO_PRUNE", 2)
    pruned = make_plan(data, aim, entries, solver="object")

    assert pruned.pruned is not None and not pruned.pruned.fell_back
    assert DRAW_LABEL in {offer.label for offer in pruned.pruned.used}
    assert pruned.solution.values[pruned.start] == pytest.approx(whole.solution.values[whole.start], rel=1e-9)
