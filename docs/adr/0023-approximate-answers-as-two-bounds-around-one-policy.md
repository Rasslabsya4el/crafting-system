# An approximate answer is an executable policy between two certified bounds

When the exact compressed state is too large to solve in about a minute, the planner solves two smaller models of a **coarse state** instead of one big one, and reports a policy that it can run on a real item together with an interval that provably holds the exact mean cost. The answer is marked **approximate** and its error is the certified gap, never a guess. This is the "approximate merges and their error measurement" of the map; the owner's tolerance is [#81](https://github.com/Rasslabsya4el/crafting-system/issues/81) Q2: exact when a benchmark query fits in about a minute, past that an approximate answer whose measured error is at most 1% of the mean cost. It amends ADR-0009 ("v1 allows only exact merges"): an approximate merge is allowed, but only in this form.

## The two models and the gap

A **coarse state** is a partition of the exact compressed states into blocks (ADR-0009's states with some slot kinds renamed to a coarser kind). Two models are solved on the blocks, each taken **per member**: for every member of a block and every action, the member's exact kernel is pushed through the block map.

- the **optimistic model** offers, in a block, every action that is legal in at least one member and charges the cheapest member. Its value `V-` of a block is at most the exact optimum `V*` of every member (the restriction of `V*` to a block is a supersolution of this operator, and value iteration from zero rises to its least fixed point);
- the **pessimistic model** offers an action only if it is legal in every member and charges the worst member. Its best policy `pi`, read on the members, is an ordinary policy of the exact problem, and its value `V+` is at least `pi`'s exact cost `J(pi)`.

So `V-(B) <= V*(s) <= J(pi)(s) <= V+(B)` for every member `s` of `B`. The answer shows `pi` and the mean `V+`, and the **certified gap** `V+/V- - 1`. Because `V*` lies in the interval too, the gap bounds the true error of the policy shown, `J(pi)/V* - 1 <= V+/V- - 1`, and bounds the error of the mean it reports the same way. It meets the tolerance when it is at most 1%. (Checked against brute force on 300 random models, 1,800 state checks, largest violation 4e-15, by the `checker` of PR #121.)

The solver's own error enters the gap. `solve` returns values with `V(1-e) <= V* <= V(1+e)` (`Solution.error_bound`, ADR-0010), so the reported lower bound is `V-(1-e-)` and the upper `V+(1+e+)`; the gap is `V+(1+e+) / (V-(1-e-)) - 1`. A table in this ADR is **certified** only when its numbers come from `solve` with this correction; the numbers from the prototype's numpy value iteration are called measured.

### Per-member, never from one representative

A block may be built from one representative member only for an action whose kernel, pushed through the block map, is the same for all members (**block-invariant**). Otherwise the bound is false. Example: a block `{s1, s2}`, `s1` reaches the goal at cost 1, `s2` loops with probability 0.9 (true cost 10); the representative `s1` gives an "upper" bound of 1. The actions that are block-invariant when only slots without a requirement are renamed:

- an erasing reroll (Chaos Orb, Harvest reforge, essence): the outcome depends on the flags, the fractured mods and the action, which a block keeps whole;
- a bench craft and Remove Crafted Mods: deterministic, the successor block is a function of the block and the craft; only legality differs between members.

For these the models differ only in which actions are offered, so both are ordinary models and need no change in the solver. The build proves block-invariance for each action class it supports (a test compares every member of every block on the fixtures, tolerance 1e-9; the prototype did it on all 13,172 members of R05 and all 386 of the harder route below, largest difference 0). **Any other action refuses the coarse state**: Exalted Orb, Annulment, Regal, fossils (their outcome reads the pool weight of the junk families), and the recombinator, imprint and Awakener's Orb of ADR-0012/0022 (they read the mods of both items). A query that enables one of them has no family-group level and goes on to the tail cut, or to the exact run, or ends with "no approximate level available".

### If a later action needs the members to differ (variants)

A model whose successor distribution depends on the member would make the pessimistic backup a max over members (variants), i.e. a min-max game. ADR-0010's certificate survives it. It uses only `T_mu(aV) = a T_mu V + (1-a) k_mu` with `k_mu` the constant term of the policy (cost plus the fixed downstream part) and a lower bound `g` on all `k`. For the operator `T+_mu V = max_v (c + P_v V + out_v)`, each variant satisfies the identity with its own `k_v`, so for `a >= 1` `T+_mu(aV) <= a T+_mu V - (a-1) g` and for `a <= 1` `T+_mu(aV) >= a T+_mu V + (1-a) g` with `g` the smallest constant term over all actions and variants; the multipliers `g/(g-e)` and `g/(g+d)` and the supersolution argument are unchanged. It is not built in v1 (no action needs it); the build ticket that adds one must supply an oracle (brute force over policies and variants).

## Which merges are allowed

1. **Family groups: pool the families no requirement cares about.** A junk family is told apart in ADR-0009 only because an enabled bench craft would clash with it. Families whose mods give no requirement, and that no goal-relevant craft clashes with, are pooled into groups; relevant ones stay apart, and status, counts and sides are never merged. A craft whose family `phi` lies in a group of `k` families with `n` junk or crafted slots of that group on the item is legal in the optimistic model when `n <= k - 1` and in the pessimistic model only when `n = 0`. A crafted mod with no requirement is pooled in the same way. Only for the block-invariant actions above.
2. **Tail cut: expand exactly only where the policy goes.** Following a coarse policy, states with an expected number of visits below `theta` are not expanded; a cut successor takes the optimistic and the pessimistic value of its block as its two leaf values. As tight as the leaf bounds, so it needs a coarse model to start from.
3. **Weight buckets: not now.** Rounding pool weights to a geometric grid gives a bound by an interval kernel (nature picks the best or worst distribution inside `[p / r^4, p r^4]` at each backup, the variants argument above), but it is loose: 1.2% already at 5% buckets.

Not allowed: any merge that changes what an action can do or cost on the goal-relevant part of the state, or that lacks both models.

## Measurement

Prototype in `.claude/scratch/83-approx/` of the main checkout (not committed; `src/` is untouched). Prices are placeholders (essence 2 Chaos, Chaos Orb 1, each craft the Chaos value of its bench cost in a made-up currency table); only ratios count. Policies are lifted to the exact graph and their exact cost computed there ("exact cost of the lifted policy"). The bounds in the first table come from the repo's `solve` on the block models, with the correction above: **certified** (up to the float64 rounding of the stored probabilities, which `solve` already allows for).

**R05 ring, essence, Remove Crafted Mods and all 141 ring crafts** (Ring1, item level 86, fractured All Attributes, goal Life and the forced Strength). The exact graph is the real `Abstraction`'s: 13,172 states, 22,994,524 transitions, 906 s to build (674 s in kernels); the exact optimum 2.159763 is from numpy value iteration (**measured**; the repo's `solve` on this graph ended without a result or a traceback, memory, so its time is not reported).

| Level | Blocks | Build | Solve (both models) | Certified lower | Certified upper | Certified gap | Exact cost of the lifted policy |
|---|---|---|---|---|---|---|---|
| exact | 13,172 | 906 s | not run | (2.159763 measured) | | | |
| M1: irrelevant families in one group | 365 | 38 s | 0.4 s | 2.159763 | 2.159763 | 0.0000% | 2.159763 |
| M2: irrelevant, groups of 8 | 1,582 | 135 s | not run | | | | |
| M3: irrelevant, groups of 4 | 4,295 | 426 s | 30 s | 2.159763 | 2.159763 | 0.0000% | 2.159763 |
| B2: all families in one group | 364 | not built | 0.1 s | 2.159763 | 2.159763 | 0.0000% | 2.159763 |

"Build" is one representative per block through the real kernels, valid because of block-invariance (member differences 0); it ran while another job shared the machine, so it is an upper bound. The 0.0000% means below 1e-4: it includes the solver's `e` (3e-11). All gaps are zero here: the 109 crafts that give neither Life nor Strength never enter the best policy (32 crafts and 141 give the same optimum), and the one craft that matters is blocked only by a family that the block keeps apart. So R05 shows what pooling saves (36 times fewer blocks, the minute), not what it can cost.

**What it can cost: a harder route** (same ring, Chaos Orb instead of the essence, goal Life and any Strength mod, 19 crafts: Life, the six Strength-and-Dexterity / Strength-and-Intelligence hybrids that are the only Strength crafts, and single-family resistance, Dexterity and Intelligence crafts; 386 exact states, certified through `solve`):

| Level | Blocks | Certified lower | Certified upper | Certified gap | Exact cost of the lifted policy | Real error of the policy |
|---|---|---|---|---|---|---|
| exact | 386 | 5.006140 | 5.006140 | 0.0000% | 5.006140 | 0 |
| M1: irrelevant pooled | 210 | 5.006140 | 5.006140 | 0.0000% | 5.006140 | 0 |
| all families in groups of 4 | 160 | 5.006140 | 5.006140 | 0.0000% | 5.006140 | 0 |
| Dexterity and Intelligence pooled | 304 | 5.006140 | 5.259536 | **5.06%** | 5.259536 | 5.06% |
| all families in one group | 94 | 5.006140 | 5.640097 | **12.66%** | 5.640097 | 12.66% |

Of the 21 pairs of families, 20 pooled with zero gap and the pair Dexterity and Intelligence (the two families the cheap Strength hybrids clash with) gives 5.06%. The certified lower bound is 5.006140 in every row, the exact optimum, and every certified upper bound is the exact cost of its lifted policy: the interval brackets the truth and the gap is the real error, so the bound works where it is nonzero. A merge of this kind fails the 1% test and the planner would not accept it.

**Other kinds** (prototype, R05 and its 76-state version): tail cut with M1's bounds as leaves, zero gap at every `theta` (28 states kept at 1e-2, 2,577 at 1e-6, since the leaves are exact); with a leaf that knows nothing the upper bound converges (2.485 at 1,218 kept states, 2.173 at 2,243, against 2.160) and the lower bound does not (0.02), so the leaf lower bound must come from a coarse model. Weight buckets of ratio `r` on the 76-state graph: the model's value moves -0.03% (1.05), +0.04% (1.25), -0.09% (1.5), -0.02% (2), -0.48% (4), the policy's cost does not move, but the certified gap is 1.2%, 4.2%, 6.4%, 7.5%, 8.0%. The solver's time, from the M3 run: about 7 microseconds per edge of the pure-Python `solve`.

**No merge in this ADR reaches 1% on R04, R13 or R14 yet.** They are not measured (no Annulment or Exalted), and those two actions are exactly the ones that refuse the family-group level (they are not block-invariant). What could reach 1% there is open: variants with an interval on the pool total of the pooled families (the certificate argument above, plus an oracle), the tail cut on top of such a model, exact pruning by proof ([#118](https://github.com/Rasslabsya4el/crafting-system/issues/118)) and a smaller craft list chosen by the user. Until one of them is built and measured, a query that enables Exalted or Annulment is exact or says that no approximate level is available.

## How the CLI decides, and how it marks the result

Before solving, the CLI runs a **pilot count**: one cached kernel of the first random action (1 s for the essence of R05, 2,061 outcomes), then the crafted slots that fit each outcome by sets of families and free slots, with no further kernel call. On R05 it gives 76 states for 32 crafts and 13,172 for 141, equal to the exact counts, in 0.3 s and 1.1 s, and predicts 27.1 million transitions (23.0 million built, 18% over). The #59 formula (rarity times crafts times junk configurations) overestimates this route by two orders of magnitude (1.2 million states) and stays only a cheap upper bound for targets the pilot cannot count yet.

The predicted time is `transitions * (r_kernel + r_solve)`: `r_kernel` is measured in the pilot (the cost per outcome of a second, cached kernel call: 38 microseconds on a loaded machine; the build took 906 s / 23.0 million = 39 microseconds per transition including everything), `r_solve` is the seconds per edge of `solve`, measured by a short calibration solve on the pilot's own first layers (about 7 microseconds in the M3 run). Both rates are parameters of the decision function, so that a test injects them and no test depends on a machine (ADR-0014). For R05 with 141 crafts the prediction is about 1,200 s against 906 s built plus an estimated 160 s of solving.

The rule: exact if the predicted time fits about a minute, otherwise the **ladder**: M1, then smaller groups of the irrelevant families, then a tail cut with M1's bounds as leaves, stopping at the first level whose certified gap is at most 1%; a level is built only if its own pilot count fits. When no level reaches 1% inside the time, or no level exists for the enabled actions, the planner prints the best interval it has, says that the gap is above 1% (or that none was available), and offers the exact run with its predicted time or a smaller craft list; it never rounds a gap down.

The result carries the words "approximate (certified within X% of the exact mean)", the two bounds, the block count and the level; in the JSON `approximate: true`, `lower`, `upper`, `gap`, `level`.

## Risk numbers of an approximate answer

An approximate answer prints no p90 and no CVaR by default, and says so: the chain on blocks is not Markov, so `risk` cannot give its certified `Estimate`s, and the exact chain of the lifted policy is not built. With `--verify` the lifted policy is run on concrete items (ADR-0019, layer 4) and the report adds the simulated mean, p90 and CVaR with confidence intervals, in a separate type and labelled "simulated, not certified"; a simulated interval is never put in `risk.Estimate`. (A later option, not decided: the exact chain of the policy over only the states it visits, 2,609 of 13,172 on R05, through `risk` once #82 has made it fast.)

## With the recombinator interval (ADR-0012, ADR-0022)

The recombinator interval comes from a family of selection rules, one solve per rule. Recombinators are refused by the family-group level (they read both items), so no approximate answer has one today. When one is supported, the two intervals combine like this: per rule `r` the approximation gap `V+_r (1+e) / (V-_r (1-e)) - 1` must be at most 1% (the 1% test applies per rule), the reported lower bound is `max_r V-_r` and the upper bound `min over candidate policies of max_r' J+_r'(pi)` (each candidate evaluated in the pessimistic model of rule `r'`), and the route interval `[best; worst]` of ADR-0012 is shown as before, widened by those bounds at each end and labelled approximate.

## Not decided here

- Annulment and Exalted (map [#67](https://github.com/Rasslabsya4el/crafting-system/issues/67)) and R04, R13, R14: see "No merge in this ADR reaches 1%". The first build ticket must re-measure on the first of them.
- Exact pruning by proof ([#118](https://github.com/Rasslabsya4el/crafting-system/issues/118)): an action that only adds a mod nobody wants is dominated in B1 (the measurement is evidence, not a proof), but with Annulment such a mod dilutes the removal, so the proof is per action and belongs there. This ADR covers what is left when no proof exists.
- The memory of the solver: `solve` holds an `Action` per state and an `Outcome` per transition and did not finish the 23-million-transition graph. [#82](https://github.com/Rasslabsya4el/crafting-system/issues/82) and the build ticket for the bounds must keep memory per transition small.

Origin: [Approximate answers within 1% when the exact state is too large](https://github.com/Rasslabsya4el/crafting-system/issues/83); [Owner decisions](https://github.com/Rasslabsya4el/crafting-system/issues/81) Q2; [Design grill round 1: foundations](https://github.com/Rasslabsya4el/crafting-system/issues/2) Q8; [state compression research](../research/2026-10-30-2-state-compression.md).
