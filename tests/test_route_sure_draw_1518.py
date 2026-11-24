"""A random craft drawn as sure says why, and a beast recipe's rare beasts are named as what they are (#1518).

The crafter doubted the dearest step of R04, R14 and R20 (the Wild Bristle Matron, 48% and 64% of the plan): a beast that adds a random
metamod was drawn with no chance. The step is sure there (lane ttruth, 2026-11-24: on a suffix-full item the one metamod with room is
Suffixes Cannot Be Changed, `beastcraft.metamod_needs_slot_and_crafted_room`), so the fault is the page's silence: the row says it now in a
Note. Its "3 × Chaos Orb" are the recipe's three rare beasts of any kind at 1 Chaos each (`beastcraft.any_rare_creature_price`).
"""

from types import SimpleNamespace

from items_support import DATA

from crafting_system.actions import ChaosOrb
from crafting_system.actions.beast_mods import BeastSideSwap, WildBristleMatron
from crafting_system.cli._route_view import _View
from crafting_system.items import Side
from crafting_system.planner._offers import Offer, PricedOffer

BEASTS = "the recipe's 3 rare beasts of any kind, at 1 Chaos each (a setting: no price list holds them)"


def view_of(action, parts=()):
    """A stand-in for the page's view of one step: the plan's priced offer of `action` and the target's start item."""
    priced = PricedOffer(Offer(action.label(DATA), action, dict(action.resources(DATA))), sum(chaos for _, _, chaos, _ in parts), tuple(parts))
    plan = SimpleNamespace(offer_of=lambda _: priced, target=SimpleNamespace(start_item=None))
    return SimpleNamespace(plan=plan, data=DATA, sure=_View.sure)


def policy_action(*weights):
    """A policy action whose outcomes have `weights` (a sure one has one outcome of weight > 0)."""
    return SimpleNamespace(label="x", outcomes=tuple(SimpleNamespace(weight=w) for w in weights))


def test_the_rare_beasts_of_a_beast_recipe_are_named_where_their_chaos_orbs_are():
    assert WildBristleMatron().stand_ins(DATA) == {"Chaos Orb": BEASTS}
    assert BeastSideSwap(Side.PREFIX).stand_ins(DATA) == {"Chaos Orb": BEASTS}
    assert ChaosOrb().stand_ins(DATA) == {}  # a real Chaos Orb stands for nothing else

    view = view_of(WildBristleMatron(), [("Wild Bristle Matron", 1, 235.0, "poe.ninja"), ("Chaos Orb", 3, 3.0, "a setting")])
    lines = _View.cost_lines(view, policy_action(1))
    assert lines == ["1 × Wild Bristle Matron 235 c", f"3 × Chaos Orb 3 c: {BEASTS}", "total 238 c"]


def test_a_random_craft_that_is_sure_on_the_step_says_why_and_that_returns_use_it_again():
    """Hand numbers: R14's step 13, an item comes 10 times in a run that reaches it (uses 8.5, reached 0.85)."""
    view = view_of(WildBristleMatron())

    note = _View.sure_draw_note(view, policy_action(1), SimpleNamespace(uses=8.5, reached=0.85))

    assert note == (
        "this craft picks its result at random among those the item allows, but on every item this step is used on only one is allowed, "
        "so each use gives the item below: it cannot miss here; it is used again each time a later miss sends the item back here"
    )
    once = _View.sure_draw_note(view, policy_action(1), SimpleNamespace(uses=0.85, reached=0.85))
    assert once is not None and "used again" not in once


def test_a_sure_craft_that_draws_nothing_or_a_draw_with_several_outcomes_has_no_such_note():
    assert _View.sure_draw_note(view_of(WildBristleMatron()), policy_action(1, 1), SimpleNamespace(uses=1.0, reached=1.0)) is None
    bench = SimpleNamespace(label=lambda data=None: "Benchcraft", resources=lambda data=None: {}, adds=lambda data=None, item=None: SimpleNamespace(draws=False))
    plan = SimpleNamespace(offer_of=lambda _: SimpleNamespace(offer=SimpleNamespace(action=bench)), target=SimpleNamespace(start_item=None))
    assert _View.sure_draw_note(SimpleNamespace(plan=plan, data=DATA, sure=_View.sure), policy_action(1), SimpleNamespace(uses=1.0, reached=1.0)) is None
