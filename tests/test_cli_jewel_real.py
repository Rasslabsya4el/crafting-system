"""Plans for a Cobalt Jewel on the real 3.29.3.3 dump, checked against hand calculations (ticket #201, Done when 3).

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with
`CRAFTING_CACHE_DIR`). They skip cleanly when it is not there; CI fetches it (ticket #165), so they run there.

* The Chaos Orb plan of `examples/targets/j01-cobalt-life-attack-speed.yaml` (a rare Cobalt Jewel with %
  increased maximum Life and two attack-speed mods): one orb costs 1 Chaos and the plan rerolls until the jewel
  holds the three families, so its mean is `1 / p` with `p` the chance that one reroll gives all three (a reroll of a
  jewel draws 3 mods with chance 65% and 4 with 35%, `jewel.reroll_mod_count`). The hand
  chance comes from `jewel_oracle`, which reads the raw mods and walks the draw orders with fractions.
* A magic route (Transmutation, then Alteration until the jewel holds the Life family): the Transmutation result has
  the same law as an Alteration result, so the mean is `Ct + (1 - q) Ca / q` with `q` the chance that a magic
  jewel of 1 or 2 mods (1/2 each) holds the family.
* The sampler of a Chaos Orb agrees with the exact engine on a family that is not rare (the engine is checked against
  the hand oracle in `test_actions_jewels.py`).
"""

import json
import random
from fractions import Fraction
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from cli_support import read_json
from jewel_oracle import PREFIX, SUFFIX, chance_of_families, family_table

from crafting_system.actions import ChaosOrb
from crafting_system.cli import main, make_plan
from crafting_system.items import Item, Rarity
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
TARGET = ROOT / "examples" / "targets" / "j01-cobalt-life-attack-speed.yaml"
COBALT = "Metadata/Items/Jewels/JewelInt"
LIFE, ATTACK_SPEED, WAND_SPEED = "MaximumLifeIncreasePercent", "IncreasedAttackSpeed", "SpecificWeaponSpeed"

MAGIC_ROUTE = """\
base: Cobalt Jewel
item_level: 84
actions: [transmutation-orb, alteration-orb]
requirements:
  - family: MaximumLifeIncreasePercent
"""


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def table(data):
    return family_table(data, COBALT, 84)


@pytest.fixture(scope="module")
def prices():
    return load_price_file(PRICES)


@pytest.fixture(scope="module")
def chaos_plan(data, prices):
    return make_plan(data, load_target(TARGET, data), prices)


def test_the_chaos_plan_offers_the_orb_alone_and_reaches_the_goal(chaos_plan):
    assert [offer.label for offer in chaos_plan.offers] == ["Chaos Orb"]
    assert chaos_plan.risk.success_probability.value == pytest.approx(1.0)


def test_the_chaos_plan_costs_the_inverse_of_the_hand_chance(chaos_plan, table):
    wanted = (LIFE, ATTACK_SPEED, WAND_SPEED)
    room = {PREFIX: 2, SUFFIX: 2}
    p = Fraction(65, 100) * chance_of_families(table, room, 3, wanted) + Fraction(35, 100) * chance_of_families(table, room, 4, wanted)
    chaos = json.loads(PRICES.read_text(encoding="utf-8"))["prices"]["Chaos Orb"]["chaos"]

    assert chaos_plan.risk.mean.value == pytest.approx(chaos / float(p), rel=1e-9)
    assert chaos_plan.mean_remaining == pytest.approx(chaos / float(p), rel=1e-9)


def test_the_magic_route_costs_what_the_hand_formula_says(data, prices, table, tmp_path):
    target_file = tmp_path / "cobalt-life.yaml"
    target_file.write_text(MAGIC_ROUTE, encoding="utf-8")
    raw = json.loads(PRICES.read_text(encoding="utf-8"))["prices"]
    transmutation, alteration = raw["Orb of Transmutation"]["chaos"], raw["Orb of Alteration"]["chaos"]
    room = {PREFIX: 1, SUFFIX: 1}
    q = (chance_of_families(table, room, 1, (LIFE,)) + chance_of_families(table, room, 2, (LIFE,))) / 2

    plan = make_plan(data, load_target(target_file, data), prices)

    assert plan.risk.success_probability.value == pytest.approx(1.0)
    assert plan.risk.mean.value == pytest.approx(transmutation + float(1 - q) * alteration / float(q), rel=1e-9)


def test_the_magic_route_for_a_family_on_both_sides_costs_what_the_hand_formula_says(data, prices, table, tmp_path):
    target_file = tmp_path / "cobalt-damage-form.yaml"
    target_file.write_text(MAGIC_ROUTE.replace(LIFE, "DamageForm"), encoding="utf-8")
    raw = json.loads(PRICES.read_text(encoding="utf-8"))["prices"]
    transmutation, alteration = raw["Orb of Transmutation"]["chaos"], raw["Orb of Alteration"]["chaos"]
    room = {PREFIX: 1, SUFFIX: 1}
    q = (chance_of_families(table, room, 1, ("DamageForm",)) + chance_of_families(table, room, 2, ("DamageForm",))) / 2

    plan = make_plan(data, load_target(target_file, data), prices)

    assert set(table["DamageForm"]) == {PREFIX, SUFFIX}  # the family has weight on both sides of the Cobalt pool
    assert plan.risk.mean.value == pytest.approx(transmutation + float(1 - q) * alteration / float(q), rel=1e-9)


def test_the_command_returns_the_chaos_policy(data, prices, tmp_path):
    out = tmp_path / "policy.json"

    code = main([str(TARGET), "--json", str(out)], data=data, prices=prices, env={})

    assert code == 0
    totals = read_json(out)["totals"]
    assert totals["success_probability"]["value"] == pytest.approx(1.0)
    assert totals["mean_cost"]["value"] > 1000


def test_the_answer_on_a_jewel_names_the_approximate_mod_count_and_one_on_a_belt_does_not(data, prices, tmp_path):
    out = tmp_path / "policy.json"
    main([str(TARGET), "--json", str(out)], data=data, prices=prices, env={})

    listed = [item["claim"] for item in read_json(out)["approximate_inputs"]]

    assert listed == ["jewel.reroll_mod_count"]


def test_the_sampler_of_a_chaos_orb_follows_the_exact_chance_of_a_family(data):
    outcomes = ChaosOrb().outcomes(data, Item.build(data, base_id=COBALT, item_level=84, rarity=Rarity.RARE))
    label = lambda mod: mod.families[0] if mod.families[0] == ATTACK_SPEED else None  # noqa: E731
    chance = sum(c for outcome, c in outcomes.distribution(label).items() if any(name == ATTACK_SPEED for name, _ in outcome))
    rng, runs = random.Random(201), 20000
    hits = sum(any(data.mods[m.mod_id].families[0] == ATTACK_SPEED for m in outcomes.sample(rng).mods) for _ in range(runs))

    assert isinstance(chance, Fraction)
    assert hits / runs == pytest.approx(float(chance), abs=4 * (float(chance) * (1 - float(chance)) / runs) ** 0.5)
