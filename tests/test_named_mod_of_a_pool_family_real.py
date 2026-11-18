"""A mod that only an action puts on the item by name, of a family the pool lists on its other side or in influence mods alone (#1290).

The Essence of Horror gives a helmet the suffix `SocketedGemsDealMoreElementalDamageEssence1`, of the family `Supported`. On a Shaper and
Elder Eternal Burgonet the pool lists that family (the influences' "supported by" mods), so with an action that reads the pool weight the
essence's mod has the kind of the family's type (`Kinds.of`: holding it takes the family's weight out of a draw). No mod of the pool can
stand for a slot of that kind on its side, and the state the essence gave was no item (`Abstraction._item_of` refused it): the bound's build
met a key with no member and the plan ended in "a fault of its own" (R20 on its guide's offers, once the build reached that key).
"""

import dataclasses
from pathlib import Path

import pytest
from abstraction_b2_support import check_layer_1
from abstraction_support import real_game_data

from crafting_system.actions import AnnulmentOrb, ExaltedOrb
from crafting_system.budget import Budget
from crafting_system.cli import make_plan
from crafting_system.items import ExplicitMod, Influence, Item, Rarity
from crafting_system.planner import PlanError
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target
from crafting_system.targets.model import StartKind

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "examples" / "targets" / "r20-rf-helmet.yaml"
ESSENCE = "SocketedGemsDealMoreElementalDamageEssence1"
METHODS = ("corrupted-essence", "exalted-orb", "annulment-orb")  # the essence, and two actions that read the junk (one by its pool weight)
STATES = 60  # the run's net, counted in states: its bound's build has 6,000 pieces of work and met the key with no member within them


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def target(data):
    """R20's helmet asked for its first two mods (the essence's suffix is then not the whole goal: a state that holds it goes on), held
    and not bought (the build then starts at the helmet itself, not at the draw of a listing's mods)."""
    whole = load_target(TARGET, data)
    return dataclasses.replace(whole, requirements=whole.requirements[:2], start=StartKind.GIVEN)


def test_the_state_that_holds_the_essences_suffix_is_an_item_and_its_kernels_are_the_items_own(data, target):
    plan = make_plan(data, target, load_price_file(target.price_file), methods=METHODS, solve_it=False)
    ability = plan.abstraction
    low = lambda mod_id: tuple(min(stat.min, stat.max) for stat in data.mods[mod_id].stats)  # noqa: E731
    item = Item.build(
        data, base_id=target.base_id, item_level=target.item_level, rarity=Rarity.RARE, influences=frozenset({Influence.SHAPER, Influence.ELDER}),
        mods=tuple(ExplicitMod(mod_id, low(mod_id)) for mod_id in (ESSENCE, "FireResist1", "IncreasedLife1")),
    )  # fmt: skip
    state = ability.compress(item)
    essence_slot = next(slot for slot in state.slots if int(slot.contribution[0]))
    assert essence_slot.kind.startswith("~")  # the type of its family, which the pool lists

    back, origins = ability._item_of(state, False)

    held = [data.mods[entry.mod_id] for entry in back.mods]
    stand_in = next(mod for mod in held if "Supported" in mod.families)
    assert stand_in.generation_type == "suffix" and not ability._kinds.is_influenced(stand_in)  # an ordinary suffix of the family
    assert origins[(stand_in.id, False, False)] == essence_slot  # and the slot it stands for keeps what the essence's mod gives the goal
    assert check_layer_1(ability, data, item, AnnulmentOrb()) is True
    assert check_layer_1(ability, data, item, ExaltedOrb()) is True


def test_a_plan_counted_in_states_stops_and_says_so_where_the_bounds_build_met_a_key_with_no_member(data, target):
    with pytest.raises(PlanError) as stopped:
        make_plan(data, target, load_price_file(target.price_file), budget=Budget.in_states(STATES), methods=METHODS, with_risk=False)

    said = str(stopped.value)
    assert said.startswith("stopped, no plan found yet")  # OR-33: a stop at the run's net, with what is still guaranteed
    assert "no plan costs less than" in said
    assert "fault of its own" not in said
