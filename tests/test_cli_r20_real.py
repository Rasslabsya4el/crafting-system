"""R20 on the real 3.29.3.3 dump, at its committed prices, with nothing solved (ticket #150).

R20 is the Shaper/Elder Eternal Burgonet of a Righteous Fire Trap and Mine build: the Essence of Horror's 30% more Elemental Damage,
the Trap and Mine Damage and Burning Damage supports and the Concentrated Effect support, from a bought dual-influenced helmet (its
Awakener's Orb is batch B3). These check the target, the start price, the offers, the given route, and the chance of the guide's two
Harvest steps beside the guide's own 16% and 15%. The policy (CLI, `--verify`, the solver's mean against the given route's) is a heavy
run: `tests/test_cli_r20_heavy.py`. These skip without the cached dump.
"""

from fractions import Fraction
from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system.actions.harvest import HarvestReforge
from crafting_system.actions.harvest_influence import HarvestReforgeInfluence
from crafting_system.cli import load_route, make_plan
from crafting_system.items import ExplicitMod, Influence, Item, Rarity
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "examples" / "targets" / "r20-rf-helmet.yaml"
ROUTE = ROOT / "examples" / "routes" / "r20-rf-helmet.yaml"
PRICES = ROOT / "tests" / "fixtures" / "prices" / "b2-r20-beasts-2026-11-12.json"
START = "Eternal Burgonet, item level 86-100, Shaper/Elder influence"
HELMET = "Metadata/Items/Armours/Helmets/HelmetStr11"
ROUTE_ACTIONS = {
    "Essence of Horror", "Orb of Annulment", "Bench craft Suffixes Cannot Be Changed", "Harvest Reforge Fire",
    "Beastcraft Wild Bristle Matron (add a metamod)", "Harvest Reforge Influence",
}
ESSENCE = "SocketedGemsDealMoreElementalDamageEssence1"
TRAP_MINE = "MineDamageTrapUber3"
BURNING = "IncreasedBurningDamageSupportedUber3"
CONCENTRATED = "AreaDamageSupportedUber3"
LOCK = "DexMasterItemGenerationCannotChangeSuffixes"  # "Suffixes Cannot Be Changed", a crafted prefix
# the guide's own odds (docs/research/2026-10-30-5-reference-routes.md, R20): step 4 "about 16% for any tier and 5% for the top tier",
# step 5 "about 15%" for Concentrated Effect (no tier)
GUIDE = {"step 4, Burning Damage": (0.16, 0.05), "step 5, Concentrated Effect": (0.15, None)}


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def target(data):
    return load_target(TARGET, data)


@pytest.fixture(scope="module")
def plan(data, target):
    return make_plan(data, target, load_price_file(target.price_file), solve_it=False)


def test_the_target_reads_its_committed_price_file_and_asks_the_four_mods(target):
    assert target.price_file.resolve() == PRICES.resolve()
    assert target.item_level == 86 and target.influences == frozenset({Influence.SHAPER, Influence.ELDER})
    asked = {leaf.mod_ids for leaf in target.requirements}
    assert asked == {frozenset({mod}) for mod in (ESSENCE, TRAP_MINE, BURNING, CONCENTRATED)}


def test_the_start_helmet_costs_its_committed_stand_in_price(plan):
    entry = load_price_file(PRICES).prices[START]
    assert plan.start_price.name == START
    assert plan.start_price.chaos == pytest.approx(entry.chaos) == pytest.approx(1125.0)
    assert entry.source == "hand"


def test_the_plan_offers_the_route_actions_all_priced(plan):
    costs = {priced.label: priced.cost for priced in plan.offers}
    assert ROUTE_ACTIONS <= set(costs)
    assert not [limit for limit in plan.limits if limit.kind == "unpriced"]
    # the Matron: the beast (poe.ninja Standard, 254 c) and three rare beasts of any kind at 1 Chaos each
    assert costs["Beastcraft Wild Bristle Matron (add a metamod)"] == pytest.approx(254.0 + 3)
    # the bench lock costs two Divine Orbs, which is why the guide's step 5 takes the beast
    assert costs["Bench craft Suffixes Cannot Be Changed"] > costs["Beastcraft Wild Bristle Matron (add a metamod)"]


def test_the_given_route_reads_against_the_offers(plan, data):
    route = load_route(ROUTE, plan, data)
    assert route.skip_refused
    assert ROUTE_ACTIONS <= {rule.do for rule in route.rules}


# --- the guide's 16% and 15% beside ours --------------------------------------------------------------------------------------------


def roll(data, mod_id: str, **flags) -> ExplicitMod:
    return ExplicitMod(mod_id, tuple(min(s.min, s.max) for s in data.mods[mod_id].stats), **flags)


def helmet(data, *mod_ids: str) -> Item:
    mods = tuple(roll(data, mod_id, crafted=mod_id == LOCK) for mod_id in mod_ids)
    return Item.build(data, base_id=HELMET, item_level=86, rarity=Rarity.RARE, influences=frozenset({Influence.SHAPER, Influence.ELDER}), mods=mods)


def chance_of(outcomes, top: str) -> tuple[float, float]:
    """The chance the outcome adds a tier of the support of `top` (any tier) and the chance it adds `top`.

    The tiers are the ids that differ from `top` in the last digit only (`...Uber1` to `...Uber3`): the family of Burning Damage,
    `HelmetAilmentUber`, also holds the other ailment supports, which are not the guide's mod.
    """
    stem = top.rstrip("0123456789")
    shown = outcomes.distribution(lambda mod: mod.id if mod.id.rstrip("0123456789") == stem else None)
    any_tier = sum((chance for outcome, chance in shown.items() if any(label is not None for label, _ in outcome)), Fraction(0))
    top_tier = sum((chance for outcome, chance in shown.items() if any(label == top for label, _ in outcome)), Fraction(0))
    return float(any_tier), float(top_tier)


def test_the_guides_two_harvest_steps_beside_ours(data):
    """Step 4 on the guide's item (the two suffixes and the lock), step 5 on the three suffixes and the lock.

    Ours for step 4 agrees with the guide (17.3% and 5.8% against 16% and 5%); ours for step 5 is 9.9% against the guide's 15%
    (#814 holds the check against Craft of Exile).
    """
    step_4 = HarvestReforge("fire").outcomes(data, helmet(data, ESSENCE, TRAP_MINE, LOCK))
    step_5 = HarvestReforgeInfluence().outcomes(data, helmet(data, ESSENCE, TRAP_MINE, BURNING, LOCK))
    ours = {
        "step 4, Burning Damage": chance_of(step_4, BURNING),
        "step 5, Concentrated Effect": chance_of(step_5, CONCENTRATED),
    }
    for step, (any_tier, top_tier) in ours.items():
        guide_any, guide_top = GUIDE[step]
        print(f"R20 {step}: guide {guide_any:.0%} any tier{'' if guide_top is None else f', {guide_top:.0%} top tier'}; ours {any_tier:.1%} any tier, {top_tier:.1%} top tier")

    assert ours["step 4, Burning Damage"] == pytest.approx((0.1730, 0.0577), abs=5e-4)
    assert ours["step 5, Concentrated Effect"] == pytest.approx((0.0994, 0.0497), abs=5e-4)
    assert ours["step 4, Burning Damage"] == pytest.approx(GUIDE["step 4, Burning Damage"], abs=0.015)
