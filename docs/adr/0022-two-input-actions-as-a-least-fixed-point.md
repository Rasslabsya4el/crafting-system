# Two-input actions are priced by the value of the second item; the solver finds the least fixed point

An action may list `extra_inputs`: states whose **value** is paid as part of the action. The value of an input state is what it costs to obtain that item, so the action costs `cost + sum V(input)` on every attempt, a self-loop retry included (the inputs are consumed each time). The solver stays generic: it never learns what an item or a donor is.

## The second item is an acquisition process

"The value of reaching an item" is not the value of a state of the main process (that is a cost to go to the main target). It is the value of a second process over the same actions whose goal is the wanted state. The caller names it with a `Need(start, want)` and a small generic adapter builds the product states `('in', want, s)`: the base actions of `s`, outcomes mapped into the same `want`, goal test `s == want` (the base goal test for the main target). A `Need` inside an action becomes `extra_inputs=(('in', want, start),)`. Buying a donor is an ordinary action of its process (ADR-0011); the main target is one more `want`.

Rejected: both items in one state (the product of two item states grows as the square of the item space, and each further donor multiplies it again); a price table for donors fixed before the solve (it cannot hold when donors are made by processes that need each other).

## The system is a min-linear least fixed point

After the exact self-loop elimination of ADR-0010 an action of state `s` reads `Q(s,a) = c' + sum_j p_j V(j) + sum_y k_y V(y)` with `c' = cost * W/L`, `p_j = w_j/L` and `k_y = (copies of y) * W/L`. The retry pays its inputs again, so inputs carry the factor `W/L`, not 1. The coefficients are nonnegative and their row sums can exceed 1, so the operator `T = min_a Q` is not a contraction. Facts, all from nonnegative coefficients and positive costs (the prototype checks each against brute force, below):

- `T` is monotone and continuous on `[0, inf]^n`; `V* = lim T^k(0)` is its least fixed point and the optimal expected cost (the expected cost of a policy that builds two items is the sum over its tree, `sum_i M^i c`).
- `V*(s)` is finite exactly when some policy has `rho(M) < 1` on the states it reaches. This is a quantitative condition: the proper-policy analysis of `proper_states` (a path to the goal) is necessary, not sufficient (a policy that needs two copies of what it makes can reach the goal with probability 1 and still cost infinity).
- A policy has `rho(M) < 1` iff `(I - M) y = c` has a strictly positive solution. That is the test policy evaluation already makes.
- Among finite nonnegative fixed points there is one, `V*`; `inf` can still be a (useless) fixed point, so the iteration starts from zero and rises.

## The solver is the SCC solver with input edges

Input edges join the dependency graph. Components are solved in reverse topological order with downstream values fixed, as now. Because an acquisition process points down at other processes, almost every component is an ordinary B1 component whose constants contain `k_y V(y)` of a finished component; nothing new is needed there. A component with an input edge inside it, a **branching component** (donors that need each other, an output recycled as a donor), is solved by Gauss-Seidel value iteration from zero (it rises monotonically to `V*` and is a lower bound at every sweep); the initial proper policy of `_attractor` is not valid there. Once the upper certificate exists the greedy policy is subcritical and, up to `direct_solve_limit` states, policy iteration (Newton's method for this system) finishes the component.

The certificate of `_certify` carries over unchanged: it uses only `T_mu(aV) = a T_mu V + (1 - a) k` and the positive constant term, never a row sum. With `g` the smallest constant term, `e` and `d` the residuals, `V g/(g+d) <= V* <= V g/(g-e)` for `e < g`; the same multipliers cross components. `error_bound` keeps its meaning.

## Infinity is declared, and the solver may fail to decide it

A supercritical or critical component diverges, and no cheap test proves it for all policies. Three guards, in order:

1. A pre-check in the finite-state analysis: the greatest set in which every retained action sends coefficient mass of at least 1 into the set (integer test: outcome weights in the set plus `W` times the copies of inputs in the set, at least `L`). Every policy there has row sums of at least 1, so its value is infinite. An action with its own state as an input is dropped (the same rule as `L = 0`).
2. `value_ceiling` (default 1e12, in the price unit): a state whose value rises above it is declared dead, `inf`, and so is every action that uses it as outcome or input; the component is solved again without it. The certified bound is relative to that model.
3. What is neither: a component critical through weights (an input with `k = 5` on a state whose other mass leaks) grows linearly and never reaches the ceiling. `solve` raises `ConvergenceError` with `error_bound = inf`, as it does today for a missing upper certificate; it is reported as unresolved, never silently dead.

The prototype met guard 3 in 5 of 5000 random instances (0.1%), where brute force says the value is infinite; real policies of a price list should not meet it, and a dense check for small components can be added.

## The interval of ADR-0012 is a family of solves

**Reworded by grill B3** ([#94](https://github.com/Rasslabsya4el/crafting-system/issues/94)): this section first said "two rules suffice when the rules are ordered by how much they favour rare mods", and took the family `R` to be the two endpoint rules and a boundary rule. That fails: the extreme of a route's success chance is often **interior** in the exponent `alpha` of ADR-0012 (132 of 1,200 random cases), so `R` is the whole **grid** of `alpha` (five points, ADR-0033), `k` solves and `k^2` fixed-policy evaluations (5 solves and 25 evaluations for the grid; with the Awakener's group conflict as a second axis the product is 10 solves and 100 evaluations, and the conflict alone is 2 and 4, ADR-0032). The bracket below holds over the grid. The true optimum over a continuous `alpha` can lie outside it by whatever happens between grid points, so the reported interval is an inner bound until a finer grid says otherwise. The headline route is the optimum at `alpha = 1`; the route with the smallest worst case comes from the same evaluations.

The wiki gives no formula, so the admissible selection rules are a family `R` of kernels (originally the boundary rule, the extreme rules and the wiki table; now the grid of `alpha`). The solver takes no uncertainty in a kernel. For each rule in `R` the adapter builds one model and `solve` runs once. Then, in `risk`:

- every candidate policy `pi_r` is evaluated under every rule `r'` (fixed-policy linear systems, exact);
- the candidate with the smallest `max_r' J` is the route with the best worst case, with interval `[min_r' J; max_r' J]` (after grill B3 the headline route is the plan at `alpha = 1` and this one is named beside it, ADR-0012);
- the bracket of the true robust optimum `W* = min_pi max_r J` is certified: `max_r V_r <= W* <= min_candidates max_r' J`. A gap of zero proves the route optimal; otherwise the report shows the gap.

A rule is one global fact of the game, not a choice nature makes at each visit, so a solver with a minimising player and a maximising nature would answer a wider question (an outer bound).

## Risk and simulator follow the policy tree

A policy of states and inputs is a tree of independent runs: before the action's own chance, the run of each input is made from its start state. `risk.evaluate`: the mean is `(I - M) V = c` (positive solution, the same test as above); the second moment is the same system with the right-hand side `c^2 + 2 c (E rest) + sum E[A_i^2] + 2 sum_{i<j} E[A_i] E[A_j] + ...`, because the runs are independent; the expected number of each donor is a row of `(I - M)^-1`. Quantiles and CVaR keep the budget DP over cost bins: the cost of an attempt is a random increment, the convolution of the pmfs of its inputs (computed first, in the order of the components), and positive costs keep the budget coordinate acyclic. `simulator` runs an input as a nested run, then applies the two-item action to the concrete items and checks that the donor compresses to `want`. (The moment formulas are checked by hand on a one-donor case: mean 44 and second moment 3604 from the system agree with the direct sum of a geometric number of independent runs; the prototype does not run `risk` or the simulator, so this part is verified by its build tickets.)

## What the prototype showed

A throwaway copy of the solver (+208 / -17 lines, `_certify.py` and `_scc.py` untouched) with `extra_inputs`, against exact brute force over every stationary policy and HiGHS: 5000 random instances (3 to 6 states, up to 2 inputs per action, traps that need two copies of what they make), 0 wrong values, 0 broken certificates, largest relative error 7e-15, HiGHS agreeing on all 2006 all-finite instances; the Gauss-Seidel iterate stayed below `V*` and never fell in every sweep traced; positivity of `(I - M) y = c` matched `rho(M) < 1` in 19,542 of 19,542 random matrices; input-free models give bit-identical results to the present solver. Near criticality the upper certificate appears after about `0.35 / (1 - rho)` sweeps and policy iteration then finishes at once (rho 0.9999: 3,466 sweeps instead of 118,633).

Consequences for the build:

- The product of acquisition processes has `(G + 1) x S` states for `G` distinct wanted items and costs 1.0 to 1.4 times the input-free solve of the same graph (G = 20, S = 200: 4,200 states, 2.8 s in pure Python).
- When an action can ask for a wanted item from any state (an imprint, a recombinator), the copies join into one branching component of the whole product, far beyond `direct_solve_limit` (64), so it is solved by sweeps only. The build needs sparse (iterative) policy evaluation for large branching components, or the sweep count grows like `1 / (1 - rho)`.
- A tiny recombinator case (4 item states, 3 wanted items, 12 product states, 24 actions, about 1 ms) matches brute force; it has no branching component because a recombination into a state that is not `want` is a dead end in that process. Its interval is read across the three rules of the prototype: the bracket `max_r V_r <= W* <= min_candidates max_r J` was tight in all 384 price sets tried (one small family, which shows nothing about whether a gap can happen).

## What is not decided here

The compressed state of a donor, the recombinator kernel and its rule family, the imprint and Awakener's Orb actions, the choice of donors to offer (lazy generation, pruning with admissible lower bounds) are mechanics and abstraction work for the B3 grill ([#94](https://github.com/Rasslabsya4el/crafting-system/issues/94)) and [#90](https://github.com/Rasslabsya4el/crafting-system/issues/90). The mechanics are now ADR-0032 to ADR-0035; the compressed state of a donor and the lazy choice of donors are [ADR-0062](0062-donor-wants-are-the-projection-a-consumer-reads.md): a want is the projection the consumer reads, the donors are offered by a loop that proves the rest unneeded, and a branching component beyond `direct_solve_limit` is solved by the sparse policy iteration that exists.

Origin: [Solver for two-input actions (B3)](https://github.com/Rasslabsya4el/crafting-system/issues/91); [multi-item and recombinators research](../research/2026-10-30-3-multi-item-recombinators.md); [solver engineering research](../research/2026-10-30-4-solver-engineering.md).
