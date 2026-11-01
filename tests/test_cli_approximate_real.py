"""R05 at 141 crafts answered approximately, and at 32 crafts exactly (ticket #127, ADR-0023). Needs the cached dump; skips without it, as CI does.

The ring is the one of ADR-0023 (Iron Ring, item level 86, a fractured All Attributes, goal Life and the forced Strength of
the Deafening Essence of Rage) with Remove Crafted Mods and either the 32 crafts that touch the goal's families or all 141
ring crafts. Prices are the committed fixture `routes-allflame-2026-10-31.json`; the start ring costs what it says there. The
rates are injected (4e-5 s per kernel outcome, 7e-6 s per solved edge, the values of ADR-0023), so the decision does not
depend on the machine; no time is asserted (ADR-0014).
"""

from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system.actions import ApplyEssence, RemoveCraftedMods
from crafting_system.actions.bench import bench_crafts
from crafting_system.cli import make_plan
from crafting_system.cli._decide import Rates
from crafting_system.cli._offers import offer_of
from crafting_system.prices import load_price_file
from crafting_system.targets import parse_target

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
BASE = "Metadata/Items/Rings/Ring1"
RATES = Rates(4e-5, 7e-6)
TOUCHING = {
    "IncreasedLife", "FireResistance", "ColdResistance", "LightningResistance", "ChaosResistance",
    "AllAttributes", "Strength", "Dexterity", "Intelligence",
}  # fmt: skip


@pytest.fixture(scope="module")
def ring():
    data = real_game_data()
    low = [min(stat.min, stat.max) for stat in data.mods["AllAttributes7"].stats]
    target = parse_target(
        f"""base: Iron Ring
item_level: 86
requirements:
  - family: IncreasedLife
  - family: Strength
    mod: StrengthEssence7_
start_item:
  rarity: rare
  mods:
    - mod: AllAttributes7
      tier: 1
      values: {low}
      fractured: true
start_price: R05 start ring
""",
        data,
        source="r05.yaml",
    )
    item_class = data.base_items[BASE].item_class
    crafts = [craft for craft in bench_crafts(data) if item_class in craft.option(data).item_classes]
    return data, target, crafts


def offers(data, target, crafts):
    start = target.start_item
    return [
        offer_of(ApplyEssence("Deafening Essence of Rage"), "Deafening Essence of Rage", data, start),
        offer_of(RemoveCraftedMods(), "Remove Crafted Mods", data, start),
        *(offer_of(craft, f"{craft.label(data)} [{craft.mod_id}]", data, start) for craft in crafts),
    ]


@pytest.fixture(scope="module")
def exact_32(ring):
    data, target, crafts = ring
    touching = [craft for craft in crafts if set(data.mods[craft.mod_id].families) & TOUCHING]
    plan = make_plan(data, target, load_price_file(PRICES), offers=offers(data, target, touching), budget=60.0, rates=RATES)
    return touching, plan


@pytest.fixture(scope="module")
def approximate_141(ring):
    data, target, crafts = ring
    return crafts, make_plan(data, target, load_price_file(PRICES), offers=offers(data, target, crafts), budget=60.0, rates=RATES)


def test_32_crafts_stay_exact(exact_32):
    touching, plan = exact_32

    assert len(touching) == 32
    assert plan.approximation is None and plan.risk is not None and plan.note == ""
    assert plan.risk.success_probability.value == pytest.approx(1.0)
    assert plan.dropped == ()


def test_141_crafts_are_answered_approximately_within_one_percent_around_the_exact_optimum_of_the_32_craft_model(ring, exact_32, approximate_141):
    crafts, plan = approximate_141
    _, exact = exact_32

    found = plan.approximation

    assert len(crafts) == 141 and plan.dropped == ()
    assert found is not None and plan.risk is None
    assert found.lower <= exact.mean_remaining <= found.upper  # the 109 other crafts never enter the best policy
    assert found.gap <= 0.01 and found.within_tolerance
    assert found.blocks < 13_172


def test_the_pilot_counts_the_exact_graphs_of_the_adr(ring, exact_32, approximate_141):
    data, target, crafts = ring
    _, plan = exact_32
    actions = [offer.action for offer in offers(data, target, crafts)]
    touching, _ = exact_32

    small = plan.abstraction.estimate([plan.start], [offer.action for offer in offers(data, target, touching)])
    large = approximate_141[1].abstraction.estimate([approximate_141[1].abstraction.compress(target.start_item)], actions)

    assert (small.states, large.states) == (76, 14_350)  # 13,172 in the ADR, before ticket #68 lifted the multimod's dead end
    assert small.complete and large.complete
    assert large.transitions > 20_000_000
