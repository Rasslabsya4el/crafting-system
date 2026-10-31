# UPDATE (2026-11-01): this file is the paused draft. The measurements were finished on GitHub (run 41251657124); the final text is ADR-0023 (PR #171). Raw logs of all rows are in `logs/` (job1..9.log are the runner outputs: 1-4 tail cut abs:1000/2000/1500/one, 5 exact cheap prices, 6 tail cut cheap, 7 tail cut goal B, 8 oracle, 9 lifted). Where this draft says the tail cut or the cheap-price exact solve "never finished" or lists the "ratio <= 2" row, the ADR and logs/ win (tail cut: floor 0.31% at spread 1000; cheap exact V*=3502.62; the ratio row has no log and is dropped).

# #130: certified level for adding actions and Annulment — partial result (paused, measurements stopped by the main chat)

Prototype and logs: `t130-prototype/` in this folder (copy of `.claude/scratch/130/` of worktree trusting-sutherland-44e2e2). Run from a worktree root with
`uv run python <dir>/levels.py abs:1000` (needs `scipy` in the scratch venv: `uv pip install scipy`; scratch only). Not product code.

## Route measured
"R14 as far as merged actions go": Thicket Bow (Bow16), ilvl 78, Hunter, from a normal item. Actions Transmutation, Alteration, Augmentation,
Regal, Annulment, Exalted, Scouring. Goal: +1 socketed gems (any), Chaos damage hybrid prefix (any tier), T1 attack speed. The metamods, the
multimod and the bench crafts of the real R14 are NOT in it (the kernel refuses them until #68 lands), and R04 needs the Fracturing Orb kernel:
not measured. Prices (Chaos, placeholders): transmute .1, alter .2, augment .2, regal 1, annul 20, exalt 15, scour 1; second set "cheap": regal .5, annul 2, exalt 2, scour .5.

## Method
- `light.py`: a fast copy of the seven kernels. Equal to the real `Abstraction` kernels in exact fractions: 1,352 kernels on all 5,762 states of the first two
  layers, and 12,200 kernels on 1,696 states of random walks up to six mods (every family told apart, as the product declares Annulment).
- Exact merge by family type with total weight per goal label ("weight-sum types"): lumpable, checked on 37,639 kernels (`validate_lump.py`).
- `coarse.py`: pools of junk kinds per side; block = (rarity, slots with pool kinds). For Exalted/Regal/Augmentation, the kernel of a member depends on the pool only
  through H = weight of the pooled families held; every outcome probability is (linear in H)/(linear in H), so the max and min of a backup over ALL members are reached
  at the lightest or the heaviest member of each pool ("variants" = the 2^p extreme members, p pools holding slots). Erasing actions, Annulment and Scouring: the pushed kernel is identical
  on every extreme member (asserted on every block built). Annulment is therefore block-invariant (it removes a uniform slot, so a pool of n slots loses one w.p. n/N, whatever the members).
- Optimistic model: min over actions and variants; pessimistic: min over actions legal in every member of the max over variants (a min-max game; nature re-picks per visit).
- Solver: nested policy iteration (nature's best response, then controller), sparse solves; certificate = sup residual eps of T V - V, then V*g/(g+eps) <= value <= V*g/(g-eps)
  with g the smallest action cost (the identity of ADR-0023 "variants"); eps is 1e-11 here, so the bracket is 1e-10 wide.
- Oracle (`oracle.py`, ticket's required one): (A) 400 random min-max models, value of both models vs brute force over every stationary policy and every nature choice: worst relative
  difference 6.5e-14 (pessimistic), 3.4e-14 (optimistic); certified bound over brute-force value at most 2.6e-13; the identity T(aV) <= aT(V)-(a-1)g (a>=1) and its a<=1 form: 0 violations in 4,000 checks.
  (C) the extremes claim on real bow pools: 300 random pools/blocks, every member enumerated, 1,776 random continuation values, worst difference 3.6e-15.

## Table (exact base: 134,821 states, 1,567,030 transitions; V* = 6837.5185, bracket 6837.51852216..6837.51852539; build 71-85 s in Python, PI solve 160 s)
Gap = certified upper / certified lower - 1 (numbers are float64 with the residual certificate, not the repo's `solve`). Policy of every row, lifted, costs exactly V* (real error 0, 29,344 exact states visited).

| Level | Blocks | Edges | Lower | Upper | Certified gap |
|---|---|---|---|---|---|
| exact, every family told apart (product today, Annulment reads all) | 725,071 | 8,904,082 | not solved | | |
| exact, ADR-0009 family types (per-mod weights) | 233,286 | 2,772,968 | not solved | | |
| exact, weight-sum types | 134,821 | 1,567,030 | 6837.5185 | 6837.5185 | 0 |
| one pool per side (21 kinds) | 137 | 1,575 | 6445.75 | 7785.34 | 20.8% |
| spread <= 3000 (4 pools) | 2,151 | 31,667 | 6780.12 | 6913.38 | 1.97% |
| spread <= 2000 (5 pools) | 2,523 | 40,067 | 6782.79 | 6905.36 | 1.81% |
| ratio <= 2 (7 pools) | 6,167 | 110,733 | 6771.24 | 6926.14 | 2.29% |
| spread <= 1500 (5 pools) | 5,103 | 80,385 | 6805.03 | 6880.39 | 1.11% |
| **spread <= 1000 (6 pools)** | **7,808** | 128,666 | 6814.34 | 6869.72 | **0.81%** |
| light kinds <= 2500 in one pool per side | 8,953 | 111,493 | 6819.00 | 6866.43 | 0.70% |
| light kinds <= 4000 | 3,186 | 38,652 | 6778.13 | 6907.38 | 1.91% |
| spread <= 500 (5 pools) | 26,801 | 391,562 | 6832.49 | 6845.38 | 0.19% |
| light <= 1500 | 24,298 | 301,675 | 6833.44 | 6846.59 | 0.19% |

("spread <= x": consecutive junk kinds by per-family weight whose weights differ by at most x from the lightest; non-monotone in the ratio rule: ratio <= 0.75 gave 5.6% with 7,808 blocks, ratio <= 0.5 1.25% with 11,616.)

Sensitivity (same levels): prices "cheap": one pool 34.5%, spread 3000/2000/1500/1000/500 = 2.33/2.16/1.36/**1.03**/0.21% (1000 misses 1% by 0.03 points; 500 passes with 26,801 blocks). Goal B (Physical damage 7000, crit multiplier 6000, T1 attack speed; exact 129,138 states, V*=625.82): one pool 22.2%, 3000/2000/1500/1000/500 = 2.29/2.11/1.32/**0.90**/0.24% (5,863 blocks at 1000).

Smaller craft list (exact, weight-sum types): without Augmentation 134,821 states, 1,566,697 edges; without Annulment 134,794 states, 869,195 edges, V* 8846.24 (+29%); Transmutation, Alteration, Regal, Exalted, Scouring only: 134,794 states, 868,887 edges, V* 10892.34 (+59%). The list does not shrink the state count (the 3+3 rare slots are reachable by Regal and Exalted alone); it changes the answer, so it is a user restriction, not an approximation.

## Reading
- Variants with extremes reach a certified 1% on this route: 0.81% at 7,808 blocks (17x fewer than exact weight-sum types, 93x fewer than the product's current exact). Needs a pool spread of about 1000 weight units (of 59,000 per side); one pool per side is 21%, so the 1% rests on grouping by weight, not on pooling everything.
- Weight buckets with interval kernels: not rebuilt. The interval polytope contains the member kernels, so for the same pooling it is never tighter than variants; ADR's 1.2% at 5% buckets stays.
- Declaring the family types of Annulment (today `Reads()` tells every family apart) cuts the exact graph 3.2x (ADR-0009 types) to 5.7x (weight-sum types); only the second fits under 2 million transitions.

## Left to measure (stopped; resume via the GitHub workflow of #165)
1. Tail cut on top of variants (`tailcut.py <cfg> <thetas...>`; expanded states = visits >= theta under the lifted policy, leaves bounded by the block values): runs for `one` and `abs:2000` never finished. The lifted policy visits only 29,344 of 134,821 states, so a cut should help a lot.
2. Exact V* for the "cheap" prices (log shows only the graph build), the no-Exalted list.
3. Not feasible now: metamod/multimod/bench steps of R14, R04 (Fracturing kernel), a second base.
4. Then: ADR-0023 amendment (below) and PR with `Closes #130`, checker pass.

## Draft of the ADR amendment (not committed)
- "Annulment is block-invariant" (proof above + assertion on every block of the measurement); additions are covered by variants; replace "additions refuse the coarse state" with: declared `Reads.adding(variants=True)` style flag, kernel = per-member extremes, pessimistic = max over variants; oracle as above.
- Ladder for such queries: pools by weight spread, halving the spread (3000, 2000, 1000, 500) until the certified gap <= 1% or the pilot count of the level does not fit.
- Caveat: one route, three goals/price sets; a metamod-bearing R14 and R04 must be re-measured by the first build ticket.
