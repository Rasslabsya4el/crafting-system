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
do not invent it as an execution anchor. The full run loop, budget accounting and distribution
aggregation remain unaudited. The source UI/configuration has not been automated at scale.

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
