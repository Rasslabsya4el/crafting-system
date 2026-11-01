# Exact pruning of offers: twins, equal kernels, and a lower bound with a certificate

Ticket [#118](https://github.com/Rasslabsya4el/crafting-system/issues/118). The owner wants an exact answer in about a minute ([#81](https://github.com/Rasslabsya4el/crafting-system/issues/81) Q2). The profile of the planner before this ticket (real 3.29.3.3 data, cProfile, fixture prices) showed that the solver was never the cost:

- R10: 399 states, 23,540 (state, offer) kernels, 154 s profiled; 81% in `Abstraction.kernel`: 79 s rebuilding the states of an already cached label distribution (`_add_drawn`), 42 s in `outcomes` (19 s of it `tier_table`, recomputed 101 times, 22 s `pool_candidates`, 107 times). Only 10 distinct pool signatures were ever computed. The solver took 5 s.
- R05: 597 states, 38,984 kernels, 393 s profiled; 80% in `_add_drawn`, 19% in `outcomes` (`tier_table` 34 s, `pool_candidates` 35 s); the solver 14 s.
- Fossils (#62): 12,696 sets on boots, 3,938 distinct plain pools by `twin_key`; the cost of a set is its `outcomes` (0.15 s, Tangled 1 s) before any kernel.

So the work is per (state, offer) and per offer, and three things shrink it without changing an answer.

## What is done, in the order of the ticket

1. **Exact speedups with no pruning.** `tier_table` and `pool_candidates` are cached (a pure function of the data, the base and the item's mods and influences). The kernel of a cached distribution is assembled from an expanded copy kept per signature (slots already sorted, statuses built once), `Slot`/`CompressedState` cache their key and hash, `integer_weights` works on integers. Same kernels, bit for bit (tests compare with the old code).
2. **Equal kernels per state** (`Abstraction.kernel_key`, `cli/_prune.py`): offers whose kernel at a state is the same keep only the cheapest. The key is the pool signature plus what the retained item gives (flags, fractured mods, kept and new slots, status); it leaves out which mod an essence forces when that mod is the same family type and gives the goal the same. At 43 sampled R10 states 2,268 (state, offer) pairs have 798 distinct kernels.
3. **Twins** (`Action.twin_key`, optional contract method, default None): a key found without building a pool, such that equal keys give equal `outcomes` on every item of the base. A fossil set declares it (the factor of each distinct tag set of the base, the flags, the forced and the added mods).
4. **Bound** (`abstraction/_bound.py`, `cli/_bound_prune.py`). `reach_bound` is an upper bound, from the pool alone, on the chance that one use of an erasing reroll makes a set of goal leaves PASSING (the exact chance with `exact=True`). With U the necessary leaves not PASSING at the start and E "all of U PASSING", `rho = min cost / pbar` over the offers is a lower bound on the cost to reach E (Wald: any policy that reaches the goal enters E, and each step enters it with chance at most `pbar`). A solve on a few offers gives J; an offer outside the solve is proved not needed when `cost + (1 - pbar) * rho > J`, and the rest are added and the solve repeated, until none fails. Then J is the optimal value of the full model (the argument is in the module docstring). Anything the argument cannot cover (an offer that changes the flags or the fractured mods, a state without a proper policy, a solver that cannot certify) falls back to the twins only.

`Action.adds` gained `fractures` (an action that fractures a mod must say so); `Reads` and `Adds` are the only declarations the filters read, and no action class is named in `cli`.

## Limits

- The bound pruning needs the offers that move the item to another shape (a Fractured Fossil) to be dearer than the plan, or it keeps the twins only. A per-shape rho would lift this.
- A fossil set has no `twin_key` on an influenced item (its pool holds mods the key does not read): nothing merges there.
- A Tangled set costs a second to bound; sets cheaper than the best ratio are bounded, the others are left to the cost test.
- `reach_bound` is proved never low and tested against the brute force; it is not tight (1.3 to 2.8 times on boots), which is why a few extra solve rounds are needed.
- Timings are in the PR, not asserted (ADR-0014).

Related: ADR-0010 listed "FTVI-style bound pruning (unless fossil combinations make B1 too slow)"; this is a bound over offers, not over states, and it keeps the solver unchanged. ADR-0023 (approximate answers) is where what this cannot make fast goes.

## Amendment: options of a Lock are not merged by equal kernel (B8, [Grill B8](https://github.com/Rasslabsya4el/crafting-system/issues/106), 2026-11-01)

Step 2 above is exact for plain actions: of two offers with one kernel, only the cheaper can be chosen. Under a Lock it is not, because two currencies with one kernel are two independent previews and the best of two is better than one (ADR-0054). The options of a Peek are therefore taken from the full catalog, before twins, this merge and the bound pruning of step 4 (an offer the Lock-free optimum never needs can still win as one more independent preview), one per currency item; all the pruning still applies to the fallback and to every plain action.
