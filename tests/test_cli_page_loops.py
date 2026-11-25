"""A step of the route page names the step its item goes on to wherever that is not the row right below: a loop back reads as one (#1442).

The heavy plans of 2026-11-23 (R04, R14, R13) had steps with no next step where the route goes on: a sure step (a bench craft, a Scouring) whose
one outcome goes back to an earlier step, a step with one forward branch that is not the row below, and restart lines that named neither their
step nor what the restart costs. Small hand-made policies on a belt, drawn through the page's entry (`build_section`).
"""

import re

from items_support import DATA
from route_view_support import COLD_REQ, DAMAGE, FRACTURED_COLD, HYSTERIA_REQ, LIFE, belt, hand_input

from crafting_system.abstraction import Status
from crafting_system.cli._route_view import DECIDE, NEXT, SURE_NEXT, build_section
from crafting_system.targets import Requirement

DAMAGE_REQ = Requirement("AllDamage", None, frozenset({DAMAGE}))


def _junk(state) -> int:
    return sum(1 for slot in state.slots if not slot.crafted)


def chaos_then_bench_back(state, ab):
    """A Chaos Orb on the start belt; an item it leaves with three other mods gets the bench craft, and the crafted item goes back to the
    Chaos Orb: the bench row's one outcome leads to the earlier row (the shape of R04's lock and Scour)."""
    return "Benchcraft: All Damage" if not state.crafted and _junk(state) == 3 else "Chaos Orb"


def bench_then_chaos(state, ab):
    """The bench craft on an item with no crafted mod, a Chaos Orb on the crafted one: the bench row's one outcome is the row below."""
    return "Chaos Orb" if state.crafted else "Benchcraft: All Damage"


def lines(row, label: str):
    return [line for field in row.fields if field.label == label for line in field.lines]


def test_a_sure_step_whose_one_outcome_goes_back_to_an_earlier_step_names_it():
    section = build_section(hand_input(belt(FRACTURED_COLD), (COLD_REQ, LIFE), chaos_then_bench_back), DATA)
    chaos, bench = section.rows[1], section.rows[2]
    assert chaos.title == "Chaos Orb" and bench.title.startswith("Benchcraft")

    (onward,) = lines(bench, NEXT)
    assert (onward.text, onward.href, onward.anchor) == ("then Chaos Orb", "#s2", "→ step 2")


def test_every_branch_of_a_step_with_several_names_its_step_the_row_below_too():
    section = build_section(hand_input(belt(FRACTURED_COLD), (COLD_REQ, LIFE), chaos_then_bench_back), DATA)
    chaos = section.rows[1]

    onward = [line for line in lines(chaos, "Chance per use") if not line.text.startswith("the target")]
    assert onward and all(line.anchor == "→ step 3" and line.href == "#s3" for line in onward)  # step 3 is the row below


def test_a_sure_step_whose_one_outcome_is_the_row_below_says_nothing_more():
    section = build_section(hand_input(belt(FRACTURED_COLD), (COLD_REQ, LIFE), bench_then_chaos), DATA)
    bench, chaos = section.rows[1], section.rows[2]
    assert bench.title.startswith("Benchcraft") and chaos.title == "Chaos Orb"

    assert lines(bench, NEXT) == []  # the arrow between the rows says it


def bench_then_by_life(state, ab):
    """The bench craft on any item with no crafted mod; then the essence on the item that has life, a Chaos Orb on the one that has not."""
    if not state.crafted:
        return "Benchcraft: All Damage"
    return "Essence of Hysteria" if state.status[1] is Status.PASSING else "Chaos Orb"


def test_the_branches_of_a_sure_craft_that_all_get_the_crafted_mod_are_told_apart_by_the_item():
    """Every branch of the bench craft gets the crafted mod, so that mod tells none apart (R13 step 7, #1442): each says what its item has."""
    section = build_section(hand_input(belt(FRACTURED_COLD), (COLD_REQ, LIFE, HYSTERIA_REQ, DAMAGE_REQ), bench_then_by_life), DATA)
    bench = section.rows[1]

    onward = {line.text.split(", then ")[-1].split(":")[0]: line.text for line in lines(bench, SURE_NEXT) if not line.text.startswith("the target")}
    assert set(onward) == {"Chaos Orb", "Essence of Hysteria"}
    rows = [line.text for line in lines(bench, DECIDE)[1:]]  # the item is told in the step's list, read from the top (#1526)
    assert rows in (
        ["with +# to maximum Life · any tier: then Essence of Hysteria", "else any other item: then Chaos Orb"],
        ["without +# to maximum Life · any tier: then Chaos Orb", "else any other item: then Essence of Hysteria"],
    )


def test_a_wanted_mod_a_fracturing_orb_hits_is_named_though_the_state_holds_it_as_its_family_type():
    """R13's Fracturing Orb (60% of the plan) read as "an orb wasted on a junk mod": the state holds a fractured mod as its family type ("~3")
    when the orb may hit any mod, and the page called every such mod "a mod of a family no requirement cares about" (#1442). The mod is
    named by what it gives the goal; only a mod that gives it nothing is that."""
    from test_abstraction_fracture import FRACTURE, fracturing, start_of

    from crafting_system.cli._route_card import FAMILY_TYPE_TEXT, _StateReader

    ab = fracturing()
    reader = _StateReader(ab)
    named = {}
    for after in ab.kernel(ab.compress(start_of("gem", None)), FRACTURE):
        (entry,) = after.fractured
        assert entry.mod_id.startswith("~")  # every hit is held as its family type here
        named[Status.PASSING in entry.contribution] = reader.fractured(entry.mod_id, entry.contribution)[1]

    assert named[False].text == FAMILY_TYPE_TEXT
    assert named[True].text != FAMILY_TYPE_TEXT and named[True].tone == "wanted" and "fractured" in named[True].marks


def test_a_branch_whose_items_hold_different_counts_of_open_slots_is_told_by_the_range_that_parts_it_from_the_others():
    """R04 step 10: the items that go on to the Exalted Orb have 1 or 2 open prefixes, the others none; "at least 1 open prefix" says it."""
    from test_cli_page_spends_and_sure_steps import START, bench_then_by_the_item

    from crafting_system.cli._route_view import _View

    view = _View(hand_input(START, (COLD_REQ, LIFE), bench_then_by_the_item), DATA, None, "", True)
    (bench,) = [step for step in view.flow.steps if step.action is not None and step.action.label.startswith("Benchcraft")]
    mine, other = sorted((edge for edge in bench.edges if edge.kind == "forward"), key=lambda edge: -len(edge.states))
    assert len(mine.states) >= 2
    counts = {state: (1 + k % 2, 1) for k, state in enumerate(mine.states)} | {state: (0, 1 + k % 2) for k, state in enumerate(other.states)}
    view._free_slots = counts.get  # the counts of open slots, made to differ inside a branch
    seen = view._traits
    view._traits = lambda state: {key: value for key, value in seen(state).items() if key[0] != "junk"}  # the mods the target does not need part nothing here

    words = view.item_words(bench, mine, [other])
    assert words == "with at least 1 open prefix"


def test_a_branch_whose_items_had_different_mods_fractured_names_the_ones_they_may_be():
    """R13 step 10: every item of a branch had a mod fractured, not the same one; the line says which they may be, not nothing (#1442)."""
    import dataclasses

    from crafting_system.abstraction import FracturedMod
    from crafting_system.cli._route_view import _View

    view = _View(hand_input(belt(FRACTURED_COLD), (COLD_REQ, LIFE), chaos_then_bench_back), DATA, None, "", True)
    chaos = next(step for step in view.flow.steps if step.action is not None and step.action.label == "Chaos Orb")
    edge = next(edge for edge in chaos.edges if edge.kind == "forward")
    hit = [FracturedMod(mod_id, (Status.ABSENT,) * len(view.plan.leaf_labels)) for mod_id in ("IncreasedLife1", "LifeRegeneration1")]
    state = edge.states[0]
    states = tuple(dataclasses.replace(state, fractured=(*state.fractured, mod)) for mod in hit)  # two items, each with another mod fractured

    (words,) = view.appeared(chaos, dataclasses.replace(edge, states=states))
    assert words.startswith("one of these fractured: ") and words.count(";") == 1


def _fractured_branch(*hits):
    """The Chaos Orb row of a belt and its forward edge, its items made one per `hits` entry: each with that mod fractured (None: none)."""
    import dataclasses

    from crafting_system.abstraction import FracturedMod
    from crafting_system.cli._route_view import _View

    view = _View(hand_input(belt(FRACTURED_COLD), (COLD_REQ, LIFE), chaos_then_bench_back), DATA, None, "", True)
    chaos = next(step for step in view.flow.steps if step.action is not None and step.action.label == "Chaos Orb")
    edge = next(edge for edge in chaos.edges if edge.kind == "forward")
    life = view.plan.leaf_labels.index(next(label for label in view.plan.leaf_labels if "Life" in label))

    def mod(mod_id: str, wanted: bool) -> FracturedMod:
        contribution = tuple(Status.PASSING if wanted and i == life else Status.ABSENT for i in range(len(view.plan.leaf_labels)))
        return FracturedMod(mod_id, contribution)

    def hit_on(state, mod_id: str, wanted: bool):
        status = tuple(Status.PASSING if wanted and i == life else s for i, s in enumerate(state.status))  # a wanted mod meets its leaf
        return dataclasses.replace(state, fractured=(*state.fractured, mod(mod_id, wanted)), status=status)

    state = edge.states[0]
    states = tuple(state if hit is None else hit_on(state, *hit) for hit in hits)
    return view, chaos, dataclasses.replace(edge, states=states)


def test_a_branch_whose_items_had_different_wanted_mods_fractured_reads_one_of_these():
    view, chaos, edge = _fractured_branch(("IncreasedLife1", True), ("IncreasedLife2", True))

    words, names_row = view.edge_phrase(chaos, edge)
    first, second = sorted(view._fractured_text(entry).removesuffix(" · fractured") for state in edge.states for entry in state.fractured[-1:])
    assert view.appeared(chaos, edge) == [f"one of these fractured: {first}; {second}"]  # the Life leaf they meet is named as the mods, once
    assert words.startswith(f"one of these fractured: {first}; {second}") and not names_row


def test_a_branch_of_a_wanted_mod_and_a_junk_mod_fractured_names_both():
    view, chaos, edge = _fractured_branch(("IncreasedLife1", True), ("LifeRegeneration1", False))

    words, _ = view.edge_phrase(chaos, edge)
    assert words.startswith("one of these fractured: ") and words.split(", ")[0].count(";") == 1


def test_a_branch_whose_items_hold_one_mod_fractured_two_ways_names_it_once():
    view, chaos, edge = _fractured_branch(("IncreasedLife1", True), ("IncreasedLife1", False))  # one mod, read for the goal two ways

    (words,) = view.appeared(chaos, edge)
    assert words == f"{view._fractured_text(edge.states[0].fractured[-1])}"


def test_a_branch_where_one_item_had_no_new_mod_fractured_says_nothing_of_a_fracture():
    view, chaos, edge = _fractured_branch(("IncreasedLife1", True), None)

    assert view.appeared(chaos, edge) == []
    words = view.edge_phrase(chaos, edge)[0]  # it may say what the item has not fractured ("without ... fractured"), never that one was
    assert "one of these fractured" not in words and not re.search(r"(^|, )with [^,]*fractured", words)
