"""Shared helpers for the nested-run tests of the simulator (ticket #222, not collected as tests).

Four real fixture amulets stand for the four states of the tiny two-prefix case of ticket #180: `E` the empty one, `P` and `Q`
holding one mod each, `PQ` both (the main target). A `ToyAction` is a fake action over them: the result depends on the state of
the item only; one that lists `wants` is a two-item action, which refuses to be applied unless it has been bound to a donor of
that state (so a test sees that the simulator applied it to the donor its nested run made).

`nested_policy` turns the policy of a solver solution over an `Acquisition` product (states `('in', want, s)`) into a simulator
policy: the main item follows the `MAIN` copy, and a `Need` of the chosen action becomes an `Input` whose sub-policy is the
copy of its `want`. It is the one place that composes the solver and the simulator, so it lives in the tests (the simulator
imports nothing of the solver, ADR-0019).
"""

from actions_support import RESIST, TARGET, amulet, roll
from simulator_support import DEAD_MOD, Draw

from crafting_system.simulator import Input, Step
from crafting_system.solver import MAIN

STATES = {
    "E": amulet(),
    "P": amulet(roll(TARGET)),
    "Q": amulet(roll(DEAD_MOD)),
    "PQ": amulet(roll(TARGET), roll(DEAD_MOD)),
    "J": amulet(roll(RESIST)),
}
STATE_OF = {item: state for state, item in STATES.items()}


def state_of(item) -> str:
    return STATE_OF[item]


def item_of(state: str):
    return STATES[state]


class ToyAction:
    """A fake action: from `row`, `((state, weight), ...)`, whatever item it is used on. With `wants` it needs a donor of that state."""

    def __init__(self, row, wants=None, donor=None):
        self.row, self.wants, self.donor = tuple(row), wants, donor

    def bound(self, donor) -> "ToyAction":
        return ToyAction(self.row, self.wants, donor)

    def outcomes(self, data, item):
        if self.wants is not None:
            assert self.donor is not None, "a two-item action was applied without a donor"
            assert STATE_OF[self.donor] == self.wants, f"applied with a donor {STATE_OF[self.donor]}, wanted {self.wants}"
        return Draw([STATES[state] for state, _ in self.row], [weight for _, weight in self.row])


def toy_actions(spec):
    """`{(base state, label): ToyAction}` of a base spec `(goals, table)` as `test_solver_acquire.tiny_spec` makes it."""
    _, table = spec
    return {
        (state, label): ToyAction(outcomes, needs[0][1] if needs else None)
        for state, rows in table.items()
        for label, _, outcomes, needs in rows
    }


def nested_policy(solution, *, actions, state_of, item_of, reaches, goal, bind=None, matches=None):
    """The simulator policy of `solution.policy`, an `Acquisition` product's, for the main item.

    `actions(state, label)` is the action the solver's action stands for at the base state. `goal(item)` is the goal of the
    main target and `reaches(state, want)` that of a want. `bind(action, donors)`, when given, returns the action applied to the
    donors the nested runs made; `matches(want, donor)` is the check of an input. Each want has one policy, made once.
    """
    made = {}

    def goal_of(want):
        return goal if want is MAIN else (lambda item: reaches(state_of(item), want))

    def policy_of(want):
        if want not in made:
            made[want] = lambda item: step_at(want, item)
        return made[want]

    def step_at(want, item):
        chosen = solution.policy.get(("in", want, state_of(item)))
        if chosen is None:
            return None
        action = actions(state_of(item), chosen.label)
        inputs = tuple(
            Input(
                item_of(start),
                policy_of(wanted),
                goal_of(wanted),
                matches=None if matches is None else (lambda donor, wanted=wanted: matches(wanted, donor)),
            )
            for _, wanted, start in chosen.extra_inputs
        )
        return Step(action, chosen.cost, inputs, None if bind is None or not inputs else (lambda donors, a=action: bind(a, donors)))

    return policy_of(MAIN)


__all__ = ["STATES", "STATE_OF", "ToyAction", "item_of", "nested_policy", "state_of", "toy_actions"]
