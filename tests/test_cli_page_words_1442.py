"""The route page's left faults of #1442 (and of #1514, #893 that the same code answers), each through the page writer's own pieces.

* the planner's limits in a player's words: no "model", no "kind", no "state", fossil sets by game names, the socket methods apart on a
  target with no sockets (`_limit_words`);
* the title names the wanted mods (#893);

The essence's note on an item with no fractured mod (R09, R20) is in the golden of the essence step on the belt; the rest (a bench craft paid
again, a listing that goes on the same way, the lower tiers of a leaf named by its top mod) is read on the redrawn reference pages.
"""

from __future__ import annotations

import dataclasses
import re

import pytest
from cli_support import R12, price_file
from items_support import DATA

from crafting_system.budget import Budget
from crafting_system.cli import make_plan
from crafting_system.cli._limit_words import fossil_name, group_words, page_limits, player_words
from crafting_system.cli._route_view import build_section, page_title, route_input, short_mod
from crafting_system.planner import Limit, kind_title
from crafting_system.planner import _limits
from crafting_system.targets import load_target

PLANNER_WORDS = re.compile(r"\bthe model\b|\bkinds?\b|\bstates?\b|methods setting|\bFossils ", re.I)


@pytest.fixture(scope="module")
def r12():
    return make_plan(DATA, load_target(R12, DATA), price_file(), budget=Budget.in_states(200_000))


def test_every_limit_and_group_title_of_the_page_is_in_a_player_s_words(r12):
    section = build_section(route_input(r12), DATA)
    for field in section.goal.leaves_out:
        assert not PLANNER_WORDS.search(field.label), field.label
        for line in field.lines:
            assert not PLANNER_WORDS.search(line.text), line.text
            assert not any(PLANNER_WORDS.search(entry) for entry in line.more), line.more


@pytest.mark.parametrize(
    "planner, page",
    [
        ("Not offered: Recombinators (kinds that are offered only when the run's methods setting names them). Among the kinds offered, the plan is cheapest. A kind left out could be cheaper.",
         "Not offered: Recombinators (left out of a run unless it is set to use them). Among the methods offered, the plan is cheapest. A method left out could be cheaper."),
        ("Not offered: X (the model has no rule for them on this item: two fossils ..., and the model has no rule for how the game counts them).",
         "Not offered: X (the planner cannot yet work out what they do on this item: two fossils ..., and the planner has no rule for how the game counts them)."),
        ("Left out where the model has no rule: Chaos Orb in 1,280 states", "Left out where the planner has no rule: Chaos Orb in 1,280 items along the route"),
        ("(the search stopped by itself, after 1 rounds and 655,225 states looked at, as soon as ...)", "(the search stopped by itself, after weighing 655,225 items along the way, as soon as ...)"),
        ("(it looked at the actions of 1 of the 2 states it found and built 1 of the 2 actions offered at them: ...)",
         "(it weighed the actions on 1 of the 2 items it met along the way and built 1 of the 2 actions offered there: ...)"),
        ("Not offered, 2 in all: Fossils Bloodstained Fossil, Fossils Glyphic Fossil + Frigid Fossil", "Not offered, 2 in all: Bloodstained Fossil, Glyphic Fossil + Frigid Fossil"),
    ],
)
def test_a_planner_sentence_is_said_in_a_player_s_words(planner, page):
    assert player_words(planner) == page


def test_a_fossil_set_is_named_by_its_fossils_and_a_group_title_is_a_player_s():
    assert fossil_name("Fossils Glyphic Fossil") == "Glyphic Fossil"
    assert group_words("Methods the model cannot list for this item") == "Methods the planner cannot work out on this item"
    assert group_words("Actions the model has no rule for in some states") == "Actions the planner cannot work out on some items of the route"


def test_on_a_target_with_no_sockets_the_socket_methods_are_said_apart_and_none_is_lost(r12):
    assert r12.target.sockets is None
    sockets = tuple(kind_title(name) for name in ("jewellers-orb", "chromatic-orb"))
    whole = Limit(_limits.NOT_BUILT, "Not offered", "methods the planner cannot use yet", "Among the methods the planner can use, the plan is cheapest.", labels=("Tempering", *sockets), approximate="x")
    split = page_limits((whole,), r12.target)
    assert [limit.labels for limit in split] == [("Tempering",), sockets]
    assert "the target asks for none" in split[1].why and "unaffected" in split[1].guarantee
    asked = dataclasses.replace(r12.target, sockets=object())  # a target that asks for sockets keeps them among the methods that leave the plan unproved
    assert page_limits((whole,), asked) == (whole,)


def test_the_title_names_the_item_and_its_wanted_mods_in_short(r12):
    title = page_title(DATA, r12.target)
    assert title.startswith("Route to craft: ") and ", with " in title
    assert short_mod("+(13-14)% chance to Suppress Spell Damage") == "Suppress Spell Damage"
    assert short_mod("+# to maximum Life") == "maximum Life"
    assert short_mod("#% increased Movement Speed / (13-16)% chance to gain Onslaught for 4 seconds on Kill") == "Movement Speed"
    assert short_mod("Adds # to # Physical Damage to Attacks") == "Adds # to # Physical Damage to Attacks"


def test_a_fossil_set_in_a_batch_of_the_search_is_named_by_its_fossils_and_a_reduced_mod_keeps_its_word():
    from crafting_system.cli._route_proof import method_name

    assert method_name("Fossils Glyphic Fossil") == "Glyphic Fossil"  # the batches' path (checker, #1442)
    assert short_mod("#% reduced Mana Cost of Skills") == "reduced Mana Cost of Skills"
    assert short_mod("-#% to Chaos Resistance") == "-#% to Chaos Resistance"
