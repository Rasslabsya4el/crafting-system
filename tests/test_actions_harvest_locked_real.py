"""A Harvest keyword reforge on an item whose sides are locked by metamods, on the real 3.29.3.3 dump (ticket #197).

The owner found it in the Craft of Exile emulator (2026-11-01): a Titanium Spirit Shield, item level 100, holding
T1 105% increased Energy Shield (prefix), T1 62% faster start of Energy Shield Recharge (suffix) and the three crafted
metamods `Can have up to 3 Crafted Modifiers`, `Prefixes Cannot Be Changed` (a suffix) and `Suffixes Cannot Be Changed`
(a prefix), so prefixes are 2/3, suffixes 3/3 and the one free slot is a prefix. A Harvest Fire reforge kept every mod
and added one prefix, "T8 10% increased Fire Damage"; the owner says Cold and Lightning behave the same.

The lesson is a consequence of rules the code already has, not a case of its own: a reforge keeps the mods of a locked side
(`metamods.locks_protect_existing_mods`), draws only into the slots that are free, and the guaranteed tagged mod is drawn from
the mods that fit them (`harvest_reforge.guaranteed_draw_first_by_weight`). With one free slot the outcome is therefore
exactly one tagged mod of that slot's side. Nothing in `src` names the shield. The expected weights below come from a
walk over the raw dump, not from the pool code.

The neighbours (one free suffix; no free slot; a free slot whose side has no mod with the tag) follow from the same rules.
For the last two the claim `harvest_reforge.refused_when_no_tagged_mod_fits_a_free_slot` says what the code does (refuse) and
marks it approximate: the wiki speaks of the mod pool, not of slots, and the emulator's answer is being checked (#198).

These tests need the cached dump (`CRAFTING_CACHE_DIR`); they skip cleanly when it is not there. CI fetches it.
"""

import datetime
import random
from fractions import Fraction

import pytest
from abstraction_support import real_game_data

from crafting_system.abstraction import Goal
from crafting_system.actions import HarvestReforge, NotApplicableError
from crafting_system.cli import make_plan, offers_for
from crafting_system.items import ExplicitMod, Item, Rarity, Side
from crafting_system.items.tiers import tier_table
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.rules import rule_by_id
from crafting_system.targets import parse_target

ITEM_LEVEL = 100
ENERGY_SHIELD = "LocalIncreasedEnergyShieldPercent8"  # T1 105% increased Energy Shield
RECHARGE = "FasterStartEnergyShieldRecharge5_"  # T1 62% faster start of Energy Shield Recharge
MULTIMOD = "StrIntMasterItemGenerationCanHaveMultipleCraftedMods"  # a suffix
LOCK_PREFIXES = "StrMasterItemGenerationCannotChangePrefixes"  # a suffix: prefixes cannot be changed
LOCK_SUFFIXES = "DexMasterItemGenerationCannotChangeSuffixes"  # a prefix: suffixes cannot be changed
LIFE = "IncreasedLife10"  # an ordinary prefix with the tag `life`
ELEMENTS = ("fire", "cold", "lightning")

OWNERS_SHIELD = (ENERGY_SHIELD, RECHARGE, MULTIMOD, LOCK_PREFIXES, LOCK_SUFFIXES)  # one free prefix
FREE_SUFFIX_SHIELD = (ENERGY_SHIELD, LIFE, MULTIMOD, LOCK_PREFIXES, LOCK_SUFFIXES)  # prefixes 3/3, suffixes 2/3
FULL_SHIELD = (ENERGY_SHIELD, LIFE, RECHARGE, MULTIMOD, LOCK_PREFIXES, LOCK_SUFFIXES)  # no free slot


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def shield(data, mod_ids) -> Item:
    base = next(b for b in data.base_items.values() if b.name == "Titanium Spirit Shield")
    mods = []
    for mod_id in mod_ids:
        mod = data.mods[mod_id]
        mods.append(ExplicitMod(mod_id, 1, tuple(min(s.min, s.max) for s in mod.stats), crafted=mod.domain == "crafted"))
    return Item.build(data, base_id=base.id, item_level=ITEM_LEVEL, rarity=Rarity.RARE, mods=tuple(mods))


def hand_walk(data, item: Item, tag: str, side: str) -> dict[str, Fraction]:
    """The chance of each mod the guaranteed draw can pick when only a `side` slot is free, found from the raw dump alone.

    A mod counts when it is of the base's domain, on that side, within the item level, tagged `tag`, spawns on the base
    (the first matching spawn tag) and shares no family with a mod the item holds; its weight is the spawn weight times
    the first matching generation weight over 100.
    """
    base = data.base_items[item.base_id]
    base_tags = set(base.tags)
    held = {family for entry in item.mods for family in data.mods[entry.mod_id].families}
    weights: dict[str, Fraction] = {}
    for mod in data.mods.values():
        if mod.domain != base.domain or mod.generation_type != side or mod.required_level > item.item_level:
            continue
        if tag not in mod.implicit_tags or held.intersection(mod.families):
            continue
        spawn = next((w.weight for w in mod.spawn_weights if w.tag in base_tags), 0)
        if not spawn:
            continue
        factor = next((Fraction(w.weight, 100) for w in mod.generation_weights if w.tag in base_tags), Fraction(1))
        weights[mod.id] = spawn * factor
    total = sum(weights.values())
    return {} if not weights else {mod_id: weight / total for mod_id, weight in weights.items()}


def one_mod_chances(outcomes) -> dict[str, Fraction]:
    """The outcome distribution of a reforge that draws one mod: mod id -> chance, failing if an outcome is not exactly one mod."""
    chances = {}
    for outcome, chance in outcomes.distribution(lambda mod: mod.id).items():
        assert sum(count for _, count in outcome) == 1, "the reforge added more or fewer than one mod"
        ((mod_id, _),) = outcome
        chances[mod_id] = chance
    return chances


# --- the owner's shield: both sides locked, one free prefix ----------------------------------------------------


def test_the_owners_shield_has_one_free_prefix_and_nothing_else(data):
    item = shield(data, OWNERS_SHIELD)
    assert {side: item.free_slots(data, side) for side in Side} == {Side.PREFIX: 1, Side.SUFFIX: 0}


@pytest.mark.parametrize("tag", ELEMENTS)
def test_a_keyword_reforge_keeps_every_mod_and_adds_exactly_one_tagged_prefix(tag, data):
    item = shield(data, OWNERS_SHIELD)
    outcomes = HarvestReforge(tag).outcomes(data, item)

    assert {entry.mod_id for entry in outcomes.retained.mods} == set(OWNERS_SHIELD)  # the locks keep all five
    chances = one_mod_chances(outcomes)
    assert chances == hand_walk(data, item, tag, "prefix")
    assert sum(chances.values()) == 1
    assert all(data.mods[mod_id].generation_type == "prefix" and tag in data.mods[mod_id].implicit_tags for mod_id in chances)


@pytest.mark.parametrize("tag", ELEMENTS)
def test_a_sampled_reforge_leaves_the_old_mods_and_one_new_tagged_prefix(tag, data):
    item = shield(data, OWNERS_SHIELD)
    outcomes = HarvestReforge(tag).outcomes(data, item)
    rng = random.Random(197)
    for _ in range(50):
        finished = outcomes.sample(rng)
        ids = [entry.mod_id for entry in finished.mods]
        assert len(ids) == 6 and set(OWNERS_SHIELD) <= set(ids)
        (new,) = set(ids) - set(OWNERS_SHIELD)
        assert data.mods[new].generation_type == "prefix" and tag in data.mods[new].implicit_tags


def test_the_fire_prefix_of_the_screenshot_is_tier_8_of_the_family_with_the_usual_weight(data):
    """The emulator showed "(Tier: 8) 10(10-19)% increased Fire Damage": the lowest tier, one of nine candidates by weight."""
    item = shield(data, OWNERS_SHIELD)
    chances = one_mod_chances(HarvestReforge("fire").outcomes(data, item))
    mod = data.mods["FireDamagePrefixOnWeapon1"]
    assert [(s.min, s.max) for s in mod.stats] == [(10, 19)]
    assert tier_table(data, item.base_id)[mod.id] == 8
    assert tier_table(data, item.base_id)["FireDamagePrefixOnWeapon8_"] == 1
    assert chances[mod.id] == Fraction(500, 2952)  # 1,000 of tiers 1-5 and the gem level mod (250), 150, 40 and 12 below
    assert len(chances) == 9  # eight tiers of "increased Fire Damage" and "+1 to Level of all Fire Spell Skill Gems"


# --- neighbours that follow from the same rules ---------------------------------------------------------------


@pytest.mark.parametrize("tag", ELEMENTS)
def test_one_free_suffix_gives_exactly_one_tagged_suffix(tag, data):
    item = shield(data, FREE_SUFFIX_SHIELD)
    assert {side: item.free_slots(data, side) for side in Side} == {Side.PREFIX: 0, Side.SUFFIX: 1}
    outcomes = HarvestReforge(tag).outcomes(data, item)

    assert {entry.mod_id for entry in outcomes.retained.mods} == set(FREE_SUFFIX_SHIELD)
    chances = one_mod_chances(outcomes)
    assert chances == hand_walk(data, item, tag, "suffix")
    assert all(data.mods[mod_id].generation_type == "suffix" for mod_id in chances)


@pytest.mark.parametrize("tag", ELEMENTS)
def test_no_free_slot_refuses_the_reforge(tag, data):
    """(b) Approximate: refused, since no tagged mod fits a slot; the emulator's answer is checked in #198."""
    item = shield(data, FULL_SHIELD)
    assert {side: item.free_slots(data, side) for side in Side} == {Side.PREFIX: 0, Side.SUFFIX: 0}
    with pytest.raises(NotApplicableError, match="free slot"):
        HarvestReforge(tag).outcomes(data, item)


@pytest.mark.parametrize("tag", ["critical", "speed", "attribute"])
def test_a_free_prefix_with_a_tag_that_only_suffixes_have_refuses_the_reforge(tag, data):
    """(c) Approximate: these tags have mods on the shield, but only suffixes, and the suffix side is full."""
    item = shield(data, OWNERS_SHIELD)
    assert not hand_walk(data, item, tag, "prefix") and hand_walk(data, item, tag, "suffix")
    with pytest.raises(NotApplicableError, match="free slot"):
        HarvestReforge(tag).outcomes(data, item)


@pytest.mark.parametrize("tag", ["physical"])
def test_a_free_suffix_with_a_tag_that_only_prefixes_have_refuses_the_reforge(tag, data):
    item = shield(data, FREE_SUFFIX_SHIELD)
    assert not hand_walk(data, item, tag, "suffix") and hand_walk(data, item, tag, "prefix")
    with pytest.raises(NotApplicableError, match="free slot"):
        HarvestReforge(tag).outcomes(data, item)


def test_the_refusal_is_a_marked_approximate_claim_the_reforge_reads():
    claim = rule_by_id("harvest_reforge.refused_when_no_tagged_mod_fits_a_free_slot")
    assert claim.approximate and claim.approximate_reason
    assert claim.id in HarvestReforge("fire").claims()


# --- the planner ---------------------------------------------------------------------------------------------

TARGET = f"""
base: Titanium Spirit Shield
item_level: {ITEM_LEVEL}
requirements:
  - family: DefencesPercent
    mod: {ENERGY_SHIELD}
  - family: EnergyShieldDelay
    mod: {RECHARGE}
  - stat: "#% increased Fire Damage"
start_item:
  rarity: rare
  mods:
    - {{mod: {ENERGY_SHIELD}, tier: 1, values: [105]}}
    - {{mod: {RECHARGE}, tier: 1, values: [62]}}
    - {{mod: {MULTIMOD}, tier: 1, values: [1], crafted: true}}
    - {{mod: {LOCK_PREFIXES}, tier: 1, values: [1], crafted: true}}
    - {{mod: {LOCK_SUFFIXES}, tier: 1, values: [1], crafted: true}}
"""
LIFEFORCE = {"Wild Crystallised Lifeforce": 0.01, "Vivid Crystallised Lifeforce": 0.02, "Primal Crystallised Lifeforce": 0.03}
START_PRICE = 5.0


def test_the_planner_offers_the_fire_reforge_and_takes_it_first_at_the_price_the_rules_give(data):
    """The target is "the old mods + any % increased Fire Damage prefix".

    The reforge's one new mod is a Fire-tagged prefix, and 250 of its 2,952 weight is "+1 to Level of all Fire Spell Skill
    Gems", which is not "increased Fire Damage": that prefix takes the last slot for good (both sides are locked), so the
    item is bought again (the start price, `restart`). Mean cost = (cost + q * start price) / (1 - q), q the chance of the gem mod.
    """
    target = parse_target(TARGET, data)
    offered = {offer.label for offer in offers_for(data, Goal.from_target(target), target.base_id, target.start_item).offers}
    assert "Harvest Reforge Fire" in offered

    prices = PriceFile(
        "Test", datetime.datetime(2026, 11, 1, tzinfo=datetime.UTC), 300.0, {n: PriceEntry(c, "test") for n, c in LIFEFORCE.items()}
    )
    plan = make_plan(data, target, prices, start_price=START_PRICE)

    item = shield(data, OWNERS_SHIELD)
    chances = hand_walk(data, item, "fire", "prefix")
    q = sum(chance for mod_id, chance in chances.items() if not any(s.id == "fire_damage_+%" for s in data.mods[mod_id].stats))
    assert q == Fraction(250, 2952)
    cost = 50 * LIFEFORCE["Wild Crystallised Lifeforce"]
    assert plan.mean_remaining == pytest.approx(float((Fraction(cost).limit_denominator(10**6) + q * Fraction(START_PRICE)) / (1 - q)))
    assert plan.solution.policy[plan.start].label == "Harvest Reforge Fire"
