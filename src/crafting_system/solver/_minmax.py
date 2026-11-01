"""The pessimistic min-max solve: the controller picks an action, nature picks its variant (ADR-0023).

The model is a game. In a state the controller picks an action; a `VariantAction` then lets nature
pick, among its variants, the successor distribution, every time the state is visited:

    V(s) = min over actions a of [ cost_a + max over variants v of sum_s' P_v(s' | s) V(s') ]

with goals at 0. Nature outside the controller's reach is not modelled: both players use
stationary policies, which suffices for this stochastic shortest path (positive costs, finitely
many states).

Algorithm (Hoffman-Karp, nature outer, controller inner). Nature keeps for every `VariantAction`
the variant it plays now (the first one at the start). With nature fixed the game is an ordinary
model, so `solve` finds the controller's best response and the values V. Then, for every variant
action in every state, nature takes the variant with the largest Q = cost + sum P_v V (an infinite
Q beats a finite one) when it beats the current one by more than a relative 1e-12, and the model is
solved again. A switch only raises values and there are finitely many choices of nature, so the
rounds end when nothing switches; the loop is also capped (`MAX_ROUNDS`), which can cost tightness
but never soundness, because the certificate below is measured on the final values, not assumed
from the loop. States whose value is infinite under some choice of nature are infinite for the
game too: that choice is a policy of nature against which no controller policy is proper.

Everything is explored once: the caller's `actions` is asked once per state (the answers are kept),
and the states reachable through any variant of any action are the states of the solve, so the
values nature needs are always there. Without any `VariantAction` the model is solved by plain
`solve` and the result is that of `solve`.

The certificate. Let mu be the controller's policy that `solve` returned for the final model and V
its values. Restrict to R, the finite-valued states reachable from `starts` by mu through ANY
variant of the chosen action (a closed set, goals included). The operator of mu on R in the game is

    T+_mu(V)(s) = max over variants v of mu(s) of [ cost + sum P_v V ]       (a plain action: one v)

Each variant has the identity of ADR-0010 with its own constant term k_v = cost >= g, where g is
the smallest cost among the actions of mu on R (goals are 0, so there is no fixed downstream part):
T_v(aV) = a T_v(V) - (a - 1) k_v. So for a >= 1, T+_mu(aV) <= a T+_mu(V) - (a - 1) g, since every
variant's right side is at most that, and the maximum of those is at most the same.

* Residual. e = max over s in R of (T+_mu V - V)^+. The sums are in float64: every Q is a sum of at
  most m terms (m the largest number of outcomes of a chosen variant, plus the cost), so it is
  within rho = (m + 2) * epsilon of its exact value, relative (the same allowance as `_certify`).
  That mismatch is added to the residual like the residual itself: delta = rho * max over R of the
  largest Q (or V), and e' = e + delta.
* If e' < g, then a = g / (g - e') gives T+_mu(aV) <= a V + a e' - (a - 1) g = aV: aV is a
  supersolution of the operator of mu against every nature, so the cost of mu against any
  stationary nature, and against the worst one, is at most aV. The returned
  `error_bound` is u * (1 + rho) - 1 with u = g / (g - e'), so for every state of R the pessimistic
  cost of mu is at most V * (1 + error_bound); `solve_bounds` reads it as the upper bound.
  If e' >= g there is no certificate: `error_bound` is `math.inf` (the values are still returned).
  There is no lower side: V is not claimed to be below anything.

What is returned. `values` holds V for the states of R and `math.inf` for every explored state whose
value is infinite (certified, see above); other states are left out on purpose, mu does not reach
them and nothing is certified about them. `policy` is mu on the non-goal states of R, as the
caller's own `Action` or `VariantAction` objects.

Known limits:
* The caller's actions and their weights are kept in memory for the whole solve (the model is
  asked once), besides a copy of every variant that nature has played.
* g is taken over the actions of mu on R, not over all actions: a smaller g would be sound, only
  looser, and the cost of mu involves no other action.
* An infinite outcome of any variant of a chosen action of R (a nature that can trap mu) gives
  `error_bound = math.inf`; when the rounds ended normally this happens only if the controller has
  no better action there.
"""

import math
from array import array
from collections.abc import Iterable

from ._certify import rounding_allowance
from ._model import Action, Model, VariantAction
from ._solve import Solution, check_options, solve

IMPROVEMENT = 1e-12  # nature switches variant only on a relative gain this large
MAX_ROUNDS = 100  # rounds of nature's best response; a stop here keeps the certificate sound


class CachedModel[S]:
    """Asks the caller's model once per state, keeps the answers and notes if any is a `VariantAction`."""

    def __init__(self, model: Model[S]) -> None:
        self.model = model
        self.offers: dict[S, tuple] = {}
        self.goals: dict[S, bool] = {}
        self.has_variants = False

    def is_goal(self, state: S) -> bool:
        found = self.goals.get(state)
        if found is None:
            found = self.goals[state] = bool(self.model.is_goal(state))
        return found

    def actions(self, state: S) -> tuple:
        found = self.offers.get(state)
        if found is None:
            found = self.offers[state] = tuple(self.model.actions(state))
            if not self.has_variants:
                self.has_variants = any(isinstance(action, VariantAction) for action in found)
        return found


class _VariantsSeen(Exception):
    """Raised by `_PlainView` at the first variant action: the model needs the game solve."""


class _PlainView[S]:
    """The cached model as `solve` wants it: it stops at the first `VariantAction`."""

    def __init__(self, cached: CachedModel[S]) -> None:
        self.cached = cached

    def is_goal(self, state: S) -> bool:
        return self.cached.is_goal(state)

    def actions(self, state: S) -> tuple:
        found = self.cached.actions(state)
        if self.cached.has_variants:
            raise _VariantsSeen
        return found


def solve_variants[S](
    model: Model[S],
    starts: Iterable[S],
    *,
    tolerance: float = 1e-10,
    direct_solve_limit: int = 64,
    max_sweeps: int = 100_000,
) -> Solution[S]:
    """The pessimistic value of every state reachable from `starts` and a policy that achieves it.

    `model.actions` may return `Action`s and `VariantAction`s mixed; for a `VariantAction` nature
    picks the worst variant (see the module docstring). The options are those of `solve`, used for
    every inner solve. `Solution.values` holds the states of the certified set R and the states with
    an infinite value, `Solution.policy` maps the non-goal states of R to the caller's own action,
    and `Solution.error_bound` is the certified relative bound `J(policy) <= V * (1 + error_bound)`
    on the cost of the policy against the worst nature (`math.inf` when it cannot be certified).
    A model without a `VariantAction` is solved by `solve` and gives its result unchanged.
    """
    check_options(tolerance, direct_solve_limit, max_sweeps)
    starts = list(starts)
    options = {"tolerance": tolerance, "direct_solve_limit": direct_solve_limit, "max_sweeps": max_sweeps}
    cached = model if isinstance(model, CachedModel) else CachedModel(model)
    try:
        return solve(_PlainView(cached), starts, **options)
    except _VariantsSeen:
        pass
    game = _Game(cached, starts)
    count = len(game.goal)
    rounds = 0
    while True:
        solution = solve(game, range(count), **options)
        value = [solution.values[i] for i in range(count)]
        if rounds >= MAX_ROUNDS or not game.switch(value):
            break
        rounds += 1
        del solution  # free the policy before the next solve
    return game.certify(solution, value, starts)


class _Game[S]:
    """The states reachable through any variant, in flat arrays, and the variant nature plays now.

    States are numbered in discovery order. Actions are numbered globally, grouped by state:
    `a_first[s]:a_first[s + 1]` are those of state `s`. Each action has one or more variants,
    numbered globally too: `v_first[k]:v_first[k + 1]` for action `k`. Variant `j` has the outcomes
    `o_first[j]:o_first[j + 1]` of `o_target` (state numbers) and `o_prob` (`w / total`, correctly
    rounded, self-loop included). `chosen[k]` is the variant of action `k` that nature plays.
    The game is also a `Model` over the state numbers (the variant chosen, as an `Action` labelled
    with the action's number), which is what the inner `solve` is given.
    """

    def __init__(self, cached: CachedModel[S], starts: list[S]) -> None:
        index: dict[S, int] = {}
        states: list[S] = []

        def intern(state: S) -> int:
            found = index.get(state)
            if found is None:
                found = index[state] = len(states)
                states.append(state)
            return found

        goal: list[bool] = []
        a_first, v_first, o_first = array("q"), array("q", [0]), array("q", [0])
        cost, o_target, o_prob = array("d"), array("i"), array("d")
        originals: list = []
        for start in starts:
            intern(start)
        i = 0
        while i < len(states):  # the list grows while it is walked: a breadth-first queue
            state = states[i]
            a_first.append(len(originals))
            if cached.is_goal(state):
                goal.append(True)
                i += 1
                continue
            goal.append(False)
            for action in cached.actions(state):
                if action.extra_inputs:
                    raise NotImplementedError(
                        "multi-input actions need the branching solver, B3 (ADR-0011)"
                    )
                originals.append(action)
                cost.append(action.cost)
                for outcomes in action.variants if isinstance(action, VariantAction) else (action.outcomes,):
                    total = sum(weight for _, weight in outcomes)
                    for successor, weight in outcomes:
                        if weight:
                            o_target.append(intern(successor))
                            o_prob.append(weight / total)
                    o_first.append(len(o_target))
                v_first.append(len(o_first) - 1)
            i += 1
        a_first.append(len(originals))
        self.states, self.index, self.goal = states, index, goal
        self.a_first, self.v_first, self.o_first = a_first, v_first, o_first
        self.cost, self.o_target, self.o_prob, self.originals = cost, o_target, o_prob, originals
        self.multi = [k for k in range(len(originals)) if v_first[k + 1] - v_first[k] > 1]
        self.chosen = array("q", v_first[:-1])  # nature starts with the first variant everywhere
        self.built: dict[int, Action] = {}

    def is_goal(self, state: int) -> bool:
        return self.goal[state]

    def actions(self, state: int) -> tuple[Action, ...]:
        return tuple(self._plain(k) for k in range(self.a_first[state], self.a_first[state + 1]))

    def _plain(self, k: int) -> Action:
        """Action `k` with the variant nature plays, over state numbers, labelled `k` (built once)."""
        j = self.chosen[k]
        found = self.built.get(j)
        if found is None:
            action = self.originals[k]
            outcomes = action.variants[j - self.v_first[k]] if isinstance(action, VariantAction) else action.outcomes
            index = self.index
            found = self.built[j] = Action(k, action.cost, tuple((index[s], w) for s, w in outcomes))
        return found

    def backup(self, j: int, base: float, value: list[float]) -> float:
        """`base + sum P_j(s') V(s')` over variant `j`."""
        low, high = self.o_first[j], self.o_first[j + 1]
        total = 0.0
        for target, p in zip(self.o_target[low:high], self.o_prob[low:high]):
            total += p * value[target]
        return base + total

    def switch(self, value: list[float]) -> bool:
        """Nature's best response to `value`: True if some variant action changed its variant."""
        v_first, chosen, cost = self.v_first, self.chosen, self.cost
        changed = False
        for k in self.multi:
            first = v_first[k]
            q = [self.backup(j, cost[k], value) for j in range(first, v_first[k + 1])]
            best = max(range(len(q)), key=q.__getitem__)
            if q[best] > q[chosen[k] - first] * (1.0 + IMPROVEMENT):
                chosen[k] = first + best
                changed = True
        return changed

    def certify(self, solution: Solution[int], value: list[float], starts: list[S]) -> Solution[S]:
        """The certificate of the module docstring for the policy of `solution`."""
        goal, cost, v_first = self.goal, self.cost, self.v_first
        o_first, o_target, o_prob = self.o_first, self.o_target, self.o_prob
        policy = solution.policy
        seen = bytearray(len(goal))
        stack = []
        for start in starts:
            i = self.index[start]
            if value[i] < math.inf and not seen[i]:
                seen[i] = 1
                stack.append(i)
        smallest, terms, residual, top = math.inf, 1, 0.0, 0.0
        used: dict[int, int] = {}
        while stack:
            s = stack.pop()
            if goal[s]:
                continue
            chosen = policy.get(s)
            if chosen is None:  # cannot happen for a finite state; refuse rather than guess
                residual = math.inf
                continue
            k = used[s] = chosen.label
            smallest = min(smallest, cost[k])
            worst = 0.0
            for j in range(v_first[k], v_first[k + 1]):
                low, high = o_first[j], o_first[j + 1]
                terms = max(terms, 1 + high - low)
                q = cost[k]
                for t, p in zip(o_target[low:high], o_prob[low:high]):
                    q += p * value[t]
                    if not seen[t] and value[t] < math.inf:
                        seen[t] = 1
                        stack.append(t)
                worst = max(worst, q)
            residual = max(residual, worst - value[s])
            top = max(top, worst, value[s])
        if smallest == math.inf:  # nothing but goals (or nothing at all) to certify
            error = 0.0
        else:
            rho = rounding_allowance(terms)
            e = residual + rho * top
            error = smallest / (smallest - e) * (1.0 + rho) - 1.0 if e < smallest else math.inf
        states, originals = self.states, self.originals
        values = {states[i]: value[i] for i in range(len(goal)) if seen[i] or value[i] == math.inf}
        return Solution(values, {states[s]: originals[k] for s, k in used.items()}, max(error, 0.0))
