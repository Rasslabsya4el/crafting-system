"""Shared helpers for the solver tests (not collected as tests): action shorthand, a counting model."""

from crafting_system.solver import Action, TabularModel

GOAL = "goal"

# The three ways the solver can be told to solve a cyclic component.
DIRECT_LIMITS = {"value-iteration-only": 0, "default": 64, "policy-iteration-only": 10**9}


def act(label, cost, *outcomes):
    """`act("try", 2, ("goal", 1), ("A", 3))`: an action of cost 2 with weighted outcomes."""
    return Action(label, cost, tuple(outcomes))


def model(table, goals=(GOAL,)):
    return TabularModel(goals, table)


class CountingModel:
    """Wraps a model and records every call, to check that `actions` is called at most once."""

    def __init__(self, inner):
        self.inner = inner
        self.action_calls = []
        self.goal_calls = []

    def is_goal(self, state):
        self.goal_calls.append(state)
        return self.inner.is_goal(state)

    def actions(self, state):
        self.action_calls.append(state)
        return self.inner.actions(state)
