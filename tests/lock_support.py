"""Shared helpers for the Lock tests of `risk` and the simulator (not collected as tests; ticket #297, ADR-0054, ADR-0057).

* `simulator_lock_policy`: a `solve_peek` solution of a tabular Peek model played on "items" that are the states themselves:
  a plain action becomes a `Step`, the Lock a `simulator.Lock` whose options are the Peek's options, whose acceptance is the
  solution's acceptance set (its rank) and whose fallback is the action the policy takes at the "give up" node.
* `product_policy`: the same acceptance set as a policy of the explicit product expansion (`peek_oracles.product_spec`): at a
  react state the best accepted pair is applied, and with none the fallback the solution gives up with.
* `burn_spec`: the hand-written burn loop: one option, a fallback that only returns to the Lock's state.

The simulator imports nothing of the solver; this file composes them, as `nested_support` does for nested runs.
"""

import itertools
from fractions import Fraction

from peek_oracles import PeekSpec, _merged

from crafting_system.simulator import Lock, Step
from crafting_system.solver import GIVE_UP, Peek, PeekNode


class Draw:
    """A sampler over states: one of `outcomes` `((state, weight), ...)`, with chance proportional to its weight."""

    def __init__(self, outcomes):
        self.outcomes = [(state, weight) for state, weight in outcomes if weight]
        self.total = sum(weight for _, weight in self.outcomes)

    def sample(self, rng):
        point = rng.random() * self.total
        for state, weight in self.outcomes:
            point -= weight
            if point < 0.0:
                return state
        return self.outcomes[-1][0]


class Kernel:
    """A fake action on state-items: `outcomes` is the solver action's own list."""

    def __init__(self, outcomes):
        self.row = tuple(outcomes)

    def outcomes(self, data, item):
        return Draw(self.row)


def step_of(action):
    return Step(Kernel(action.outcomes), action.cost)


def simulator_lock_policy(spec_actions, solution):
    """`spec_actions[state]` the actions of the model (a `Peek` among them), `solution` its `solve_peek` answer: item -> step."""
    peeks = {s: a for s, actions in spec_actions.items() for a in actions if isinstance(a, Peek)}
    steps = {}
    for state, action in solution.policy.items():
        if isinstance(state, PeekNode):
            continue
        if state in peeks and action.label == peeks[state].label:
            peek = peeks[state]
            rank = {pair: index for index, pair in enumerate(solution.reactions[state])}
            give_up = solution.policy.get(PeekNode(state, GIVE_UP))
            steps[state] = Lock(
                peek.cost,
                tuple(step_of(option) for option in peek.options),
                lambda a, item, rank=rank: rank.get((a, item)),
                None if give_up is None else step_of(give_up),
            )
        else:
            steps[state] = step_of(action)
    return steps.get


def product_policy(spec, solution):
    """The acceptance set of `solution` at `spec.state` as a choice of the product expansion: state -> action index."""
    size, product = _product(spec)
    choice = {}
    for state in range(spec.size):
        action = solution.policy.get(state)
        if action is None:
            continue
        if state == spec.state and action.label == "lock":
            choice[state] = len(product[state]) - 1  # the lock is the last action of the Peek state
        else:
            choice[state] = next(i for i, (label, _, _) in enumerate(product[state]) if label == action.label)
    if spec.state is None or spec.state not in solution.reactions:
        return choice
    rank = {pair: index for index, pair in enumerate(solution.reactions[spec.state])}
    give_up = solution.policy.get(PeekNode(spec.state, GIVE_UP))
    combos = list(itertools.product(*(_merged(outs) for _, _, outs in spec.options)))
    for index, combo in enumerate(combos):
        node = spec.size + index
        accepted = [(rank[(a, result)], a) for a, (result, _) in enumerate(combo) if (a, result) in rank]
        if accepted:
            choice[node] = min(accepted)[1]
        elif give_up is not None:
            choice[node] = len(spec.options) + next(i for i, (label, _, _) in enumerate(spec.fallback) if label == give_up.label)
    return choice


def _product(spec):
    from peek_oracles import product_spec

    return product_spec(spec)


def burn_spec(lock=Fraction(3), success=1, failure=4, option_cost=Fraction(1), burn=Fraction(1, 2)):
    """State 0 offers the Lock; its one option lands on the goal (2) with weight `success`, else on the dead state 1.

    The fallback is a burn back to 0, so the player locks, looks, and either applies the option (a hit) or burns and
    locks again: the number of Locks is geometric with chance `success / (success + failure)`.
    """
    options = [("option", option_cost, [(2, success), (1, failure)])]
    return PeekSpec(2, {0: [], 1: []}, 0, lock, options, [("burn", burn, [(0, 1)])], 0)
