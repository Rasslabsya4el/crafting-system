# CoE calculator and conditional simulator: source notes

Read 2026-09-20 from S3, frozen `sources/raw/coe/package.js`, SHA-256 in SOURCES.md. This is
`reimplemented-from-CoE` evidence, not a proof that every branch matches the current game.
No downloaded JavaScript was executed. All function names and line numbers refer to this cache.

## Calculator paths actually reviewed

`poec_computeFinalProbsV2` (1021-1198) combines per-side requirement probabilities with a
prefix/suffix count distribution. In the ordinary final aggregation (1187-1195), each term is
the prefix requirement probability times the suffix requirement probability times the count
composition weight, then terms are summed. Method-specific cases and special bases intervene;
this summary is not an independent proof of that factorization for every game pool.

`poec_computePermutationsV2` (1199-1249) has two materially different modes:

- Its exact-labelled path is selected when `allmods < numModifersToExact` or the user chooses
  `poec_cAlgoMode == 'x'`. The cached threshold is 10 (line 435). It enumerates compatible
  combinations of 1, 2 or 3 mods per side, filters requirement groups, then visits draw-order
  permutations. Each step contributes required weight / remaining weight; removing a chosen
  group decreases the denominator. It distinguishes selected-tier weight from full group weight.
- Its extrapolation path (1229 onward) substitutes a rounded average unwanted-group weight for
  some unneeded draws (1234, 1239). It is an approximation. The exact-labelled branch also
  clamps totals above 1 at 1228; another clamp appears at 1242. Clamping is an observed safeguard,
  not proof of numerical correctness. Do not reproduce it to hide errors in our distribution.

Thus CoE calculator results must record mode, pool and conditions before use as known answers.
They are not uniformly exact. Potential overlapping-group accounting and the final side
factorization still need independent synthetic checks (Q14).

`poec_computeBestFossils` (1494) builds candidate combinations; `poec_computeFCTrueCalc`
(1522-1538) reweights pool and required tiers for each combination, calls the probability
routine, and ranks by probability or estimated spend. Its estimated attempts use ceil(1/p)
(1535), and prices come from site data. Our inputs use caller prices; exact mean attempts are
1/p without that display rounding when independent geometric assumptions hold.

`poec_computeConfidence` (938-941) displays chance of a hit within N tries using 1-(1-p)^N,
with p reconstructed from the displayed attempts field. This is a geometric CDF, not a
statistical confidence interval. Reusing a rounded attempts field can change the displayed CDF.

## Conditional simulator configuration

`poec_nsimBuildConfig` (3220-3236) reconstructs steps with method choices/options, conditions,
thresholds, unveiling filters, and separate success/failure routes. `poec_nsimGenerateConfigData`
(3237) serializes these settings. `poec_nsimRelayConfigData` (3266-3296) expands metamethod
recipes, remaps step references and combines method constraints. Observed route values include
next, step, end, loop and restart. `poec_nsimGetStepConditions` (3546 onward) renders conditions
for open slots, mod counts, tags and tiers, including AND/OR and threshold-of-group conditions.

This supports policies with explicit stopping and restart decisions rather than an unconditional
action list. The method name `poec_nsimExecute` requested in the first inventory is absent;
do not invent it as an execution anchor. The source UI/configuration has not been automated
at scale. Budget accounting, batch scheduling and final distribution aggregation remain
unaudited; the per-action execution and routing below have now been read.

`poec_simExecuteAction` (3365-3399) snapshots the preceding state, checks constraints, dispatches
the action, evaluates the resulting item, increments per-step/action counters and routes:

| result / route | observed transition at 3398 |
|---|---|
| success / next | advance one step |
| success / end | move beyond final step |
| success or failure / step | go to explicit one-based route minus one |
| failure / loop | keep current step AND changed item |
| failure / restart | step zero AND restore initial `nsim_sdata` snapshot |

At 3399, a completed policy records action/step counts and calls `poec_simActionSucceed`.
Restart does not reset those current-craft counters in the observed branch. A policy costing
model must charge consumed actions and replacement/preparation inputs; restoring a simulator
snapshot is not evidence that the game restores a destroyed or modified item for free.

Conditions at 3384-3397 inspect affix tiers or stored value sums, fracture flags, free slots,
mod counts, tags and pseudos. The labels AND/OR are insufficient to infer all semantics: both
group branches compare passing-condition counts with an explicit threshold or their group
size, then group-level pass logic applies. Future specs must state boolean semantics directly.
Unveiling at 3361-3371 picks the first preferred offered ID; when none matches, a method option
controls whether a fallback offer is taken. Player choice and random offer generation are
distinct stages. The blanket corrupted-item rejection at 3365 is a simulator limitation,
not proof against the documented bench/tainted exceptions (S37, corruption.md).

## Consequences for BRIEF 3b

The reviewed CoE calculator centers on one requested target and returns aggregate success.
Our stage calculators instead retain an outcome distribution, then apply a target predicate or
utility threshold. See D7 and `docs/design/build_contract.md`. Exact enumeration must keep
all legal outcome mass, including undesirable outcomes; it cannot only enumerate successful
combinations and claim that is the whole distribution. No calculator has been implemented yet.

Synthetic independent entries A/B/C with weights 1/1/2 and no group conflicts:
two sequential draws without replacement give unordered outcomes AB=1/6, AC=5/12, BC=5/12
(sum 1). For example AC=(1/4)*(2/3)+(2/4)*(1/2)=5/12. Therefore P(A present)=7/12.
These hand-derived values extend the existing affix-generation example; they are invented
test inputs, not a real mod pool. They test a distribution, not merely one target probability.

## Batch execution and cost/result aggregation (read 2026-09-20)
Source: S3 package.js, poec_simLoopAction 3308-3312, poec_simActionSucceed 3405-3410,
poec_simOutputResultsTbl 3435-3485, poec_sortByActions 3486. Confidence:
`reimplemented-from-CoE`; this is program behavior, not a game mechanic.

- Fixed mode stops after either a requested action count or a requested completed-item count.
  Real-time/debug modes use different scheduling. No monetary-budget stop appears in the
  reviewed loop; fixed action count must not be described as a currency budget.
- Success storage is optional and capped by nsim_maxitems. Affix/count distributions are
  accumulated only for completed items. Success resets the item to the starting snapshot,
  resets the step index and increments completed count; a restart is not a free in-game item.
- Per-step frequency is passed/count; the displayed reciprocal uses ceil(1/p). Separate
  success-only mod frequencies divide by completed count. Those conditional frequencies
  cannot substitute for an unconditional stage outcome distribution (BRIEF 3b).
- Currency quantities multiply executed step counts by recipe quantities. Fossils additionally
  count one resonator of the chosen socket size (3437-3438); removed bench crafts add a
  separate scour quantity (3464-3465). Restore-imprint/unveil are excluded as currency tokens,
  but their necessary prior inputs must still be represented in a player's policy.
- Cost-per-success uses ceil(total quantity/completed count) **for each resource separately**
  before multiplying by its price (3466,3477). This is a display estimate with rounding bias,
  not the unrounded sample mean. Example (invented): 5 units over 2 completed items gives
  display 3 units rather than mean 2.5; at price 4, display 12 versus mean cost 10.
- 'Cheapest' and 'Costliest' select first/last after sorting by **action count**, then price
  the selected path (3478,3486). These need not be price extrema. Synthetic counterexample:
  one action costing 10 versus two actions costing 1 each; fewer actions costs 10, more costs 2.
- No p90 cost computation is in this reviewed output routine. Min/max selected paths or a
  rounded per-success quantity must not be relabelled as p90 or a confidence interval.

Q28 records both cost-display limitations. Our later policy implementation must retain complete
resource/cost totals and distributions, charge replacement starting inputs, and distinguish
success-conditioned terminal utility from unconditional outcomes. None of CoE's code is executed
or copied; these findings constrain our own specifications.
