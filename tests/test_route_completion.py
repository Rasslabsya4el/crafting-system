"""The rule of a completed route (tickets #599, #628): it never restarts where the guide's own loop could keep the progress.

`examples/routes/<route>-restart.yaml` is the guide plus rules the guide does not have. Where a rule the guide does not have fires a `restart`, every
action the guide's rules name must be refused by the game, or the restart throws away what the guide's loop could have kept (R04 before #599: the
guide's 13 gaps bought a new quiver and lost the fractured Pierce). The check is `cli._route_completion`; here it runs on hand-built items of the real
game data, at once. The full check (every state the route reaches on the walked graph of R04 and R14) is a heavy run of
`.github/scripts/completion_check.py`, which the PR of #599 names by run id.
"""

from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system.cli import load_route, make_plan, parse_route
from crafting_system.cli._route_completion import added_restarts, guide_actions, losses_at_item
from crafting_system.items import ExplicitMod, Influence, Item, Rarity
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-11-10.json"
TARGETS = {"R04": "r04-penetrating-quiver", "R14": "r14-hunter-bow"}
ROUTES = {"R04": "r04-penetrating-quiver", "R14": "r14-hunter-bow"}

QUIVER = "Metadata/Items/Quivers/QuiverNew5"
PIERCE, STRENGTH, ARROW = "AdditionalPierceEssence7", "StrengthEssence7_", "AdditionalArrowQuiver1_"
NO_ATTACK, MULTIMOD = "IntMasterItemGenerationCannotRollAttackAffixes", "StrIntMasterItemGenerationCanHaveMultipleCraftedMods"
SPEED = "LocalIncreasedAttackSpeed5"
JUNK_PREFIXES = ("LocalIncreasedPhysicalDamagePercentAndAccuracyRating1", "LocalAddedFireDamage1", "LocalAddedColdDamage1")


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def plan_of(data, route_id):
    return make_plan(data, load_target(ROOT / "examples" / "targets" / f"{TARGETS[route_id]}.yaml", data), load_price_file(PRICES), solve_it=False)


def rare(data, base_id, item_level, mod_ids, fractured=(), influences=frozenset()):
    mods = tuple(
        ExplicitMod(mod_id, tuple(min(s.min, s.max) for s in data.mods[mod_id].stats), fractured=mod_id in fractured, crafted=data.mods[mod_id].domain == "crafted")
        for mod_id in mod_ids
    )
    return Item.build(data, base_id=base_id, item_level=item_level, rarity=Rarity.RARE, influences=influences, mods=mods)


def gap_item(data, route_id):
    """A state the guide has no word for: both metamods on, the prefixes full of mods that are not the target's, no slot free."""
    if route_id == "R04":  # the metamod on, the Pierce fractured, the Strength and the arrow there, Life and Damage at the lowest tier
        return rare(data, QUIVER, 81, (PIERCE, STRENGTH, ARROW, NO_ATTACK, "IncreasedLife1", "DamageWithBowSkills1"), fractured=(PIERCE,))
    plan = plan_of(data, route_id)
    return rare(data, plan.target.base_id, 78, (SPEED, MULTIMOD, NO_ATTACK, *JUNK_PREFIXES), influences=frozenset({Influence.HUNTER}))


@pytest.fixture(scope="module", params=["R04", "R14"])
def route_id(request):
    return request.param


def test_a_completed_route_restarts_only_where_every_action_of_the_guide_is_refused(data, route_id):
    plan = plan_of(data, route_id)
    guide = load_route(ROOT / "examples" / "routes" / f"{ROUTES[route_id]}.yaml", plan, data)
    completed = load_route(ROOT / "examples" / "routes" / f"{ROUTES[route_id]}-restart.yaml", plan, data)

    assert added_restarts(guide, completed)  # the file has a restart the guide does not
    assert losses_at_item(plan, guide, completed, data, gap_item(data, route_id)) == ()


def test_the_check_names_the_loss_of_a_catch_all_restart_at_the_guides_gap(data):
    """The shape R04's completed route had before #599: the guide and a last `restart`. At the guide's gap the Annulment of its step 6 is legal."""
    plan = plan_of(data, "R04")
    guide = load_route(ROOT / "examples" / "routes" / "r04-penetrating-quiver.yaml", plan, data)
    text = (ROOT / "examples" / "routes" / "r04-penetrating-quiver.yaml").read_text(encoding="utf-8")
    old = parse_route(text.replace("name: R04, PoE Vault guide", "skip_refused: true") + "\n  - do: restart\n", plan, data, "old-completed")

    (loss,) = losses_at_item(plan, guide, old, data, gap_item(data, "R04"))

    assert "Orb of Annulment" in loss.legal and "Deafening Essence of Rage" not in loss.legal  # the game refuses the essence under the metamod
    assert loss.rule_line == old.rules[-1].line


def test_the_guides_own_restarts_are_not_checked(data):
    """R04's step 4 restart (another mod was fractured) is the guide's word: no rule of the guide's file counts as added."""
    plan = plan_of(data, "R04")
    guide = load_route(ROOT / "examples" / "routes" / "r04-penetrating-quiver.yaml", plan, data)

    assert added_restarts(guide, guide) == frozenset()
    assert "restart" not in guide_actions(guide) and "Deafening Essence of Rage" in guide_actions(guide)


def test_r14_keeps_the_attack_speed_where_the_exalted_orbs_left_the_chaos_damage_over_time_prefix_too_weak(data):
    """The state #619 measured (completion_check.py R14, run 42381244084): both metamods, the +1 gems, the Chaos Damage over Time prefix below the top tier.

    Before #619 the catch-all `restart` bought a new bow there and threw the tier-1 Attack Speed away while the guide's Bench craft, Remove Crafted Mods and
    Orb of Annulment were legal; now the crafts come off and the guide's step 3 goes on."""
    plan = plan_of(data, "R14")
    guide = load_route(ROOT / "examples" / "routes" / "r14-hunter-bow.yaml", plan, data)
    path = ROOT / "examples" / "routes" / "r14-hunter-bow-restart.yaml"
    item = rare(
        data, plan.target.base_id, 78, (SPEED, MULTIMOD, NO_ATTACK, "LocalIncreaseSocketedGemLevel1", "PoisonDamagePrefixInfluence3"), influences=frozenset({Influence.HUNTER})
    )
    text = path.read_text(encoding="utf-8")
    start, end = text.index("  # NOT IN THE GUIDE (a)"), text.index("  # NOT IN THE GUIDE (b)")
    old = parse_route(text[:start] + text[end:], plan, data, "r14-before-619")  # the file without the rule that keeps the Attack Speed

    (loss,) = losses_at_item(plan, guide, old, data, item)

    assert {"Bench craft +2 to Level of Socketed Support Gems", "Remove Crafted Mods", "Orb of Annulment"} <= set(loss.legal)
    assert losses_at_item(plan, guide, load_route(path, plan, data), data, item) == ()
