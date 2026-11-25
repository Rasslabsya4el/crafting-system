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
from crafting_system.actions.beasts import RARE_BEAST, RARE_BEAST_PRICE_WORDS, AspectBeast, TalismanFracture
from crafting_system.actions.contract import StandIn
from crafting_system.cli._route_view import _View
from crafting_system.items import Side
from crafting_system.planner._offers import Offer, PricedOffer

BEASTS = StandIn(RARE_BEAST, 3, 1.0, RARE_BEAST_PRICE_WORDS)


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
    assert TalismanFracture(1).stand_ins(DATA) == {"Chaos Orb": BEASTS}
    assert AspectBeast("cat", 30).stand_ins(DATA) == {"Chaos Orb": StandIn(RARE_BEAST, 2, 1.0, RARE_BEAST_PRICE_WORDS)}  # The Black Mórrígan takes one place
    assert AspectBeast("cat", 20, rare_creature_price=0).stand_ins(DATA) == {}

    view = view_of(WildBristleMatron(), [("Wild Bristle Matron", 1, 235.0, "poe.ninja"), ("Chaos Orb", 3, 3.0, "a setting")])
    lines = _View.cost_lines(view, policy_action(1))
    assert lines == [
        "1 × Wild Bristle Matron 235 c",
        "3 × rare beast of any kind 3 c, paid as 3 × Chaos Orb: approximate, a fixed price the planner sets: no price list holds them, and no supply is known",
        "total 238 c",
    ]


def note_view(action, steps=()):
    view = view_of(action)
    view.flow = SimpleNamespace(steps=steps)
    view.title_of = lambda row: {10: "Exalted Orb"}.get(row, "x")
    return view


def test_the_matron_sure_on_the_step_says_its_rule_its_one_result_and_where_the_item_comes_back_from():
    """Hand numbers: R14's step 13 (flow step 12), entered from row 10 (flow step 9); an item comes 10 times in a run that reaches it
    (uses 8.5, reached 0.85). The goal names the metamod the card below shows."""
    back = SimpleNamespace(number=9, edges=(SimpleNamespace(to=12),))
    view = note_view(WildBristleMatron(), (back, SimpleNamespace(number=12, edges=(SimpleNamespace(to=14),))))
    goal = ["+1 to Level of Socketed Gems · T1", "Suffixes Cannot Be Changed · crafted"]

    note = _View.sure_draw_note(view, policy_action(1), SimpleNamespace(number=12, uses=8.5, reached=0.85), goal)

    assert note == (
        "the Wild Bristle Matron adds one metamod at random among those the item has room for (an open slot on the metamod's side, and not "
        "on the item already); on every item this step is used on only one has room (Suffixes Cannot Be Changed · crafted), so it cannot "
        "miss here; the item comes here again each time step 10 (Exalted Orb) sends it"
    )
    once = _View.sure_draw_note(view, policy_action(1), SimpleNamespace(number=12, uses=0.85, reached=0.85), goal)
    assert once is not None and "comes here again" not in once


def test_only_a_craft_with_a_rule_of_choice_gets_the_note():
    """A Harvest swap or a Chaos Orb that happens to be sure names no rule of choice (checker on #1518: `Adds.draws` is true by default)."""
    step = SimpleNamespace(number=1, uses=1.0, reached=1.0)
    assert _View.sure_draw_note(note_view(WildBristleMatron()), policy_action(1, 1), step) is None  # not sure
    assert _View.sure_draw_note(note_view(ChaosOrb()), policy_action(1), step) is None
    assert _View.sure_draw_note(note_view(BeastSideSwap(Side.PREFIX)), policy_action(1), step) is None
