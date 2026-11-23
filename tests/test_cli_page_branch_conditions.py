"""Every outcome line of a step says what a player checks on his item to know where it goes, and a step reads in the order a player takes it (#1442).

The heavy plans of 2026-11-23 (R13, R14) had branches told apart by nothing the page named: an Exalted Orb's "then Orb of Annulment" beside
"not yet, this step again", a Regal Orb's two "then ..." lines, where the items differed only in the mods the target does not need. A sure
craft that removes wanted crafted mods (Remove Crafted Mods) printed its every outcome under "On failure", and a row reached only from a loop
sat between the rows of the straight path with nothing saying where a player comes to it from. Small hand-made policies on a belt, drawn through
the page's entry (`build_section`), with the words worked out by hand from the policy.
"""

from items_support import DATA, roll
from route_view_support import COLD_REQ, DAMAGE, FRACTURED_COLD, LIFE, belt, crafted_damage, hand_input

from crafting_system.abstraction import Status
from crafting_system.cli._route_flow import Edge, Flow, Step
from crafting_system.cli._route_view import AGAIN, NEXT, REACHED_FROM, SURE_NEXT, _View, build_section
from crafting_system.targets import Requirement

DAMAGE_REQ = Requirement("AllDamage", None, frozenset({DAMAGE}))
JUNK_PREFIX = roll("IncreasedLife1")  # a prefix: Life is not asked for by these targets, so it is a mod the target does not need
JUNK_ES = roll("IncreasedEnergyShield1")  # another prefix the target does not need


def _unwanted_prefixes(state) -> int:
    return sum(1 for slot in state.slots if not slot.crafted and slot.side.value == "prefix" and Status.PASSING not in slot.contribution)


def chaos_until_no_unwanted_prefix(state, ab):
    """A Chaos Orb until the item holds at most one prefix the target does not need (a Chaos Orb's item always holds one here: the fractured
    Cold is its only wanted mod), then the bench craft (a prefix) finishes it: the two branches of the Chaos Orb differ only in the item's
    unwanted prefixes. Worked by hand: the bench's items hold exactly one, the Chaos Orb's again two (the abstraction keeps no more than the
    bench craft's free prefix needs)."""
    if state.crafted:
        return None
    return "Chaos Orb" if _unwanted_prefixes(state) > 1 else "Benchcraft: All Damage"


def lines(row, label: str) -> list[str]:
    return [line.text for field in row.fields if field.label == label for line in field.lines]


def test_branches_told_apart_only_by_the_mods_the_target_does_not_need_say_so():
    section = build_section(hand_input(belt(FRACTURED_COLD, JUNK_PREFIX, JUNK_ES), (COLD_REQ, DAMAGE_REQ), chaos_until_no_unwanted_prefix), DATA)
    (chaos,) = [row for row in section.rows if row.title == "Chaos Orb"]

    chances = lines(chaos, "Chance per use")
    onward = [text for text in chances if "then Benchcraft" in text]
    again = [text for text in chances if AGAIN in text]
    assert len(onward) == 1 and onward[0].startswith("with an unwanted prefix, then Benchcraft: ")
    assert len(again) == 1 and again[0].startswith(f"with 2 unwanted prefixes, {AGAIN}: ")


def test_the_words_of_a_branch_hold_on_every_item_of_it_and_on_none_of_the_others():
    """The words are read off the item: checked here on each item the Chaos Orb leaves, by its own unwanted prefixes."""
    view = _View(hand_input(belt(FRACTURED_COLD, JUNK_PREFIX, JUNK_ES), (COLD_REQ, DAMAGE_REQ), chaos_until_no_unwanted_prefix), DATA, None, "", True)
    (chaos,) = [step for step in view.flow.steps if step.action is not None and step.action.label == "Chaos Orb"]
    by_words = {view.item_words(chaos, edge): edge for edge in chaos.edges if edge.kind != "goal"}

    assert set(by_words) == {"with an unwanted prefix", "with 2 unwanted prefixes"}
    assert {_unwanted_prefixes(state) for state in by_words["with an unwanted prefix"].states} == {1}
    assert {_unwanted_prefixes(state) for state in by_words["with 2 unwanted prefixes"].states} == {2}


def remove_then_chaos(state, ab):
    """Remove Crafted Mods on the crafted start (it takes off the crafted All Damage the target asks for), then a Chaos Orb until Life
    lands, then the bench craft again: the removal is the sure craft's one outcome, not a failure of it."""
    life = state.status[1] is Status.PASSING
    if state.crafted:
        return None if life else "Remove Crafted Mods"
    return "Benchcraft: All Damage" if life else "Chaos Orb"


def test_a_sure_craft_that_removes_wanted_crafted_mods_reads_as_its_next_step_not_as_a_failure():
    start = crafted_damage(belt(FRACTURED_COLD))
    view = _View(hand_input(start, (COLD_REQ, LIFE, DAMAGE_REQ), remove_then_chaos), DATA, None, "", True)
    section = build_section(hand_input(start, (COLD_REQ, LIFE, DAMAGE_REQ), remove_then_chaos), DATA)
    (remove,) = [row for row in section.rows if row.title.endswith("Remove Crafted Mods")]

    assert lines(remove, "On failure") == []  # it never misses: removing is what it is used for (R13 step 13)
    assert "crafted mods removed" in lines(remove, "Goal")
    (step,) = [step for step in view.flow.steps if step.action is not None and step.action.label == "Remove Crafted Mods"]
    (edge,) = step.edges
    assert edge.kind == "failure" and edge.lost  # the flow still counts the loss: the page says it as the craft's purpose
    words, _ = view.edge_phrase(step, edge)
    assert words.endswith("· crafted removed") and "lost" not in words  # the one crafted mod it took off
    assert all("lost" not in text for text in lines(remove, NEXT) + lines(remove, SURE_NEXT))


def test_a_row_the_row_above_does_not_lead_to_says_where_it_is_reached_from_and_no_other_row_does():
    """R14's shape, by hand: row 2 leads to rows 3 and 4, row 3 only back to row 2, row 4 to the target. A player reading down from row 3
    would take row 4 next, so row 4 says it is reached from step 2; rows 2 and 3 follow the row above them and say nothing."""
    view = _View(hand_input(belt(FRACTURED_COLD, JUNK_PREFIX, JUNK_ES), (COLD_REQ, DAMAGE_REQ), chaos_until_no_unwanted_prefix), DATA, None, "", True)
    steps = (
        Step(1, (), None, "first", (Edge("forward", 2, 0.5, ()), Edge("forward", 3, 0.5, ())), None, None),
        Step(2, (), None, "loop", (Edge("forward", 1, 1.0, ()),), None, None),
        Step(3, (), None, "last", (Edge("goal", None, 1.0, ()),), None, None),
    )
    view.flow = Flow(steps, {})

    assert [view.reached_from(row) for row in (2, 3)] == [None, None]
    field = view.reached_from(4)
    assert field is not None and field.label == REACHED_FROM
    assert [(line.text, line.href) for line in field.lines] == [("step 2: no action", "#s2")]


def test_a_branch_of_two_kinds_of_item_names_each_kind_joined_by_or():
    """By hand: the branch holds items with Life, and items with an unwanted prefix and no Life; the other branch items with neither. No one
    condition holds on all of the branch, so the words are one kind each: "with Life, or with an unwanted prefix"."""
    import numpy as np

    from crafting_system.cli._route_view import _Column, _kinds, _Table, _words

    columns = (_Column("with", "Life", (0, 0)), _Column("with", "an unwanted prefix", (3, 1)), _Column("without", "an unwanted prefix", (3, 2)))
    #                 mine: Life, Life+junk, junk | others: plain, plain
    tests = np.array([[1, 1, 0, 0, 0], [0, 1, 1, 0, 0], [1, 0, 0, 1, 1]], dtype=bool)
    table = _Table({}, columns, tests)
    on_mine, on_others = tests[:, :3], tests[:, 3:]
    kinds = _kinds(table, on_mine, on_others, np.ones(2, dtype=bool))

    assert kinds is not None
    assert ", or ".join(_words([columns[c] for c in kind]) for kind in kinds) in ("with Life, or with an unwanted prefix", "with an unwanted prefix, or with Life")
