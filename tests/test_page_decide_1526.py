"""Where a step's items go, as a list read from the top (#1526): the rule learner of `cli/_route_decide`, on hand-made tables.

A row only parts its items from the items of the rows below it, so each row takes few conditions and the last one none; an item the first
row that holds on it sends somewhere else than its own branch would send a player wrong, so every list is checked item by item.
"""

import numpy as np

from crafting_system.cli._route_decide import decision_list


def first_place(rows, tests, i):
    return next(label for conditions, label in rows if conditions is None or all(tests[c, i] for c in conditions))


def test_every_item_meets_its_own_branch_first():
    # conditions: 0 "with Life", 1 "with an unwanted prefix", 2 "with an open suffix"; items: 6, labels: where each goes
    tests = np.array(
        [
            [1, 1, 0, 0, 0, 0],
            [0, 1, 1, 1, 0, 0],
            [1, 0, 1, 0, 1, 0],
        ],
        dtype=bool,
    )
    labels = np.array([2, 2, 3, 3, 4, 5])
    mass = np.array([0.3, 0.1, 0.2, 0.1, 0.2, 0.1])

    rows = decision_list(tests, labels, mass)

    assert rows[-1][0] is None
    assert all(first_place(rows, tests, i) == labels[i] for i in range(labels.size))
    assert all(len(conditions) <= 3 for conditions, _ in rows[:-1])


def test_the_rule_comes_last_and_its_exceptions_first():
    """An Essence step's shape (R24 step 2): most items go back to the essence; two small kinds go on. Said against all the rest at once the
    essence's branch needs several rows ("this step again" four times); with the exceptions first it is the one last row."""
    # conditions: 0 "with an open suffix", 1 "with 2 unwanted prefixes", 2 "with Suppress" (no one condition holds on the essence's items alone)
    tests = np.array(
        [
            [1, 0, 0, 0, 1, 0, 0, 0],
            [0, 1, 0, 0, 0, 1, 0, 0],
            [1, 1, 0, 0, 0, 0, 0, 0],
        ],
        dtype=bool,
    )
    labels = np.array([4, 3, 1, 1, 1, 1, 1, 1])  # 1: this step again; 3: Annulment; 4: Exalted Orb
    mass = np.array([0.02, 0.01, 0.2, 0.2, 0.2, 0.17, 0.1, 0.1])

    rows = decision_list(tests, labels, mass)

    assert all(first_place(rows, tests, i) == labels[i] for i in range(labels.size))
    assert len(rows) == 3 and rows[-1] == (None, 1)


def test_a_list_prefers_with_to_without_when_both_are_as_short():
    tests = np.array([[1, 1, 0, 0], [0, 0, 1, 1]], dtype=bool)  # 0 "with A", 1 "without A"
    labels = np.array([7, 7, 8, 8])
    mass = np.array([0.1, 0.1, 0.4, 0.4])

    rows = decision_list(tests, labels, mass, negative=np.array([False, True]))

    assert rows == [((0,), 7), (None, 8)]


def test_items_a_player_sees_alike_are_one_item_to_the_rows():
    tests = np.array([[1, 1, 0], [0, 0, 1]], dtype=bool)
    labels = np.array([5, 5, 6])  # the caller gives look-alike items one label: two equal columns never part

    rows = decision_list(tests, labels, np.array([0.5, 0.25, 0.25]))

    assert len(rows) == 2 and all(first_place(rows, tests, i) == labels[i] for i in range(3))


# -- the field on the page, on the hand-made belt of `test_cli_page_branch_conditions` -------------------------------------------------


def _chaos_view():
    from items_support import DATA
    from route_view_support import COLD_REQ, FRACTURED_COLD, belt, hand_input
    from test_cli_page_branch_conditions import DAMAGE_REQ, JUNK_ES, JUNK_PREFIX, chaos_until_no_unwanted_prefix

    from crafting_system.cli._route_view import _View

    view = _View(hand_input(belt(FRACTURED_COLD, JUNK_PREFIX, JUNK_ES), (COLD_REQ, DAMAGE_REQ), chaos_until_no_unwanted_prefix), DATA, None, "", True)
    (chaos,) = [step for step in view.flow.steps if step.action is not None and step.action.label == "Chaos Orb"]
    return view, chaos


def test_the_rows_shares_and_the_targets_chance_add_up_to_every_use():
    view, chaos = _chaos_view()
    goal = sum(edge.chance for edge in chaos.edges if edge.kind == "goal")
    assert abs(sum(share for *_, share in view.decisions(chaos)) + goal - 1.0) < 1e-9


def test_a_long_list_shows_its_first_rows_and_the_rest_below_and_look_alike_items_say_so():
    from crafting_system.cli._route_decide import SHOWN_ROWS
    from crafting_system.cli._route_view import DECIDE

    view, chaos = _chaos_view()
    edges = [edge for edge in chaos.edges if edge.kind != "goal"]
    rows = [(f"with condition {n}", [(edges[n % len(edges)], 1.0)], (0,), 0.01) for n in range(SHOWN_ROWS + 3)]
    rows.append(("", [(edges[0], 0.75), (edges[-1], 0.25)], (), 0.5))
    view.__dict__["_decisions"] = {chaos.number: rows}

    field = view.decision_field(chaos)

    assert field is not None and field.label == DECIDE
    shown = field.lines[1:]
    assert len(shown) == SHOWN_ROWS
    assert shown[-2].text == f"else check the other {len(rows) - SHOWN_ROWS + 1} rows, in this order, before the last row"
    assert len(shown[-2].more) == len(rows) - SHOWN_ROWS + 1  # every row is on the page, the rarer middle folded
    assert shown[-1].text.startswith("else any other item: items that look alike go on differently (50%): ")
    assert "on 75%" in shown[-1].text and "on 25%" in shown[-1].text


def test_a_veiled_mod_is_drawn_as_the_game_names_it_and_counts_apart_from_the_unwanted_mods():
    from crafting_system.abstraction import Slot as StateSlot
    from crafting_system.abstraction import Status
    from crafting_system.items import Side

    import pytest

    view, _ = _chaos_view()
    if "VeiledPrefix" not in view.data.mods:
        pytest.skip("the game data of these tests holds no veiled mod")
    leaves = len(view.plan.leaf_labels)
    row = view.reader.family(StateSlot(Side.PREFIX, "VeiledPrefix", (Status.ABSENT,) * leaves))

    assert (row.text, row.marks) == ("Veiled Prefix", ("veiled",))
    assert view._veiled("VeiledPrefix")
    assert not view._veiled("JunMasterVeiledMovementVelocityAndOnslaughtOnKill")  # an unveiled mod (domain "unveiled") is no veiled mod


def test_an_unwanted_mod_of_a_wanted_mods_family_blocks_it():
    view, _ = _chaos_view()
    cold = next(i for i, label in enumerate(view.plan.leaf_labels) if "Cold" in label)

    assert cold in view._blocked_leaves("ColdResistance")
    assert view._blocked_leaves("~3") == ()  # a family type names no family


def test_the_goal_card_says_the_divine_rate_and_the_implicit_the_target_does_not_ask():
    view, _ = _chaos_view()

    (line,) = view.divine_line(())
    assert line.startswith("Divine Orb: ") and line.endswith("the Divine figures of this page are at this rate")
    base = view.data.base_items[view.ab.base_id]
    if base.implicits:
        (said,) = view.implicit_lines()
        assert said.startswith("not asked: the base's own implicit (")


def test_items_no_three_conditions_part_get_rows_of_their_own_and_are_never_sent_elsewhere():
    """Sixteen items told by four facts (with and without each), sent by the parity of the facts held: every conjunction of three conditions
    holds on two items of different places, so no short row is pure and each item is said by its every fact (the learner once gave what was
    left to the heaviest place, which sent R17's kept +1 Gems to the Restore)."""
    bits = np.array([[(i >> b) & 1 for i in range(16)] for b in range(4)], dtype=bool)
    tests = np.concatenate((bits, ~bits))
    labels = bits.sum(axis=0) % 2
    mass = np.linspace(1.0, 2.0, 16)

    rows = decision_list(tests, labels, mass)

    assert all(first_place(rows, tests, i) == labels[i] for i in range(labels.size))
