"""The planner imprints only an item worth coming back to (#1567; `Abstraction.imprint_offer_pruned`, `planner._plan.IMPRINTS_WORTH_SAVING`).

A player imprints an item he wants to come back to after a miss: one that holds the wanted mod hardest to roll and nothing he must take off again. On the
small amulet pool of `test_pattern_imprint.py` (a magic amulet, three wanted mods, the Alteration, Augmentation and Regal orbs, the
Annulment, the imprint and the restore under the cap of one):

* with the rule off (the abstraction's default) no imprint is left out; with it on, an imprint of an item holding no mod, an unwanted mod,
  a crafted one or not the rarest wanted mod is left out, one of wanted mods alone with the rarest among them is not, a restore never is;
* the kernel never reads it, so a given route that imprints elsewhere is walked as the game plays it;
* through the envelope search the rule removes options only: the mean is never below the search without it, the answer names the
  imprint it left out (`Prunings`, a limit that says the plan is the best found, not proved the cheapest).
"""

import pytest
from abstraction_pool import DAMAGE_2, LIFE_2, MANA_1, RESIST_3, SMALL, roll, small_item
from test_pattern_imprint import START, abstraction, priced_offers

from crafting_system.abstraction import PRUNED_IMPRINT
from crafting_system.actions import Imprint, Restore, imprint_actions
from crafting_system.items import Rarity
from crafting_system.planner._envelope_plan import envelope_result
from crafting_system.planner._limits import IMPRINTS, pruning_limits

IMPRINT = next(action for action in imprint_actions(SMALL, START, max_imprints=1) if isinstance(action, Imprint))
RESTORE = Restore(0)


def _state(ab, *mods, rarity=Rarity.MAGIC):
    return ab.compress(small_item(*mods, rarity=rarity))


def test_the_rule_is_off_unless_the_planner_sets_it():
    ab = abstraction(1)
    assert not ab.imprint_offer_pruned(_state(ab), IMPRINT)
    assert not ab.imprint_offer_pruned(_state(ab, roll(MANA_1)), IMPRINT)


def test_an_imprint_is_left_out_of_an_item_with_no_mod_an_unwanted_mod_a_crafted_one_or_not_the_rarest_wanted_mod_and_a_restore_never():
    ab = abstraction(1)
    ab.imprints_worth_saving = True
    assert ab.rarest_leaves() == {2}  # Added Lightning Damage weighs least of the three wanted mods in the amulet's pool
    rare = Rarity.RARE
    assert ab.imprint_offer_pruned(_state(ab), IMPRINT)  # nothing to come back to
    assert ab.imprint_offer_pruned(_state(ab, roll(DAMAGE_2), roll(MANA_1), rarity=rare), IMPRINT)  # an unwanted mod would have to come off
    assert ab.imprint_offer_pruned(_state(ab, roll(LIFE_2), roll(RESIST_3), rarity=rare), IMPRINT)  # wanted mods alone, not the rarest one
    assert not ab.imprint_offer_pruned(_state(ab, roll(DAMAGE_2)), IMPRINT)
    assert not ab.imprint_offer_pruned(_state(ab, roll(DAMAGE_2), roll(RESIST_3), rarity=rare), IMPRINT)
    assert not ab.imprint_offer_pruned(_state(ab), RESTORE)
    # the kernel is the game's: the imprint of an unwanted mod is still a move a given route can walk
    assert ab.kernel(_state(ab, roll(MANA_1)), IMPRINT)


def test_through_the_envelope_search_the_rule_only_removes_options_and_the_answer_names_it():
    free_ab = abstraction(1)
    free_first = free_ab.compress(START)
    free = envelope_result(free_ab, free_first, priced_offers(1))
    assert not free_ab.prunings.labels(PRUNED_IMPRINT)
    ruled_ab = abstraction(1)
    ruled_ab.imprints_worth_saving = True
    first = ruled_ab.compress(START)
    ruled = envelope_result(ruled_ab, first, priced_offers(1))
    assert ruled.solution.values[first] >= free.solution.values[free_first] * (1 - 1e-9)
    assert ruled_ab.prunings.labels(PRUNED_IMPRINT)
    (limit,) = [limit for limit in pruning_limits(ruled_ab.prunings) if limit.kind == IMPRINTS]
    assert "not proved" in limit.guarantee
    from crafting_system.planner._limits import TITLES

    assert IMPRINTS in TITLES  # the page has a title for its group


def test_the_rule_reads_only_what_a_pattern_key_holds_so_every_member_of_a_key_answers_alike():
    # the statuses and the count of the mods decide, not which slot passes: the bound's build (one member of a key) and the search (each
    # state) agree
    ab = abstraction(1)
    ab.imprints_worth_saving = True
    rare = Rarity.RARE
    two_wanted, one_unwanted = _state(ab, roll(DAMAGE_2), roll(RESIST_3), rarity=rare), _state(ab, roll(DAMAGE_2), roll(MANA_1), rarity=rare)
    assert len(two_wanted.slots) == len(one_unwanted.slots) == 2
    assert not ab.imprint_offer_pruned(two_wanted, IMPRINT) and ab.imprint_offer_pruned(one_unwanted, IMPRINT)


def test_the_planner_plans_with_the_rule_on_and_its_switch_turns_it_off(monkeypatch):
    from abstraction_support import real_game_data
    from pathlib import Path

    from crafting_system.cli import make_plan
    from crafting_system.planner import _plan
    from crafting_system.prices import load_price_file
    from crafting_system.targets import load_target

    root = Path(__file__).resolve().parents[1]
    data = real_game_data()
    target = load_target(root / "examples" / "targets" / "r17-lightning-talisman.yaml", data)
    prices = load_price_file(root / "tests" / "fixtures" / "prices" / "references-allflame-2026-07-31.json")
    assert make_plan(data, target, prices, solve_it=False).abstraction.imprints_worth_saving
    monkeypatch.setattr(_plan, "IMPRINTS_WORTH_SAVING", False)
    assert not make_plan(data, target, prices, solve_it=False).abstraction.imprints_worth_saving
