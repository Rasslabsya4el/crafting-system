# Big graphs are solved on flat arrays; cuts are exact first, then tolerance with a stated guarantee, and fixed rails only stop and say so

**Draft** for [ticket #312](https://github.com/Rasslabsya4el/crafting-system/issues/312) (research note `docs/research/2026-11-01-exact-merging-and-cuts.md`, which holds the numbers). Not accepted: the owner decides whether the build tickets below are cut.

R04 (177,242 states, 535.9 M transitions), R14 (816,153 states) and R08 with the Alchemy did not solve exactly. The ticket suspected that their states differ in detail no decision sees, so that an exact merge would shrink them to a solvable size. Measured: they do not shrink that way (R04 2.0x, R14 1.4x with the coarsest exact partition; the routes that merge by 50 to 140x already solve). What stopped them is that the solver holds the graph as Python objects, that the walk is serial Python, and that nothing cuts by cost before the walk. R04's exact mean cost is 69,716.06 chaos and R14's 5,786.62, both found by solving the class graph on numpy arrays in under 3 minutes.

## Decision

1. **Exact merging is not built into the walk.** The coarsest exact partition (same goal status, same action costs, same outcome chances over the classes) stays a research and verification tool (`research/312/exact_classes.py`), and the quotient is an optional pre-step of the flat solve. A canonical key cheaper than the partition does not exist (no single projection is exact on all routes) and would gain 2.0x and 1.4x at most.
2. **A graph that does not fit the object solver is solved on flat arrays.** Self-loops eliminated into exit costs; policy iteration from a proper start policy (the shortest-path tree of the lucky path lowers the distance to the goal with positive chance, so it is proper); each policy evaluated by an iterative linear solve; the Bellman residual reported, and certified the way `solver/_certify.py` certifies a component. The object solver stays for the small routes and for everything with inputs, variants or Locks.
3. **Cuts are classified by what they guarantee, in this order, and the report says which ones ran:**
   - *Exact*: an action is never expanded when its cost with lower bounds on its outcomes exceeds the best action's cost with upper bounds (ADR-0031 raised from offers to states). The incumbent is a given route or a cheap first solve; the lower bound is any value never above the exact one: the luckiest path, or the solution of an optimistic coarse model (states told apart by cheap keys). Nothing is lost. None of the bounds measured is strong on R04 and R14 (see below), so this cut is built only after a bound is found that is.
   - *Tolerance, only with a stated guarantee*: an outcome is lumped only when `p * (UB - LB)` is below the margin the bounds leave the choice. The report states `V_opt <= V* <= V_pess` and the relative gap, and that every choice with a positive margin is unchanged. No fixed chance and no count are used as a threshold.
   - *Safety net*: a time or memory limit stops the run and says so. A ceiling on uses of one step, or on the chance of an outcome, is never applied silently; it is a named limit the owner sets, and the report lists the limits that were binding.
4. **No default is given to a fixed number.** R11 (1,086 chaos) has no route under a 1,000-use ceiling; lumping outcomes below 1e-3 moves R13 from 6,300 to between 24 and 16,800 chaos and R08 with the Alchemy by +4.3%; 1e-4 and 1e-5 changed nothing on any measured route, but nothing says why.

## What the measurements say about each part

- **Flat solve**: R04's class graph (89,778 classes, 414,544 actions, 171 M edges) in 155 s and under 2 GB; R14's (589,930 classes, 6.9 M edges) in 19 s. The object solver died at 15.7 GB on R04.
- **Walk**: R04 380 s, 1.3 GB; R14 1,721 s, 8 GB (2.1 ms per state with 12 offers). Python-bound, serial.
- **Cuts**: the lucky-path bound with 32 sweeps is 0.6% of R04's cost and cuts nothing; a perfect bound would leave 13% of R04's classes and 11% of R14's. The coarse optimistic models (status, rarity, mods per side, fractured ids) give 97% of the cost on R13 but 1.4 to 3.5% on R04 and 0.5 to 4.1% on R14, and cut no action there.
- **Near ties**: on R13 the other actions are within 3% of the best; an exact cut cannot remove them, a tolerance cut can only with a settled margin.

## Consequences

- The proof sketch of the exact cut: `LB(s') <= V*(s') <= UB(s')` for every state; the optimistic coarse model has an optimal value at most the exact value because a concrete policy is a policy of the coarse model that picks the action of the member it is in; an action whose lower Q exceeds the best upper Q is not part of any optimal policy, so the optimal value of the cut graph is the optimal value of the whole.
- The flat solve is a second solver. Both must agree on the routes both can hold (R05, R08, R13: equal to 1e-12 in the measurement); a test keeps it so.
- A walk guided by the bounds needs the bounds before the walk, so the coarse model must be built without the full graph (the variants level of ADR-0023 is the nearest existing piece). That is the open build ticket whose gain the note could only bound from above.

## Proposed tickets

1. **Flat solve for big graphs** (`solver/`): the policy-iteration solve of `research/312/prune_analysis.py` as a solver entry for graphs above a size; the residual certified; equal to the object solver on R05, R08, R13 (tests); R04 and R14 end to end through the planner. Done when R04 and R14 give their exact value through `make_plan`.
2. **A parallel, cheaper walk** (`abstraction/`, `cli/`): R04's 380 s and R14's 1,721 s split across the runners (kernels per state are independent); profile first. Done when R14's walk is under 10 minutes on 8 runners.
3. **A lower bound that is strong on R04 and R14** (research): the keys tried (status, rarity, mods per side, fractured ids) fail because they hide the junk the Annulment, the Exalted Orb and the essences gamble on. Try a coarse model that keeps the junk's family types but drops the status detail, or bounds from the pool (ADR-0031's `rho` at state level); it must be buildable without the full graph (the variants level of ADR-0023). Done when a bound is at least 50% of the exact cost on R04 and R14, and a bound-guided expansion is measured against the full walk.
4. **Report the cuts** (`cli/`): the report lists which cut kinds ran, the tolerance and what it guarantees, and the limits that were binding; no cut by a fixed count or chance. Done when a binding time or memory limit makes the plan say "not exact, stopped at ..." and a test covers it.

## Not proposed

An in-walk canonical key; a rail with a default; lumping by a fixed chance; the exact merge as a build step of the planner.
