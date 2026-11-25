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
