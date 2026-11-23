"""A step of the route page names the step its item goes on to wherever that is not the row right below: a loop back reads as one (#1442).

The heavy plans of 2026-11-23 (R04, R14, R13) had steps with no next step where the route goes on: a sure step (a bench craft, a Scouring) whose
one outcome goes back to an earlier step, a step with one forward branch that is not the row below, and restart lines that named neither their
step nor what the restart costs. Small hand-made policies on a belt, drawn through the page's entry (`build_section`).
"""

from items_support import DATA
from route_view_support import COLD_REQ, FRACTURED_COLD, LIFE, belt, hand_input

from crafting_system.cli._route_view import NEXT, build_section


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
