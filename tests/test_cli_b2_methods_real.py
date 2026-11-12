"""Every beast, Talisman and Harvest add/remove/swap method of batch B2 is offered and priced by the CLI (ticket #150).

No benchmark route uses the Harvest swaps, the side-swap beasts, the aspects or the Talisman fractures (`tests/golden/reachability.md`),
so these plans name them: rare boots for the Harvest crafts, the side swaps and the Matron, the same boots wanting an aspect (an aspect
is offered only to a target that wants it), and a Talisman for the fractures. Each is built with `make_plan(solve_it=False)` at R20's
price file, which prices every beast the recipes consume (`beastcraft.recipe_beasts`): from poe.ninja's Standard economy, the planner's
own last fallback, because Allflame's beast prices are gone, and The Black Morrigan by a hand placeholder (#813). Skips without the
cached dump.

Not here: the beast influence recipes (`beast-influence-recipe`) and the influenced Exalted Orbs are `planner=False` until a goal built
from a target names an influenced mod (ADR-0030, amendment of #155), so no plan offers them yet.
"""

import textwrap
from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system.cli import make_plan
from crafting_system.prices import load_price_file
from crafting_system.rules import get_rule
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "b2-r20-beasts-2026-11-12.json"
MORRIGAN = "The Black Mórrígan"
HARVEST_TAGS = ("Fire", "Cold", "Lightning", "Physical", "Life", "Defence", "Chaos", "Attack", "Caster", "Speed", "Critical")
SWAPS = [(a, b) for a in ("Fire", "Cold", "Lightning") for b in ("Fire", "Cold", "Lightning") if a != b]
BOOTS = {
    **{f"Harvest Add Remove {tag}": None for tag in HARVEST_TAGS},
    **{f"Harvest Swap Resistance {a} to {b}": None for a, b in SWAPS},
    **{f"Harvest Swap Damage {a} to {b}": None for a, b in SWAPS},
    # a named beast and three rare beasts of any kind at 1 Chaos each (`beastcraft.any_rare_creature_price`)
    "Beastcraft Add Prefix Remove Suffix": 2.0 + 3,  # Farric Wolf Alpha
    "Beastcraft Add Suffix Remove Prefix": 1.0 + 3,  # Farric Lynx Alpha
    "Beastcraft Wild Bristle Matron (add a metamod)": 254.0 + 3,
}
# an aspect: its beast and three rare beasts at level 20, its beast, The Black Morrigan and two rare beasts at level 30
ASPECT_BEASTS = {"Bird": ("Avian", 1.0), "Cat": ("Cat", 20.0), "Crab": ("Crab", 2.7), "Spider": ("Spider", 30.0)}
ASPECTS = [
    (f"Grants{word}AspectCrafted{'' if level == 20 else 30}", f"Beastcraft Aspect of the {name} (level {level})", beast + (3 if level == 20 else 100.0 + 2))
    for word, (name, beast) in ASPECT_BEASTS.items()
    for level in (20, 30)
]
TALISMAN = {
    "Beastcraft Fracture a Talisman Modifier": 1.0 + 3,  # Farric Frost Hellion Alpha
    "Beastcraft Fracture two Talisman Modifiers": 761.2 + 100.0 + 2,  # Fenumal Plagued Arachnid and The Black Morrigan
}


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def plan_of(data, tmp_path: Path, text: str):
    path = tmp_path / "target.yaml"
    path.write_text(textwrap.dedent(text) + f"price_file: {PRICES.as_posix()}\n", encoding="utf-8")
    target = load_target(path, data)
    return make_plan(data, target, load_price_file(PRICES), solve_it=False)


def check_offered_and_priced(plan, expected: dict[str, float | None]) -> None:
    costs = {priced.label: priced.cost for priced in plan.offers}
    assert set(expected) <= set(costs), sorted(set(expected) - set(costs))
    assert not [limit for limit in plan.limits if limit.kind == "unpriced"]
    for label, cost in expected.items():
        assert costs[label] > 0
        if cost is not None:
            assert costs[label] == pytest.approx(cost), label


def test_every_beast_a_recipe_consumes_is_priced_and_marked(data):
    entries = load_price_file(PRICES).prices
    beasts = {name for recipe in get_rule("beastcraft.recipe_beasts").value.values() for name in recipe if name != "any_rare_creature"}

    assert beasts <= set(entries)
    assert {name for name in beasts if entries[name].source != "poe.ninja-standard"} == {MORRIGAN}
    assert entries[MORRIGAN].source == "hand"


def test_the_harvest_crafts_the_side_swaps_and_the_matron_on_rare_boots(data, tmp_path):
    plan = plan_of(data, tmp_path, """
        base: Murder Boots
        item_level: 86
        influence: []
        actions: [harvest-add-remove, harvest-resistance-swap, harvest-damage-swap, beast-side-swap, wild-bristle-matron]
        requirements:
          - family: ColdResistance
            min_tier: 2
        start_item:
          rarity: rare
        start: given
    """)

    check_offered_and_priced(plan, BOOTS)


@pytest.mark.parametrize(("mod_id", "label", "cost"), ASPECTS, ids=[mod_id for mod_id, *_ in ASPECTS])
def test_each_aspect_for_a_target_that_wants_it(data, tmp_path, mod_id, label, cost):
    plan = plan_of(data, tmp_path, f"""
        base: Murder Boots
        item_level: 86
        influence: []
        actions: [aspect-beast]
        requirements:
          - family: GrantedSkill
            mod: {mod_id}
        start_item:
          rarity: rare
        start: given
    """)

    check_offered_and_priced(plan, {label: cost})


def test_the_talisman_fractures_on_a_talisman(data, tmp_path):
    plan = plan_of(data, tmp_path, """
        base: Metadata/Items/Amulets/Talismans/TalismanBlackMaw
        item_level: 86
        influence: []
        actions: [talisman-fracture, chaos-orb]
        requirements:
          - family: IncreasedLife
            min_tier: 1
        start_item:
          rarity: rare
        start: given
    """)

    check_offered_and_priced(plan, TALISMAN)
