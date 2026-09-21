# Spec: enumerate real policy choices and expose the selected parameters

Worktree: `.worktrees/template-optimizer` (branch `w-template-optimizer`).
May touch ONLY `src/craftoracle/optimizer.py`, `src/craftoracle/policies.py`,
`src/craftoracle/harvest_policies.py`, `src/craftoracle/frontier.py`,
`src/craftoracle/cli.py`, `tests/test_optimizer.py`, `tests/test_policies.py`,
`tests/test_frontier.py`, `tests/test_plan_cli.py`, `tests/test_harvest_policies.py`.
Dependencies: accepted policy_attempts.py and protected Harvest policy must be present.
Do not start before lead acceptance of those dependencies. At most90minutes; report a
concrete limit early if a conditional grid exceeds the documented runtime budget.

## Why
GOAL2 demands parameters, not a hardcoded one-Exalt recipe. The lead's complete mathematical
design is docs/design/parameter-search.md. Follow its full-prefix recovery and joint-cost
laws. The task changes planner behaviour; it is not a new game-rule research task.

## Requirements
1. Keep an explicit fixed-policy evaluator as a benchmark; add optimize_policies and route
   the default CLI/frontier through it. Avoid recursive calls between wrappers. Every returned
   policy has chosen parameters, candidate_count and a compact parameter/mean audit table.
   Select minimum mean, then p90, then stable parameters within each template (retain distinct
   essence IDs and optional bench-finish variant as the existing visible policy identities).
   Terminal distributions, expected utility, costs, steps, unavailable reasons and Pareto
   contract remain valid. Do not claim global optimality beyond the listed finite grid.
2. Protected Exalt grid: k1/2/3, preparation max_prefixes1/2, minimum desired elemental
   suffixes1/2, preparation early-stop false/true. Full suffixes exactly3 remain required.
   Use the group-aware finite kernel to stop at first Life9; never assume independent slams.
   For k3 failure charge Envy preparation again, because no prefix-lock slot remains.
   Use the general u/v/p/b renewal law for means and p90. Show recovery, probabilities,
   expected action counts and actual terminal prefix counts. Stage distributions are retained.
3. Protected Harvest grid: same preparation gates/early-stop choices, supported life route
   and accepted exact Harvest p,b. Existing baseline is one grid point. Side-group guard and
   concrete suffix representatives remain required. Parameters identify first_only model;
   all_draws sensitivity is not silently treated as an independent proven strategy.
4. Magic grid: first two-mod gate m0/1/2, post-Regal gate n0/1/2/3, max Exalts k0/1/2/3,
   early-stop false/true. Desired label means an accepted tier for required/any_of criteria
   or a positive caller value-table entry. Keep group identities through gates; stop/reject
   is decided from labels/counts. Use joint stage/cost atoms and accepted correlated cost
   helper. Optional Augment coin has the sourced independent law from the design. Report
   costs paid only on reached stages and stop as soon as the chosen rule permits.
5. Chaos setup early-stop false/true: Alchemy outcome may complete the target. With setup
   success a and Chaos success p, early mean=base+alchemy+(1-a)*chaos/p; terminal mixture
   and p90 must use the actual early atom plus conditional geometric tail. Alchemy+Scour
   has only its fixed stop rule; essence variants expose their actual forced ID and tier.
   Current exact helmet target has no bench substitute for Life9: no lower bench life
   counted as T1. Expose target_left_to_bench=null with the reason when no permitted bench
   ID is in the requested tier mapping. Keep compatible optional bench131 finish on known
   one-prefix states only; do not attach it to unknown junk or full-prefix outputs.
6. Level search is OPT-IN: CLI --item-level-range MIN:MAX and API optional interval. Default
   keeps spec.item_level exactly. Evaluate lower bound plus eligible PoB modifier-level
   breakpoints up to upper bound, deduplicate identical pool signatures. Never lower target
   tier IDs. Both endpoint validation and no-reachable-tier results are explicit. Use same
   supplied base price at all allowed levels and disclose this. Return chosen item_level,
   searched interval and actual distinct pool count. No new input-file schema needed.
7. Cache raw distributions by all draw-affecting inputs, excluding prices/thresholds.
   Conditional schedules include gate/stopping inputs in their cache keys. Share common
   live-profile prefixes or equivalent work across the grid so default helmet/bow plans
   remain under a minute in one process. Never use hidden id(ActionData) caches. Compute
   mean selection before expensive p90 where it cannot affect the selected candidate; do
   not repeat large real DPs in each unit test. At runtime a work limit must be explicit,
   with incomplete grid status rather than a falsely optimal result.
8. Show chosen parameters in text next to the policy steps and in JSON. The bow threshold
   sweep retains shared raw distributions and current utility/frontier semantics. Fixed
   benchmark tests may call the fixed evaluator; production CLI tests must exercise the
   optimized path and assert meaningful policies/parameters rather than obsolete counts.
   Keep the whole pytest suite under a minute by sharing explicit test fixtures/caches for
   repeated identical real inputs, without deleting relevant assertions.

## Numbers a test must reproduce
- Fixed Exalt one-slam helmet mean8357.193927854994; gate baseline u0,maxP2,minElem1:
  k2 mean4693.130543194264, k3 with paid full reset4787.896236081543.
  Probabilities/cycle means are in the design. Final optimized protected mean must be
  <=4693.130543194264; report selected gates, early-stop and k, not a guessed optimum.
- Harvest fixed mean2703.6093795549086, p.07950823245417578,b.07592833649031873;
  optimized mean must be no higher under the same prices. Envy baseline1927.479966
  remains a comparison; measure the actual best policy after the grid.
- Lead's independent mean-only grid reference at3712602: best protected Exalt k3,
  maxP1/minElem2/early=true, u=.002594060684443422,v=.0005495684166343905,
  mean1948.603171950813. Harvest same gate mean1986.1982162752881. Reproduce through
  your implemented grid, not by inserting these values. This does not preselect the
  overall best (pure Envy remains cheaper); terminal distributions/p90 still require tests.
- Design tiny protected fixture: e5 selects k3 mean50 versus k2=51; e50 selects k2=141
  versus k3=230. Synthetic renewal early completion case mean22 versus28 without it.
- Chaos setup a.25,p.5,alchemy2,chaos3,base0: ignored setup mean8; early-stop mean6.5.
- Illegal k3 free relock must fail a regression: charge reset; optional bench cannot be
  applied when all prefixes are occupied or an unknown conflicting group is retained.
- Fixed-seed p90 reproducible with N/interval metadata. Tiny exact means/conditional atoms
  and utility agree with hand fixtures; pure constant utility remains constant.
- Level fixture has modifier thresholds10,20 in offered10..25, so at most two distinct
  relevant pools; target requiring level20 cannot be silently downgraded at10. Default
  singleton level keeps the given input unchanged.

## Numbers to report
Focused and full test summaries if runtime permits; real selected parameters/candidate
counts, protected Exalt/Harvest before-after means and p90 intervals, overall best helmet
policy, magic before-after cost, optimized bow60/100 frontier, plan runtime and distinct
level pools. Commits/files; explicit grid limitations. Final starts `=== FINAL REPORT ===`.
