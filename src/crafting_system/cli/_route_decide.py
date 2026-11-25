"""Where a step's items go next, as a list a player reads from the top: the first row whose conditions hold on his item says the step (#1526).

The plan picks the next action by the item a use leaves, so the items of two branches of a step are told apart by what a player sees on
them (the wanted mods held and their tiers, crafted and fractured mods, the mods the target does not need on each side with their attack or
caster tag, the veiled mods, the open slots, the rarity: hand test H63, 0 misses on R11, R13, R14, R17, R20, R24 once the veiled mods are
in). Said branch by branch against every other branch at once, a branch of many kinds of item took four kinds of four conditions each (300
to 600 characters, "with A and B, or with C and D, or ..."), or no words at all. Said as a decision list, each row only parts its items
from the items of the rows below it, so a row takes one to three conditions and the last row none ("any other item").

`decision_list` is the greedy rule learner of H63 (`.claude/scratch/h63/h63.py`, `learn1`): each row is the conjunction of at most
`MOST_CONDITIONS` conditions that covers the most of what is left of one label and nothing of another, the most visits first (a player meets
the common items first), fewer conditions on a tie; it is run once scoring by visits and once by items, and the shorter list is kept. Items
whose conditions are all equal and whose labels differ cannot be parted by any row: the caller gives them one label of their own beforehand
(`_View.decisions`: "items that look alike", which is a question for the planner, not page wording).
"""

from __future__ import annotations

import numpy as np

MOST_CONDITIONS = 3  # the most conditions one row joins: past them a row no longer reads as a check a player makes
TRIPLE_POOL = 24  # the conditions a triple is formed from: the ones that each cover the most of what is left
LAST_TRIED = 3  # the heaviest places tried as the last row ("any other item"): each try is a whole list
SHOWN_ROWS = 8  # the most rows a step shows; the rarer rest is in a list below them (the stage board's form)


def decision_list(tests: np.ndarray, labels: np.ndarray, mass: np.ndarray, negative: np.ndarray | None = None) -> list[tuple[tuple[int, ...] | None, int]]:
    """Rows `(conditions, label)` that send every item to its label: `tests[c, i]` whether condition `c` holds on item `i`, `labels[i]` its
    label (equal conditions on two items imply equal labels), `mass[i]` how often it comes. The last row has conditions None ("any other").
    Of the lists tried, the one of fewest rows, then fewest conditions, then fewest `negative` ones ("without ..."): "with A: X, else Y"
    reads better than "without A: Y, else X"."""
    if not labels.size:
        return []
    views, at = np.unique(tests.T, axis=0, return_inverse=True)  # items a player sees alike are one item to the rows
    at = at.reshape(-1)
    view_labels = np.zeros(len(views), dtype=labels.dtype)
    view_labels[at] = labels
    view_mass = np.bincount(at, weights=mass, minlength=len(views))
    view_tests = np.ascontiguousarray(views.T)
    best, best_size = None, None
    heavy = sorted(np.unique(view_labels).tolist(), key=lambda label: -float(view_mass[view_labels == label].sum()))[:LAST_TRIED]
    for last in (None, *heavy):
        for by_mass in (True, False):
            rows = _learn(view_tests, view_labels, view_mass, by_mass, last)
            used = [c for conditions, _ in rows for c in conditions or ()]
            size = (len(rows), len(used), 0 if negative is None else int(sum(bool(negative[c]) for c in used)))
            if best_size is None or size < best_size:
                best, best_size = rows, size
    return best or []


def _learn(tests: np.ndarray, labels: np.ndarray, mass: np.ndarray, by_mass: bool, last: int | None = None) -> list[tuple[tuple[int, ...] | None, int]]:
    """One greedy list; `last` is a label kept for the last row ("any other item") while a row of another label can be found: the
    exceptions first, then the rule (an Essence step's "this step again" reads as the last row, not as five)."""
    left = np.ones(labels.size, dtype=bool)
    rows: list[tuple[tuple[int, ...] | None, int]] = []
    while left.any():
        open_labels = np.unique(labels[left])
        if open_labels.size == 1:
            rows.append((None, int(open_labels[0])))
            break
        found = None
        if last is not None and last in open_labels:
            found = _best_row(tests, labels, mass, left, by_mass, skip=last)
        if found is None:
            found = _best_row(tests, labels, mass, left, by_mass)
        if found is None:  # no row of `MOST_CONDITIONS` parts what is left: each item of the other places is said by its every fact (exact,
            # as H63's learner isolates a key by its full row: the columns hold "with" and "without" of each fact, so they name the item), the
            # heaviest place last; with no new search, which on R17 took minutes per row
            heaviest = max(open_labels.tolist(), key=lambda label: float(mass[left & (labels == label)].sum()))
            said: set[tuple[tuple[int, ...], int]] = set()
            for j in sorted(np.flatnonzero(left & (labels != heaviest)).tolist(), key=lambda i: -float(mass[i])):
                row = (_isolating(tests, labels, left, j), int(labels[j]))
                if row not in said:  # two items said by the same facts to the same place are one row (crafter on R13: 141 repeated rows)
                    said.add(row)
                    rows.append(row)
            rows.append((None, int(heaviest)))
            break
        conditions, label, covered = found
        rows.append((conditions, label))
        left &= ~covered
    return rows


def _isolating(tests: np.ndarray, labels: np.ndarray, left: np.ndarray, j: int) -> tuple[int, ...]:
    """Conditions that hold on item `j` and on no item of another label among `left`: each the one that rules out the most of what is still
    covered (greedy; the item's every condition rules out all, since the columns hold "with" and "without" of each fact)."""
    other = left & (labels != labels[j])
    chosen: list[int] = []
    while other.any():
        c = max((c for c in range(tests.shape[0]) if tests[c, j]), key=lambda c: int((other & ~tests[c]).sum()))
        if not (other & ~tests[c]).any():
            break  # nothing parts the rest (equal conditions): the caller's labels promise it never happens
        chosen.append(c)
        other &= tests[c]
    return tuple(sorted(chosen))


def _best_row(tests: np.ndarray, labels: np.ndarray, mass: np.ndarray, left: np.ndarray, by_mass: bool, skip: int | None = None):
    """The conjunction of at most `MOST_CONDITIONS` conditions that covers only items of one label among `left`, scoring the most covered."""
    useful = [c for c in range(tests.shape[0]) if (tests[c] & left).any() and (left & ~tests[c]).any()]
    best, best_score = None, None

    def consider(conditions: tuple[int, ...]) -> None:
        nonlocal best, best_score
        covered = left.copy()
        for c in conditions:
            covered &= tests[c]
        if not covered.any():
            return
        held = np.unique(labels[covered])
        if held.size != 1 or int(held[0]) == skip:
            return
        weight, size = float(mass[covered].sum()), int(covered.sum())
        score = ((weight, size) if by_mass else (size, weight), -len(conditions), [-c for c in conditions])
        if best_score is None or score > best_score:
            best, best_score = (conditions, int(held[0]), covered), score

    for c in useful:
        consider((c,))
    for i, a in enumerate(useful):
        for b in useful[i + 1 :]:
            consider((a, b))
    if MOST_CONDITIONS >= 3 and (best is None or len(best[0]) > 1):
        pool = sorted(useful, key=lambda c: -float(mass[left & tests[c]].sum()))[:TRIPLE_POOL]
        for i, a in enumerate(pool):
            for j in range(i + 1, len(pool)):
                ab = tests[a] & tests[pool[j]] & left
                if not ab.any():
                    continue
                for c in pool[j + 1 :]:
                    consider(tuple(sorted((a, pool[j], c))))
    return best
