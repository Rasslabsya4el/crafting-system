"""The six beast influence recipes ("Add a Mod to a <influence> Item") as a method of the planner (#1196, OR-37: the B2 grill put them in
batch B2, a beta method), planned through the entry and the envelope search on the hand-typed Contract Helmet of `influence_support.py`.

The recipe of an influence adds one mod of that influence to a rare item that holds it, drawn from the pool of the influence's Exalted Orb
(`influence_beast.adds_a_mod_of_that_influence`, approximate: no source says which mod it adds). One use consumes the influence's red beast,
a Craicic Maw and two rare beasts of any kind, priced as Chaos Orbs (`influence_beast.recipes`): `b = 1 + 1 + 2 = 4` Chaos with every beast at
1 Chaos. The start is a bought rare helmet of item level 84 holding the Plain prefix, at `S` Chaos.

* A Shaper start, the goal the top Shaper prefix P3. The Shaper pool at item level 84 is the prefix family P (P1 300, P2 300, P3 200: 800)
  and the suffix family S (S1 500, S2 500: 1,000), 1,800 in all. One recipe gives P3 with chance 200/1,800 = 1/9, P1 or P2 with 600/1,800 =
  1/3 (P is then held at the wrong tier and no method removes it: bought again), and S with 1,000/1,800 = 5/9. With S held, the next recipe
  draws from P alone: P3 with chance 200/800 = 1/4, else P is lost. So `W = b + (3/4)(S + V)` (cheaper than buying again while
  `b < (1/4)(S + V)`) and `V = b + (1/3)(S + V) + (5/9)W`, `V = (56/9)b + 3S`: 174.89 at b = 4, S = 50.
* An uninfluenced start, with the influenced Exalted Orbs too. Shaper's Exalted Orb (at `e`) adds the influence and draws from the same pool,
  so the first draw is the orb's and the second the recipe's: `V = e + (1/3)(S + V) + (5/9)(b + (3/4)(S + V))`, `V = 4e + (20/9)b + 3S`:
  198.89 at e = 10. With the orb alone (#818) the plan is `9e + 8S` = 490.

The lower bound of the method: on a start shape that holds the influence, the recipe keeps every mod and adds one drawn mod, and its class
declares the draw of the shape (`added_draw`, together over the open sides as an Exalted Orb draws), so the offers' floors class it ADD with
the bound of one added mod (`declared_add_bound`); on a shape without the influence it is refused everywhere and stays TERMINAL (its floor is
its price). The search proves each plan exact: its last standing has its lower figure at the plan's cost, and no standing is above it.
"""

import dataclasses
import datetime

import pytest
from influence_support import HELMET, HIGH, INFLUENCE_DATA, OLD, P1, P2, P3, PLAIN, S1, S2, helmet, roll
from test_cli_offers import with_currency_names

from crafting_system.actions import NotApplicableError, catalog, kinds
from crafting_system.items import Influence
from crafting_system.planner import PlanSettings, plan_target
from crafting_system.planner import _envelope
from crafting_system.planner._offer_kinds import ADD, TERMINAL, _kind_of
from crafting_system.planner._offers import Offer, PricedOffer
from crafting_system.prices import PriceFile
from crafting_system.prices.price_file import PriceEntry
from crafting_system.prices.provenance import EXCHANGE, Provenance
from crafting_system.targets import load_target

DATA = with_currency_names(INFLUENCE_DATA)
S = 50.0
B = 4.0  # one recipe: the red beast, a Craicic Maw and two rare beasts at 1 Chaos each
RECIPES = ("beast-influence-recipe",)  # the run's methods setting (#405: a target names none)
BEASTS = ("Fenumal Devourer", "Saqawine Blood Viper", "Farric Goliath", "Craicic Watcher", "Fenumal Queen", "Fenumal Scrabbler", "Craicic Maw")

TARGET = """\
base: Contract Helmet
item_level: {level}
{influence}requirements:
  - family: ContractHelmetShaperP
    mod: {mod}
start_item:
  rarity: rare
  mods:
    - mod: ContractHelmetPlain1
      values: [1, 5]
start: bought
"""


@pytest.fixture(autouse=True)
def every_shared_kernel_checked(monkeypatch):
    monkeypatch.setattr(_envelope, "CHECK_SHARED", True)  # the search builds every kernel it shares by key again and compares (#886)


def _prices(beast: float = 1.0, **chaos: float) -> PriceFile:
    day = "2026-10-30"
    entry = lambda value: PriceEntry(value, "poe.ninja", None, None, Provenance(EXCHANGE, "Test", day, 1e9))  # noqa: E731
    orbs = {f"{influence.value.capitalize()}'s Exalted Orb": entry(chaos.get(influence.value, 1000.0)) for influence in Influence}
    beasts = {name: entry(beast) for name in BEASTS}
    return PriceFile("Test", datetime.datetime(2026, 10, 30, tzinfo=datetime.UTC), 300.0, {**orbs, **beasts, "Chaos Orb": entry(1.0)})


def _target(tmp_path, mod: str = P3, influence: str = "shaper", level: int = 84, methods: tuple[str, ...] = RECIPES):
    path = tmp_path / "helmet.yaml"
    text = TARGET.format(level=level, mod=mod, influence=f"influence: [{influence}]\n" if influence else "")
    path.write_text(text, encoding="utf-8")
    return dataclasses.replace(load_target(path, DATA), actions=methods)


def _plan(target, prices: PriceFile, seen: list | None = None):
    settings = PlanSettings(recipe_starts=False, start_price=S, solver="envelope", watch=None if seen is None else seen.append)
    return plan_target(DATA, target, prices, settings)


def test_the_beast_influence_recipe_is_a_planner_kind_offered_by_default():
    (kind,) = [each for each in kinds() if each.name == "beast-influence-recipe"]
    assert kind.planner and not kind.opt_in  # a beta method, offered by default (OR-37, OR-41)


def test_recipes_on_a_shaper_start_until_the_top_shaper_prefix_cost_56b_over_9_plus_3s(tmp_path):
    target = _target(tmp_path)
    assert target.base_id == HELMET
    seen: list = []
    plan = _plan(target, _prices(), seen)
    expected = 56 * B / 9 + 3 * S
    assert plan.mean_remaining == pytest.approx(expected, rel=1e-9)
    assert seen and all(standing.lower <= expected * (1 + 1e-9) for standing in seen)
    assert seen[-1].lower == pytest.approx(expected, rel=1e-9)  # proved: the bound met the plan


def test_a_shapers_exalted_orb_then_the_shaper_recipe_cost_4e_plus_20b_over_9_plus_3s(tmp_path):
    target = _target(tmp_path, influence="", methods=("influenced-exalted-orb", *RECIPES))
    seen: list = []
    plan = _plan(target, _prices(shaper=10.0), seen)
    expected = 4 * 10.0 + 20 * B / 9 + 3 * S
    assert plan.mean_remaining == pytest.approx(expected, rel=1e-9)
    assert expected < 9 * 10.0 + 8 * S  # cheaper than the orb alone (#818)
    assert seen[-1].lower == pytest.approx(expected, rel=1e-9)


def test_the_answer_names_the_recipe_claim_as_approximate(tmp_path):
    from crafting_system.cli._marking import approximate_inputs

    plan = _plan(_target(tmp_path), _prices())
    claims = {item.claim for item in approximate_inputs(plan, plan.policy, DATA)}
    assert "influence_beast.adds_a_mod_of_that_influence" in claims


def test_the_recipes_are_listed_for_the_influences_the_item_may_hold(tmp_path):
    shaper = _target(tmp_path).start_item
    listed = lambda item: {action.influence for action in catalog(DATA, item, planner_only=True, names=RECIPES)}  # noqa: E731
    everything = set(Influence)
    assert listed(shaper) == everything  # an Awakener's Orb may add a second influence from item level 68
    assert listed(dataclasses.replace(shaper, influences=frozenset())) == everything  # an influenced Exalted Orb may give one
    assert listed(dataclasses.replace(shaper, item_level=67)) == {Influence.SHAPER}  # neither orb works below 68
    assert listed(dataclasses.replace(shaper, influences=frozenset({Influence.SHAPER, Influence.ELDER}))) == {Influence.SHAPER, Influence.ELDER}
    assert listed(dataclasses.replace(shaper, influences=frozenset(), item_level=67)) == set()
    assert listed(dataclasses.replace(shaper, corrupted=True)) == set()
    fractured = dataclasses.replace(shaper, influences=frozenset(), mods=tuple(dataclasses.replace(entry, fractured=True) for entry in shaper.mods))
    assert listed(fractured) == set()


def test_a_class_with_no_influence_key_lists_no_recipe_and_says_it_is_a_model_gap(tmp_path):
    from crafting_system.actions.catalog import catalog_kinds

    start = dataclasses.replace(_target(tmp_path).start_item, influences=frozenset())
    jewel = dataclasses.replace(DATA.base_items[HELMET], item_class="Jewel")
    data = dataclasses.replace(DATA, base_items={**DATA.base_items, HELMET: jewel})
    gaps: list = []
    assert tuple(catalog_kinds(data, start, planner_only=True, names=RECIPES, gaps=gaps)) == ()
    assert [gap.kind for gap in gaps] == ["beast-influence-recipe"]


def test_the_recipe_is_an_addition_on_a_shape_with_its_influence_and_terminal_without(tmp_path):
    start = _target(tmp_path).start_item
    (shaper,) = [action for action in catalog(DATA, start, planner_only=True, names=RECIPES) if action.influence is Influence.SHAPER]
    priced = PricedOffer(Offer(shaper.label(), shaper, {}), B, ())
    assert _kind_of(DATA, start, priced)[0] == ADD
    assert _kind_of(DATA, dataclasses.replace(start, influences=frozenset()), priced)[0] == TERMINAL  # refused on the whole shape
    draw = shaper.added_draw(DATA, start)
    assert draw is not None and draw.together
    weights = {entry.mod.id: entry.weight for family in draw.pool for entry in family.mods}
    assert sum(weights.values()) == 1800 and weights[P3] == 200  # the Shaper pool of the bare helmet: P 800, S 1,000


def test_the_declared_draw_is_what_the_recipe_does_at_every_member_of_the_shape():
    """The contract of `Action.added_draw` (`check_added_draw`) at the members of the Shaper helmet's shape: the flags kept, one mod added, drawn by
    the declared weights over the sides with room together; a member with the prefix side full draws a suffix, one with P held draws S."""
    from contract_support import check_added_draw, finished

    from crafting_system.actions import BeastInfluenceRecipe

    recipe, shaper = BeastInfluenceRecipe(Influence.SHAPER), frozenset({Influence.SHAPER})
    checked = 0
    for prefixes in ((), (PLAIN,), (P1,), (PLAIN, P2), (PLAIN, P3, OLD)):
        for suffixes in ((), (S1,), (S2, HIGH)):
            item = helmet(*(roll(mod_id, 1) for mod_id in (*prefixes, *suffixes)), influences=shaper)
            try:
                outcomes = recipe.outcomes(DATA, item)
            except NotApplicableError:
                continue
            check_added_draw(recipe, item, finished(outcomes, DATA), DATA)
            checked += 1
    assert checked == 9  # the six members that hold both P and S draw nothing: refused
    # members with a crafted metamod: the Attack block keeps its mods out of the draw, and a side lock still lets its open slots fill
    for crafted in ("IntMasterItemGenerationCannotRollAttackAffixes", "StrMasterItemGenerationCannotChangePrefixes"):
        item = helmet(roll(PLAIN, 1), roll(crafted, 1, crafted=True), influences=shaper)
        check_added_draw(recipe, item, finished(recipe.outcomes(DATA, item), DATA), DATA)
