"""The kind-level relevance test before the walk (ticket #848, decided in #637), on the real 3.29.3.3 dump.

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with `CRAFTING_CACHE_DIR`). They skip cleanly
when it is not there; CI fetches it (ticket #165), so they run there.

The test leaves out, before the walk and the bound, (A) an action the model refuses on every item of the target's base (`UnmodelledBase`:
the Harvest crafts and the veiled orbs on a jewel) and (B) an action that needs a veiled placeholder no offered action can make (Unveil,
Pick). Done when (#848), and the test of each:

1. A kind it leaves out changes no exact mean, the walk with and without it, to 1e-12: `test_j01_with_the_left_out_kinds_forced_in_*` and
   `test_on_generated_jewel_targets_*`; on J01 the left-out set holds the 17 kinds the probe of #637 found inert:
   `test_on_j01_every_kind_named_*`.
2. The answer lists the kinds left out with what it still guarantees (OR-13): the same test and `test_the_answer_of_j01_*`.
3. The counts on a runner: the PR's measurement (`.github/scripts/actions_key.py`), not a test.

The hand number: J01's Chaos Orb plan costs `chaos / p`, `p` the chance that one reroll holds the three families (65% 3 mods, 35% 4,
`jewel.reroll_mod_count`), from `jewel_oracle`, which reads the raw mods and shares no code with the engine (as `test_cli_jewel_real.py`).
"""

import dataclasses
import random
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from jewel_oracle import PREFIX, SUFFIX, chance_of_families, family_table

from crafting_system.abstraction import Goal
from crafting_system.actions import (
    ChaosOrb,
    HarvestResistanceSwap,
    NotApplicableError,
    OutOfScopeError,
    Unveil,
    UnmodelledBase,
    VeiledChaosOrb,
    base_refusal,
    catalog_kinds,
    kinds,
)
from crafting_system.actions.scope import BasePassed
from crafting_system.cli import _limits, make_plan, offers_for
from crafting_system.cli import _plan as plan_module
from crafting_system.cli._offers import offer_of, split_usable
from crafting_system.items import ExplicitMod, Item, Rarity, veiled_placeholder
from crafting_system.prices import load_price_file
from crafting_system.prices.price_file import PriceEntry
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-11-10.json"  # prices every Harvest craft, Unveil and Pick
TARGET = ROOT / "examples" / "targets" / "j01-cobalt-life-attack-speed.yaml"
COBALT, CRIMSON, VIRIDIAN = "Metadata/Items/Jewels/JewelInt", "Metadata/Items/Jewels/JewelStr", "Metadata/Items/Jewels/JewelDex"
BELT = "Metadata/Items/Belts/Belt3"
LIFE, ATTACK_SPEED, WAND_SPEED = "MaximumLifeIncreasePercent", "IncreasedAttackSpeed", "SpecificWeaponSpeed"

# The 17 kinds the probe of #637 (run 42378616946) found to add no state to J01 and that list no action for a rare Cobalt Jewel.
INERT_ON_J01 = frozenset({
    "harvest-reforge-influence", "essence", "corrupted-essence", "bench-craft", "remove-crafted-mods", "transmutation-orb", "alteration-orb",
    "augmentation-orb", "regal-orb", "talisman-fracture", "aspect-beast", "wild-bristle-matron", "divine-orb", "imprint", "restore", "vaal", "locus",
})  # fmt: skip
REFUSED_ON_A_JEWEL = frozenset({  # cut A: listed for the jewel, refused by the model on every item of the base
    "harvest-reforge", "harvest-add-remove", "harvest-resistance-swap", "harvest-damage-swap", "veiled-chaos-orb", "veiled-exalted-orb",
})  # fmt: skip
NEED_A_VEIL = frozenset({"unveil", "pick"})  # cut B: no offered action makes a veiled placeholder on a jewel
CUT_KINDS = sorted(REFUSED_ON_A_JEWEL | NEED_A_VEIL)
# Walked with the kinds forced in: all but the Harvest add and remove crafts, whose reads tell every junk family apart (J01 with them did
# not finish its walk in 40 s here); that blow-up is what the cut saves, and their exactness rests on the base refusal shown below.
WALKED_KINDS = sorted(set(CUT_KINDS) - {"harvest-add-remove"})
PER_KIND = 20  # actions of one kind the base-refusal property asks
J01_MEAN = 34288.310783892106  # J01's Chaos Orb plan at these prices (the hand chance test checks it against the oracle)
VEILED_ORB_PRICE = 3.0  # the snapshot lists none; a price makes the "with" walk offer them for real


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def prices():
    base = load_price_file(PRICES)
    extra = {name: PriceEntry(VEILED_ORB_PRICE, "test") for name in ("Veiled Chaos Orb", "Veiled Exalted Orb")}
    return dataclasses.replace(base, prices={**base.prices, **extra})


def every_kind() -> list[str]:
    return [entry.name for entry in kinds(planner_only=True) if not entry.needs_strands]


def jewel_target(data, tmp_path, base_name: str, families: tuple[str, ...], named: list[str], name: str = "target"):
    """A target on `base_name` (a jewel, or any base) at item level 84 from a given rare start item, with the kinds `named`."""
    text = (
        f"base: {base_name}\nitem_level: 84\nstart_item:\n  rarity: rare\nstart: given\nactions: [{', '.join(named)}]\nrequirements:\n"
        + "".join(f"  - family: {family}\n" for family in families)
    )
    path = tmp_path / f"{name}.yaml"
    path.write_text(text, encoding="utf-8")
    return load_target(path, data)


def forced_offers(data, target):
    """Every action the named kinds list for the start item, unfiltered: what the walk would hold without the relevance test."""
    listed = catalog_kinds(data, target.start_item, planner_only=True, names=frozenset(target.actions))
    labels = {}
    for action in listed:
        labels.setdefault(action.label(data), []).append(action)
    offers = []
    for label, actions in labels.items():
        for number, action in enumerate(actions, 1):
            offers.append(offer_of(action, label if len(actions) == 1 else f"{label} [{number}]", data, target.start_item, listed[action]))
    return offers


def walk_mean(data, target, prices, offers=None) -> float:
    plan = make_plan(data, target, prices, offers=offers, solver="packed", with_risk=False)
    return plan.mean_remaining


def crafted_only(data, start_item, actions):
    """`split_usable` as it was before #848 (only the crafted-mod rule), so that a forced walk really holds an Unveil and a Pick."""
    actions = list(actions)
    if start_item.crafted_mods or any(action.adds(data, start_item).crafted for action in actions):
        return actions, []
    return [a for a in actions if not a.reads(data).needs_crafted], [a for a in actions if a.reads(data).needs_crafted]


def forced_walk_mean(data, target, prices, monkeypatch) -> tuple[float, int]:
    """The walk's mean with every action of the named kinds offered, and the number of states it holds."""
    offers = forced_offers(data, target)
    with monkeypatch.context() as patch:
        patch.setattr(plan_module, "split_usable", crafted_only)
        plan = make_plan(data, target, prices, offers=offers, solver="packed", with_risk=False)
    return plan.mean_remaining, len(plan.solution.values)


# --- 1 and 2: J01 -------------------------------------------------------------------------------------------------------------------


def test_on_j01_every_kind_named_leaves_out_the_seventeen_inert_kinds_and_the_eight_it_proves_unusable(data, tmp_path):
    target = jewel_target(data, tmp_path, "Cobalt Jewel", (LIFE, ATTACK_SPEED, WAND_SPEED), every_kind())

    chosen = offers_for(data, Goal.from_target(target), target.base_id, target.start_item, target.actions)

    offered = {offer.kind for offer in chosen.offers}
    left_out = set(target.actions) - offered
    assert INERT_ON_J01 <= left_out
    assert REFUSED_ON_A_JEWEL | NEED_A_VEIL <= left_out
    assert offered == {"chaos-orb", "fossil-set", "exalted-orb", "annulment-orb", "fracturing-orb", "beast-side-swap"}
    gaps = [limit for limit in chosen.limits if limit.kind == _limits.LISTING_GAP]
    assert len(gaps) == 1 and set(gaps[0].labels) == {_limits.kind_title(name) for name in REFUSED_ON_A_JEWEL}
    assert "An action the model has no rule for could make it cheaper." in gaps[0].guarantee  # a model gap is never silent (#506)
    veils = [limit for limit in chosen.limits if limit.kind == _limits.NO_VEIL]
    assert len(veils) == 1 and veils[0].labels == ("Unveil", "Pick 1", "Pick 2", "Pick 3")
    assert veils[0].guarantee == "The plan is unaffected: these could never be used for this target."


def test_j01_with_the_left_out_kinds_named_costs_the_hand_chance(data, prices, tmp_path):
    target = jewel_target(data, tmp_path, "Cobalt Jewel", (LIFE, ATTACK_SPEED, WAND_SPEED), ["chaos-orb", *CUT_KINDS])
    table = family_table(data, COBALT, 84)
    room = {PREFIX: 2, SUFFIX: 2}
    p = sum(
        share * chance_of_families(table, room, picks, (LIFE, ATTACK_SPEED, WAND_SPEED))
        for share, picks in ((0.65, 3), (0.35, 4))
    )
    chaos = 1.0  # a Chaos Orb is worth 1 Chaos, whatever the file lists (`price_offers`)

    plan = make_plan(data, target, prices)

    assert [offer.label for offer in plan.offers] == ["Chaos Orb"]
    assert plan.mean_remaining == pytest.approx(chaos / float(p), rel=1e-9)


@pytest.mark.parametrize(
    "group",
    [
        ("harvest-reforge", "harvest-resistance-swap", "harvest-damage-swap", "veiled-chaos-orb"),
        ("veiled-exalted-orb", "unveil", "pick"),
        ("unveil", "pick"),
    ],
    ids=["harvest-and-veiled-chaos", "veiled-exalted-and-unveil", "unveil-alone"],
)
def test_j01_with_the_left_out_kinds_forced_in_has_the_same_walk_mean_to_1e_12(data, prices, tmp_path, monkeypatch, group):
    target = jewel_target(data, tmp_path, "Cobalt Jewel", (LIFE, ATTACK_SPEED, WAND_SPEED), ["chaos-orb", *group])
    assert {offer.kind for offer in forced_offers(data, target)} == {"chaos-orb", *group}  # the walk really holds them

    without = walk_mean(data, target, prices)
    with_them, states = forced_walk_mean(data, target, prices, monkeypatch)

    assert with_them == pytest.approx(without, rel=1e-12)
    assert without == pytest.approx(J01_MEAN, rel=1e-12)
    assert states >= 8  # 8 without them; 77 to 767 with (the swaps' reads split the junk)


def test_the_answer_of_j01_as_committed_is_unchanged(data, prices):
    plan = make_plan(data, load_target(TARGET, data), prices)

    assert [offer.label for offer in plan.offers] == ["Chaos Orb"]
    assert not [limit for limit in plan.limits if limit.kind in (_limits.LISTING_GAP, _limits.NO_VEIL)]


# --- 1: generated jewel targets ------------------------------------------------------------------------------------------------------


def generated_cases(data, count: int, seed: int = 848):
    """`count` random targets: a base jewel, one or two families of its pool, the Chaos Orb and a random part of the kinds the test cuts."""
    rng = random.Random(seed)
    bases = (("Cobalt Jewel", COBALT), ("Crimson Jewel", CRIMSON), ("Viridian Jewel", VIRIDIAN))
    cases = []
    for _ in range(count):
        name, base_id = rng.choice(bases)
        table = family_table(data, base_id, 84)
        families = tuple(rng.sample(sorted(table), rng.choice((1, 2))))
        named = ["chaos-orb", *sorted(rng.sample(WALKED_KINDS, rng.randint(1, 2)))]
        cases.append((name, families, named))
    return cases


@pytest.mark.parametrize("index", range(6))
def test_on_generated_jewel_targets_the_left_out_kinds_change_no_walk_mean(data, prices, tmp_path, monkeypatch, index):
    name, families, named = generated_cases(data, 6)[index]
    target = jewel_target(data, tmp_path, name, families, named, f"case{index}")

    chosen = offers_for(data, Goal.from_target(target), target.base_id, target.start_item, target.actions)
    without = walk_mean(data, target, prices)
    with_them, _ = forced_walk_mean(data, target, prices, monkeypatch)

    assert {offer.kind for offer in chosen.offers} == {"chaos-orb"}, (name, families, named)
    assert with_them == pytest.approx(without, rel=1e-12), (name, families, named)


# --- what the test does not cut --------------------------------------------------------------------------------------------------------


def test_on_a_belt_the_harvest_swaps_and_the_veiled_orbs_stay_offered(data, tmp_path):
    named = ["chaos-orb", "harvest-resistance-swap", "veiled-chaos-orb", "unveil", "pick"]
    target = jewel_target(data, tmp_path, "Leather Belt", ("IncreasedLife",), named)

    chosen = offers_for(data, Goal.from_target(target), target.base_id, target.start_item, target.actions)

    assert {offer.kind for offer in chosen.offers} == set(named)
    assert not [limit for limit in chosen.limits if limit.kind in (_limits.LISTING_GAP, _limits.NO_VEIL)]


def test_an_unveil_is_kept_for_a_start_item_that_holds_a_placeholder_and_cut_without_one(data):
    plain = Item.build(data, base_id=BELT, item_level=84, rarity=Rarity.RARE)
    veiled = plain.add_mod(data, veiled_placeholder(data, "VeiledSuffix"))

    assert split_usable(data, plain, [ChaosOrb(), Unveil()]) == ([ChaosOrb()], [Unveil()])
    assert split_usable(data, veiled, [ChaosOrb(), Unveil()]) == ([ChaosOrb(), Unveil()], [])
    assert split_usable(data, plain, [VeiledChaosOrb(), Unveil()]) == ([VeiledChaosOrb(), Unveil()], [])


# --- the base refusal is a property of the base ---------------------------------------------------------------------------------------


def jewel_items(data, base_id: str) -> list[Item]:
    """Items of a jewel base: empty at each rarity, and rare and magic ones with mods drawn by the engine's own orbs."""
    rng = random.Random(base_id)
    rare = Item.build(data, base_id=base_id, item_level=84, rarity=Rarity.RARE)
    items = [rare, Item.build(data, base_id=base_id, item_level=84, rarity=Rarity.MAGIC), Item.build(data, base_id=base_id, item_level=84, rarity=Rarity.NORMAL)]
    items += [ChaosOrb().outcomes(data, rare).sample(rng) for _ in range(3)]
    return items


@pytest.mark.parametrize("base_id", [COBALT, CRIMSON, VIRIDIAN, "Metadata/Items/Jewels/JewelAbyssMelee"])
def test_an_action_the_model_refuses_on_one_item_of_a_base_for_its_base_refuses_every_item_of_it(data, base_id):
    """The contract `UnmodelledBase` rests on: its verdict reads the base alone, so one item proves it for all (every planner action)."""
    items = jewel_items(data, base_id)
    per_kind: dict[str, list] = {}
    for item in items:
        for action, kind in catalog_kinds(data, item, planner_only=True, names=frozenset(every_kind())).items():
            if action not in per_kind.setdefault(kind, []) and len(per_kind[kind]) < PER_KIND:  # the fossil sets are thousands of one code path
                per_kind[kind].append(action)
    listed = [action for actions in per_kind.values() for action in actions]
    proved = 0
    for action in listed:
        verdicts = []
        for item in items:
            try:
                action.outcomes_under(data, item)
                verdicts.append("result")
            except UnmodelledBase:
                verdicts.append("base")
            except (NotApplicableError, OutOfScopeError):
                verdicts.append("refused")
        if "base" in verdicts:
            proved += 1
            assert "result" not in verdicts, f"{action.label(data)} refuses some items of {base_id} for the base and gives a result on another"
            assert base_refusal(data, action, items) is not None
    assert proved > 0


def test_the_probe_stops_a_use_at_the_base_verdict_and_leaves_no_probe_behind(data):
    rare_belt = Item.build(data, base_id=BELT, item_level=84, rarity=Rarity.RARE)
    rare_jewel = Item.build(data, base_id=COBALT, item_level=84, rarity=Rarity.RARE)

    assert base_refusal(data, HarvestResistanceSwap(), [rare_jewel]) is not None
    assert base_refusal(data, HarvestResistanceSwap(), [rare_belt]) is None
    assert base_refusal(data, ChaosOrb(), [rare_jewel]) is None  # the orbs work on jewels
    ChaosOrb().outcomes(data, rare_jewel)  # outside a probe the base passes silently: no `BasePassed` escapes
    with pytest.raises(UnmodelledBase):
        HarvestResistanceSwap().outcomes(data, rare_jewel)
    assert issubclass(UnmodelledBase, OutOfScopeError) and not issubclass(BasePassed, ValueError)


def test_a_placeholder_item_is_built_as_the_offers_see_it(data):
    """`veiled_placeholder` gives the mod `holds_placeholder` looks for (a guard on the fixture of the test above)."""
    from crafting_system.actions import holds_placeholder

    plain = Item.build(data, base_id=BELT, item_level=84, rarity=Rarity.RARE)
    assert not holds_placeholder(data, plain)
    assert holds_placeholder(data, plain.add_mod(data, veiled_placeholder(data, "VeiledPrefix")))
    assert isinstance(veiled_placeholder(data, "VeiledPrefix"), ExplicitMod)
