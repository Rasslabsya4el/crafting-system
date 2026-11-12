"""The socket finish (ADR-0045, ADR-0058, ticket #231): the sockets of a goal item, finished by a problem of their own.

The finish starts from the sockets a goal state's item holds and ends when the target's socket requirement holds. No mod action changes
sockets and no socket action changes mods (ADR-0045), so it is solved on its own and its value is added to every goal state of the mods.

**The state** is the item's sockets as `Sockets` (the colour of every socket in order, the link groups as sizes), reduced by the one reduction
that is exact (ADR-0058, "What the state keeps"): a link group shorter than the group the target asks for is forgotten (its sockets are
held as groups of one), because no action grows a group or reads a short one. The real colours and the positions are kept. Item level,
class and quality are constants of the problem; the quality is compared at two levels (`solve_finish`).

**The kernels** come from the actions alone (the contract, ticket #108): each finish action gives its `SocketRule` (`Action.socket_rule`) for the
base, item level, quality and reading, so no mechanic of a socket action is written here. A rule with a `shape` changes the count or the links
(its results are listed: at most 32); a rule with a `roll` changes the colours, and is one **shared table** per (step, count, link groups), the roll
before the exclusion. `FinishModel.kernel` gives one kernel exactly (`Fraction`s that sum to 1); layer 1 compares it with the action itself run
on every concrete socket assignment (`tests/test_socket_finish.py`). An action whose kernel on a state is "stay where you are" for certain is no
action there: it can only cost (the concrete item may refuse it or let it change links that are forgotten).

A roll that `excludes_current` (a Chromatic Orb never returns the item's colours, ADR-0047): with `e` the table's chance of the state's own colours
and `S` the table summed over all outcomes at the current values, its backup is `cost + (S - e V(s)) / (1 - e)`, exactly the roll conditioned on
other colours. A roll that excludes nothing (a bench colour craft) has its own colours as a self-loop: `(cost + S - e V(s)) / (1 - e)`. A sweep
costs the states plus the table entries, not the states times the outcomes (ADR-0058, decision 1).

**The solve** is value iteration over these backups with Anderson acceleration (depth 6, a step accepted only when it lowers the Bellman
residual), from below, until the largest Bellman residual is below `TOLERANCE` of the largest value. A listed action's self-loop is solved out
(`(cost + sum of the other outcomes) / (1 - p_self)`), which is exact. Before it, the states from which no policy reaches the goal for
certain are found (they keep an infinite value) and every action that may lead to one is left out. `solver.solve` is not used (ADR-0058,
decision 3; `abstraction` may not import `solver`).

**Readings** (ADR-0047): an action the plan's policy takes may read a rule axis (`Action.rule_axes`: the Jeweller's table, the forced colour); the
finish is solved at the plan's reading, and each other reading's number is the plan's policy evaluated at it (not a re-solve), as ADR-0045 says.
A reading that changes no number (the forced colour of a target that needs two coloured sockets or more) is not listed.

**The bound flag** of Orb of Binding (ADR-0048, ticket #232) is a second start of the same problem: `FinishValues.of` gives the value of any
state the solve reached, and `solve_finish` takes the start it is given.
"""

from __future__ import annotations

import time
from collections.abc import Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from functools import cached_property
from math import inf

import numpy as np

from crafting_system.actions import MAX_CURRENCY_QUALITY, Action, OutOfScopeError, Reading, SocketRule, expected_quality_currency
from crafting_system.data import GameData
from crafting_system.items import SocketColour, Sockets, class_maximum

TOLERANCE = 1e-13  # the largest Bellman residual accepted, relative to the largest finite value (at least 1)
ANDERSON_DEPTH = 6
MAX_SWEEPS = 200_000
WHITE, RED, GREEN, BLUE = 0, 1, 2, 3
_COLOUR_OF = {SocketColour.WHITE: WHITE, SocketColour.RED: RED, SocketColour.GREEN: GREEN, SocketColour.BLUE: BLUE}
_SOCKET_COLOUR = {number: colour for colour, number in _COLOUR_OF.items()}

State = tuple[tuple[int, ...], tuple[int, ...]]  # (colour numbers in socket order, link group sizes), reduced


@dataclass(frozen=True)
class SocketWanted:
    """The socket requirement as the finish reads it (ADR-0046): at least `count` sockets, a linked group of at least `links`, and at least
    `red`, `green`, `blue` sockets of those colours, counted in one group of at least `links` sockets when `links` is given, over the item otherwise."""

    count: int | None = None
    links: int | None = None
    red: int = 0
    green: int = 0
    blue: int = 0

    @classmethod
    def of(cls, requirement) -> SocketWanted:
        """The requirement of a target (`targets.SocketRequirement`), read by duck typing."""
        return cls(requirement.count, requirement.links, requirement.red, requirement.green, requirement.blue)

    @property
    def named(self) -> tuple[int, int, int]:
        return (self.red, self.green, self.blue)

    @property
    def group(self) -> int:
        """The least size of a group that counts: `links`, or 1 when no link is asked (a group of one is every socket alone).

        With `links` 1 the colours add up to at most 1 (the parser's rule), so one socket of the colour anywhere meets it, as with no link at all."""
        return self.links if self.links is not None and self.links > 1 else 1

    def is_met(self, state: State) -> bool:
        colours, links = state
        if self.count is not None and len(colours) < self.count:
            return False
        if self.group == 1:
            return all(colours.count(number) >= wanted for number, wanted in zip((RED, GREEN, BLUE), self.named, strict=True))
        start = 0
        for size in links:
            if size >= self.group:
                part = colours[start : start + size]
                if all(part.count(number) >= wanted for number, wanted in zip((RED, GREEN, BLUE), self.named, strict=True)):
                    return True
            start += size
        return False


@dataclass(frozen=True)
class FinishStep:
    """One finish action as the plan offers it: its label, the action and the cost of one use in Chaos."""

    label: str
    action: Action
    cost: float


def state_of(sockets: Sockets) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """The colours and links of `sockets` as numbers (not reduced)."""
    return tuple(_COLOUR_OF[colour] for colour in sockets.colours), tuple(sockets.links)


def sockets_of(state: State) -> Sockets:
    """The `Sockets` a state stands for (its reduced form: forgotten groups unlinked)."""
    colours, links = state
    return Sockets(tuple(_SOCKET_COLOUR[number] for number in colours), links)


def _resized(state: State, count: int) -> State:
    """`resized_sockets` on numbers: new sockets white and unlinked at the end, a lower count removes the last ones and cuts a group where they end."""
    colours, links = state
    if count >= len(colours):
        added = count - len(colours)
        return (*colours, *([WHITE] * added)), (*links, *([1] * added))
    kept, left = [], count
    for size in links:
        if left <= 0:
            break
        kept.append(min(size, left))
        left -= size
    return colours[:count], tuple(kept)


class _Table:
    """One shared colour table: the roll of one action on one count and one set of link groups, before the exclusion."""

    __slots__ = ("chances", "excludes", "targets")

    def __init__(self, chances: Mapping[tuple[int, ...], Fraction], excludes: bool) -> None:
        self.chances = chances
        self.excludes = excludes  # a Chromatic Orb never returns the item's colours; a bench craft may
        self.targets: list[int] = []


@dataclass(frozen=True)
class FinishValues:
    """The solve of one finish model from its starts: the value of every state it reached (`inf` where no policy finishes for certain) and the
    label of the action the plan takes at every state that is not finished."""

    values: Mapping[State, float]
    policy: Mapping[State, str]
    sweeps: int
    seconds: float
    transitions: int  # the listed outcomes plus the entries of the shared tables
    goals: int = 0  # how many of the states reached are finished (ADR-0058 counts the states without them)

    @property
    def open_states(self) -> int:
        """The states reached that are not finished: the count ADR-0058 measures."""
        return len(self.values) - self.goals

    def of(self, sockets: Sockets, model: FinishModel) -> float:
        """The value of the item with `sockets` (reduced by `model`); `KeyError` for sockets the solve did not reach."""
        return self.values[model.reduce(state_of(sockets))]


class FinishModel:
    """The finish of one target on one base at one item level and plain quality, with the finish actions offered (ADR-0045, ADR-0058).

    `steps` are the actions with their costs (labels distinct); each is asked its `SocketRule` here, and one with none on this base at this
    quality is not offered. `reading` is the reading of the rule axes the rules are taken at (None: the plan's). A base with no socket table is
    `OutOfScopeError`.
    """

    def __init__(
        self,
        data: GameData,
        base_id: str,
        item_level: int,
        wanted: SocketWanted,
        steps: Sequence[FinishStep],
        *,
        quality: int = 0,
        reading: Reading | None = None,
    ) -> None:
        base = data.base_items[base_id]
        if class_maximum(base) is None:
            raise OutOfScopeError(f"a {base.item_class} takes no sockets, so it has no socket finish")
        labels = [step.label for step in steps]
        if len(set(labels)) != len(labels):
            raise ValueError("the finish steps need distinct labels")
        for step in steps:
            if not step.cost > 0:
                raise ValueError("every finish step costs more than 0")
            if not step.action.adds(data).only_sockets:
                raise ValueError("a finish step is an action that changes the sockets and nothing else")
        self.data = data
        self.base_id = base_id
        self.item_level = item_level
        self.wanted = wanted
        self.quality = quality
        self.reading = reading
        rules = [(step, step.action.socket_rule(data, base_id, item_level, quality, reading)) for step in steps]
        self.steps = tuple(step for step, rule in rules if rule is not None)
        self.rules: dict[str, SocketRule] = {step.label: rule for step, rule in rules if rule is not None}
        self._shapes: dict = {}
        self._tables: dict = {}

    # --- the state --------------------------------------------------------------------------------------

    def reduce(self, state: State) -> State:
        """The state with every link group shorter than the target's group made groups of one (ADR-0058: the one exact reduction)."""
        colours, links = state
        group = self.wanted.group
        if group == 1:
            return colours, (1,) * len(colours)
        if all(size >= group or size == 1 for size in links):
            return state
        reduced: list[int] = []
        for size in links:
            reduced.extend((size,) if size >= group else (1,) * size)
        return colours, tuple(reduced)

    def is_goal(self, state: State) -> bool:
        return self.wanted.is_met(state)

    # --- the kernels -------------------------------------------------------------------------------------

    def shape_kernel(self, step: FinishStep, count: int, links: tuple[int, ...]) -> tuple[tuple[int, tuple[int, ...], Fraction], ...] | None:
        """The kernel of a step whose rule has a `shape` on `count` sockets in the reduced `links`, its results' links reduced and merged; None
        where the game refuses it. Cached by its arguments."""
        key = (step.label, count, links)
        if key not in self._shapes:
            found = self.rules[step.label].shape(count, links)
            if found is None:
                self._shapes[key] = None
            else:
                merged: dict[tuple[int, tuple[int, ...]], Fraction] = {}
                for new, new_links, chance in found:
                    reduced = (new, self.reduce(((WHITE,) * new, tuple(new_links)))[1])
                    merged[reduced] = merged.get(reduced, Fraction(0)) + chance
                self._shapes[key] = tuple((new, new_links, chance) for (new, new_links), chance in merged.items())
        return self._shapes[key]

    def roll_table(self, step: FinishStep, count: int) -> Mapping[tuple[int, ...], Fraction] | None:
        """The roll of a step whose rule has a `roll` on `count` sockets, colours as numbers; None where the game refuses it. Cached."""
        key = (step.label, count)
        if key not in self._tables:
            found = self.rules[step.label].roll(count)
            self._tables[key] = None if found is None else {tuple(_COLOUR_OF[colour] for colour in colours): chance for colours, chance in found.items()}
        return self._tables[key]

    def kernel(self, state: State, step: FinishStep) -> dict[State, Fraction] | None:
        """The exact kernel of `step` on the reduced `state`: each reduced result with its chance (they sum to 1), or None where it is no action.

        None means the game refuses it there, or every result is the state itself (an action that can only cost)."""
        found = self._kernel(state, step)
        if found is None or found == {state: Fraction(1)}:
            return None
        return found

    def _kernel(self, state: State, step: FinishStep) -> dict[State, Fraction] | None:
        colours, links = state
        rule = self.rules[step.label]
        if rule.shape is not None:
            shape = self.shape_kernel(step, len(colours), links)
            if shape is None:
                return None
            return _merged(((_recoloured(colours, new), new_links), chance) for new, new_links, chance in shape)
        table = self.roll_table(step, len(colours))
        if table is None:
            return None
        if rule.excludes_current:  # never the colours the item has
            own = table.get(colours, Fraction(0))
            if own == 1:
                return None
            return {(new, links): chance / (1 - own) for new, chance in table.items() if new != colours}
        return {(new, links): chance for new, chance in table.items()}

    # --- the solve ---------------------------------------------------------------------------------------

    def solve(self, starts: Iterable[State], policy: Mapping[State, str] | None = None) -> FinishValues:
        """The optimal values from `starts` (reduced here), or with `policy` (a label per state) the values of that policy at this model's kernels."""
        began = time.perf_counter()
        graph = _Graph(self, [self.reduce(start) for start in starts], policy)
        values, chosen, sweeps = graph.iterate()
        labels = [step.label for step in self.steps]
        found_policy = {graph.states[s]: labels[step] for s, step in chosen.items()}
        found_values = {state: float(value) for state, value in zip(graph.states, values, strict=True)}
        return FinishValues(found_values, found_policy, sweeps, time.perf_counter() - began, graph.transitions, int(graph.goal.sum()))


def _recoloured(colours: tuple[int, ...], count: int) -> tuple[int, ...]:
    """The colours of an item cut or grown to `count` sockets: the first keep theirs, new ones are white (ADR-0046)."""
    if count <= len(colours):
        return colours[:count]
    return (*colours, *([WHITE] * (count - len(colours))))


def _merged(pairs: Iterable[tuple[State, Fraction]]) -> dict[State, Fraction]:
    found: dict[State, Fraction] = {}
    for state, chance in pairs:
        found[state] = found.get(state, Fraction(0)) + chance
    return found


class _Graph:
    """The reachable states of a model and the arrays of one sweep: listed actions as edges, colour actions as shared tables."""

    def __init__(self, model: FinishModel, starts: list[State], policy: Mapping[State, str] | None) -> None:
        self.model = model
        index: dict[State, int] = {}
        states: list[State] = []

        def add(state: State) -> int:
            number = index.get(state)
            if number is None:
                number = index[state] = len(states)
                states.append(state)
            return number

        for start in starts:
            add(start)
        tables: dict[Hashable, _Table] = {}
        x_state, x_step, x_cost, x_self = [], [], [], []  # one entry per listed state-action
        e_sa, e_target, e_chance = [], [], []  # its outcomes other than the state itself
        y_state, y_step, y_cost, y_table, y_own = [], [], [], [], []  # one entry per state-action of a shared table
        table_numbers: dict[Hashable, int] = {}
        shapes: dict[tuple[int, int, tuple[int, ...]], tuple | None] = {}  # the listed kernels as floats, by (step, count, links)
        goal: list[bool] = []
        wanted_label = None
        position = 0
        while position < len(states):
            state = states[position]
            is_goal = model.is_goal(state)
            goal.append(is_goal)
            if not is_goal:
                if policy is not None:
                    wanted_label = policy.get(state)
                colours, links = state
                for number, step in enumerate(model.steps):
                    if policy is not None and step.label != wanted_label:
                        continue
                    rule = model.rules[step.label]
                    if rule.roll is not None:
                        key = (step.label, len(colours), links)
                        table = tables.get(key)
                        if table is None and key not in tables:
                            chances = model.roll_table(step, len(colours))
                            if chances is None:
                                tables[key] = None  # type: ignore[assignment]
                                continue
                            table = tables[key] = _Table(chances, rule.excludes_current)
                            table.targets = [add((new, links)) for new in chances]
                            table_numbers[key] = len(table_numbers)
                        if table is None:
                            continue
                        own = table.chances.get(colours, Fraction(0))
                        if own == 1:
                            continue
                        y_state.append(position)
                        y_step.append(number)
                        y_cost.append(step.cost)
                        y_table.append(table_numbers[key])
                        y_own.append(float(own))
                        continue
                    shape = shapes.get((number, len(colours), links), False)
                    if shape is False:
                        found = model.shape_kernel(step, len(colours), links)
                        shape = shapes[(number, len(colours), links)] = None if found is None else tuple((new, new_links, float(chance)) for new, new_links, chance in found)
                    if shape is None:
                        continue
                    outcomes: dict[State, float] = {}
                    for new, new_links, chance in shape:
                        target = (_recoloured(colours, new), new_links)
                        outcomes[target] = outcomes.get(target, 0.0) + chance
                    stay = outcomes.pop(state, 0.0)
                    if not outcomes:
                        continue  # every result is the state itself: an action that can only cost
                    sa = len(x_state)
                    x_state.append(position)
                    x_step.append(number)
                    x_cost.append(step.cost)
                    for target, chance in outcomes.items():
                        e_sa.append(sa)
                        e_target.append(add(target))
                        e_chance.append(chance)
                    x_self.append(stay)
            position += 1
        self.states = states
        self.goal = np.array(goal, dtype=bool)
        self.x_state = np.array(x_state, dtype=np.int64)
        self.x_step = np.array(x_step, dtype=np.int64)
        self.x_cost = np.array(x_cost, dtype=float)
        self.x_self = np.array(x_self, dtype=float)
        self.e_sa = np.array(e_sa, dtype=np.int64)
        self.e_target = np.array(e_target, dtype=np.int64)
        self.e_chance = np.array(e_chance, dtype=float)
        live = [tables[key] for key in table_numbers]  # numbered in the order they were made
        self.t_table = np.array([number for number, table in enumerate(live) for _ in table.targets], dtype=np.int64)
        self.t_target = np.array([target for table in live for target in table.targets], dtype=np.int64)
        self.t_chance = np.array([float(chance) for table in live for chance in table.chances.values()], dtype=float)
        self.t_excludes = np.array([table.excludes for table in live], dtype=bool)
        self.y_state = np.array(y_state, dtype=np.int64)
        self.y_step = np.array(y_step, dtype=np.int64)
        self.y_cost = np.array(y_cost, dtype=float)
        self.y_table = np.array(y_table, dtype=np.int64)
        self.y_own = np.array(y_own, dtype=float)
        self.tables = len(live)
        self.transitions = len(e_target) + len(self.t_target)

    # --- which states can finish ---------------------------------------------------------------------------

    def _finishing(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """The states from which some policy finishes for certain, and which state-actions keep inside them (listed, table)."""
        size = len(self.states)
        inside = np.ones(size, dtype=bool)
        x_count, y_count, t_count = len(self.x_state), len(self.y_state), len(self.t_target)
        while True:
            # an action is safe when every outcome stays inside (a table's own entry is the state itself, inside with it)
            x_out = np.bincount(self.e_sa, weights=~inside[self.e_target], minlength=x_count) if x_count else np.zeros(0)
            x_safe = inside[self.x_state] & (x_out == 0) if x_count else np.zeros(0, dtype=bool)
            t_out = np.bincount(self.t_table, weights=~inside[self.t_target], minlength=self.tables) if t_count else np.zeros(self.tables)
            y_safe = inside[self.y_state] & (t_out[self.y_table] == 0) if y_count else np.zeros(0, dtype=bool)
            reach = self.goal & inside
            while True:
                x_hit = np.bincount(self.e_sa, weights=reach[self.e_target], minlength=x_count) > 0 if x_count else np.zeros(0, dtype=bool)
                t_hit = np.bincount(self.t_table, weights=reach[self.t_target], minlength=self.tables) > 0 if t_count else np.zeros(self.tables, dtype=bool)
                grown = reach.copy()
                grown[self.x_state[x_safe & x_hit]] = True
                if y_count:
                    grown[self.y_state[y_safe & t_hit[self.y_table]]] = True
                if (grown == reach).all():
                    break
                reach = grown
            if (reach == inside).all():
                return inside, x_safe, y_safe
            inside = reach

    # --- value iteration ----------------------------------------------------------------------------------

    def iterate(self) -> tuple[np.ndarray, dict[int, int], int]:
        """The values (inf where no policy finishes for certain), the step chosen at every state not finished, and the sweeps taken."""
        size = len(self.states)
        inside, x_safe, y_safe = self._finishing()
        free = inside & ~self.goal
        values = np.where(inside, 0.0, inf)
        if not free.any():
            return values, {}, 0
        x = np.flatnonzero(x_safe)
        y = np.flatnonzero(y_safe)
        e_keep = x_safe[self.e_sa]
        e_sa = np.searchsorted(x, self.e_sa[e_keep])
        e_target, e_chance = self.e_target[e_keep], self.e_chance[e_keep]
        x_state, x_cost, x_self = self.x_state[x], self.x_cost[x], self.x_self[x]
        y_state, y_cost, y_table, y_own = self.y_state[y], self.y_cost[y], self.y_table[y], self.y_own[y]
        y_scale = np.where(self.t_excludes[y_table], 1.0 - y_own, 1.0)
        sa_state = np.concatenate([x_state, y_state])
        sa_step = np.concatenate([self.x_step[x], self.y_step[y]])
        order = np.lexsort((sa_step, sa_state))
        sorted_state = sa_state[order]
        group_start = np.flatnonzero(np.r_[True, sorted_state[1:] != sorted_state[:-1]])
        group_state = sorted_state[group_start]
        free_index = np.flatnonzero(free)
        if not np.array_equal(np.sort(group_state), free_index):
            raise AssertionError("a state that can finish has no action that keeps it inside")
        x_count = len(x)

        def backups(v: np.ndarray) -> np.ndarray:
            q_x = (x_cost + np.bincount(e_sa, weights=e_chance * v[e_target], minlength=x_count)) / (1.0 - x_self)
            sums = np.bincount(self.t_table, weights=self.t_chance * v[self.t_target], minlength=self.tables) if self.tables else np.zeros(0)
            q_y = (y_cost * y_scale + sums[y_table] - y_own * v[y_state]) / (1.0 - y_own)
            return np.concatenate([q_x, q_y])[order]

        def bellman(v: np.ndarray) -> np.ndarray:
            out = v.copy()
            out[group_state] = np.minimum.reduceat(backups(v), group_start)
            return out

        history_x: list[np.ndarray] = []
        history_f: list[np.ndarray] = []
        sweeps = 0
        current = np.zeros(size)  # from below; an infinite state is never read by a kept action, and 0 keeps the sums finite
        mapped = bellman(current)
        residual = np.max(np.abs(mapped[free] - current[free]))
        while True:
            scale = max(1.0, float(np.max(mapped[free])))
            if residual <= TOLERANCE * scale:
                current = mapped
                break
            if sweeps >= MAX_SWEEPS:
                raise ArithmeticError(
                    f"the cost of finishing the sockets did not settle after {MAX_SWEEPS:,} rounds of working it out (it still moved by {residual:.3g} Chaos)"
                )
            f = (mapped - current)[free]
            history_x.append(current[free].copy())
            history_f.append(f)
            if len(history_x) > ANDERSON_DEPTH + 1:
                history_x.pop(0)
                history_f.pop(0)
            candidate, accelerated = mapped, False
            if len(history_f) >= 2:
                d_f = np.stack([history_f[k + 1] - history_f[k] for k in range(len(history_f) - 1)], axis=1)
                d_x = np.stack([history_x[k + 1] - history_x[k] for k in range(len(history_x) - 1)], axis=1)
                gamma, *_ = np.linalg.lstsq(d_f, f, rcond=None)
                step = current[free] + f - (d_x + d_f) @ gamma
                if np.all(np.isfinite(step)):
                    candidate, accelerated = mapped.copy(), True
                    candidate[free] = step
            sweeps += 1
            following = bellman(candidate)
            following_residual = np.max(np.abs(following[free] - candidate[free]))
            if not accelerated or following_residual < residual:
                current, mapped, residual = candidate, following, following_residual
                continue
            # the accelerated step did not lower the residual: take the plain one and start the history again
            history_x.clear()
            history_f.clear()
            sweeps += 1
            current = mapped
            mapped = bellman(current)
            residual = np.max(np.abs(mapped[free] - current[free]))
        values = np.where(inside, current, inf)
        values[self.goal & inside] = 0.0
        q = backups(np.where(inside, current, 0.0))
        best = np.minimum.reduceat(q, group_start)
        chosen: dict[int, int] = {}
        sorted_step = sa_step[order]
        tied = np.flatnonzero(q <= np.repeat(best, np.diff(np.r_[group_start, len(q)])) * (1 + 1e-12))
        for position in tied:  # the first offer (in the order of the steps) among those within rounding of the best
            state = int(sorted_state[position])
            if state not in chosen:
                chosen[state] = int(sorted_step[position])
        return values, chosen, sweeps


@dataclass(frozen=True)
class Finish:
    """The socket finish of a target from its start sockets (ADR-0045, ADR-0049): what the plan adds to every goal state.

    `value` is the expected cost in Chaos from `start`, the quality bought first included when `quality_bought`; `quality_cost` is that
    part (0 when the plan keeps the item's own quality). `model` and `solution` are the problem at the quality the plan finishes at and its
    solve. `second_readings` maps the name of each rule axis with a second reading the finish reads to the plan's policy evaluated at that
    reading (quality included), as ADR-0045 says; an axis the plan's policy does not read is not in it.
    """

    value: float
    start: State
    model: FinishModel
    solution: FinishValues
    quality_bought: bool = False
    quality_cost: float = 0.0
    quality_step: FinishStep | None = None
    second_readings: Mapping[str, float] = field(default_factory=dict)

    @property
    def met(self) -> bool:
        """Whether the start sockets already meet the requirement (nothing to do)."""
        return self.model.is_goal(self.start)

    @property
    def policy(self) -> Mapping[State, str]:
        return self.solution.policy

    @property
    def states(self) -> int:
        return len(self.solution.values)

    @property
    def claims(self) -> frozenset[str]:
        """The claims of the actions the plan's policy takes, and of the quality step when it is bought (ADR-0028: the inputs it reads)."""
        taken = set(self.policy.values())
        found: set[str] = set()
        for step in self.model.steps:
            if step.label in taken:
                found |= step.action.claims(self.model.data)
        if self.quality_bought and self.quality_step is not None:
            found |= self.quality_step.action.claims(self.model.data)
        return frozenset(found)


def solve_finish(
    data: GameData,
    base_id: str,
    item_level: int,
    wanted: SocketWanted,
    start: Sockets,
    steps: Sequence[FinishStep],
    *,
    quality: int = 0,
    quality_step: FinishStep | None = None,
) -> Finish:
    """The finish of `wanted` from the sockets `start` with the finish actions `steps`, at the item's own `quality` and, with a `quality_step`
    (a Whetstone or a Scrap and its price) below 20%, also at 20% after buying it; the cheaper (ADR-0049). Its second readings beside it."""
    if quality_step is not None and not quality_step.action.adds(data).only_quality:
        raise ValueError("the quality step of the finish is an action that sets the quality and nothing else")

    def level(percent: int, reading: Reading | None = None) -> FinishModel:
        return FinishModel(data, base_id, item_level, wanted, steps, quality=percent, reading=reading)

    own_model = level(quality)
    origin = own_model.reduce(state_of(start))
    own = own_model.solve([origin])
    choice = (own_model, own, own.values[origin], False, 0.0)
    if quality_step is not None and quality < MAX_CURRENCY_QUALITY:
        bought_cost = float(expected_quality_currency(item_level, MAX_CURRENCY_QUALITY, quality)) * quality_step.cost
        raised_model = level(MAX_CURRENCY_QUALITY)
        raised = raised_model.solve([origin])
        if raised.values[origin] + bought_cost < choice[2]:
            choice = (raised_model, raised, raised.values[origin] + bought_cost, True, bought_cost)
    model, solution, value, bought, quality_cost = choice
    seconds_readings: dict[str, float] = {}
    taken = set(solution.policy.values())
    axes = {axis.name: axis for step in model.steps if step.label in taken for axis in step.action.rule_axes(data)}
    for name, axis in sorted(axes.items()):
        for other in axis.readings:
            if other == axis.plan:
                continue
            evaluated = level(model.quality, Reading.of({name: other})).solve([origin], policy=solution.policy).values[origin] + quality_cost
            if abs(evaluated - value) > 1e-9 * max(1.0, abs(value)):  # a reading that changes no number is not listed
                seconds_readings[name] = evaluated
    return Finish(value, origin, model, solution, bought, quality_cost, quality_step, seconds_readings)
