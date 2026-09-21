# Spec: Pareto frontier and two stopping thresholds on the bow

Dispatch ONLY after GOAL steps1-6 and required helmet CLI are merged/green.
Worktree `.worktrees/stretch-frontier`, branch `w-stretch-frontier`.
Allowed `src/craftoracle/frontier.py`, `tests/test_frontier.py`, `src/craftoracle/cli.py`,
`tests/test_plan_cli.py`, README frontier usage paragraph. Budget20minutes, no refactor.
One bounded integration correction is also authorized in `src/craftoracle/policies.py`:
the conditional utility mean currently evaluates a constant100 as99.99999999999999 for some
distributions and100 for others, which would invent Pareto improvements. In
`_conditional_expected_utility` center the weighted mean on the first selected utility:
`anchor + fsum(mass * (utility-anchor)) / selected_mass`. This preserves exact constant
utility and does not apply an arbitrary tolerance to genuine utility/risk/cost differences.
Regression in test_frontier.py must cover unequal masses with all accepted utilities100.
No other policy implementation change is authorized.
Accepted engine result contract is a dict ranked/unavailable/assumptions, with JSON-ready
policy records. Use its optional caller-owned distribution_cache for repeated thresholds.

## Requirements / design authority
BRIEF3b, D7, build_contract.md and GOAL stretch. Pure `pareto_frontier(records)` returns
nondominated policy records. Minimize expected_cost,cost_p90,irreversible_failure_risk and
maximize expected_utility; domination is <= on all cost/risk dimensions and >= utility,
with at least one strict inequality. Identical points both remain, stable input order, no
hidden tiebreaker masquerading as domination. Reject nonfinite/incomplete metrics, not missing
risk=0. Rare inputs remain reported and constrained by loadout; no invented ordering on names.

Mark frontier members on the full ranked output; never remove policies from the mandatory
>=3-policy table merely because they are dominated. For utility mode explicitly evaluate
the SAME cached stage distribution under two stopping thresholds. Add optional CLI
`--compare-thresholds 60,100` (utility-only, both >=spec.threshold) or equivalent bounded
input field approved by lead; no score-only reuse for transitions. Expand policy candidates
with threshold IDs and compute conditional terminal utility separately from stage EV.

## Checkable cases
- build_contract invented A1/2 utility0,B1/3 utility6,C1/6 utility10, price2:
  threshold6 p1/2,mean4,p90 8,terminalutility22/3; threshold10 p1/6,mean12,p90 26,
  terminalutility10. Both nondominated. Same inputdistribution, stageEV11/3.
- Add dominated policy utility6,cost5,p90 9,risk0 ->removed; exactduplicate of threshold6
  stays; lowercost/higherirreversible-risk is nondominated if otherdimensions don'tdominate.
- Real bow example exactlabels FireT1=60/FireT2=40, AST1=40/AST2=25:
  FireT1only score60;bothT2 score65;bothT1 score100. Threshold60vs100 must return different
  positive success chances, p100<=p60, mean100>=mean60 and conditionalutility100>=utility60.
  Real probabilities come from accepted exact kernel, no externalclaim. Print frontier and
boththresholds throughCLI; quality20/fixedvalues remain assumptions.

## Concrete integration contract
Expose `evaluate_frontier(spec,loadout,data,*,thresholds=None)` returning the existing result
shape. One evaluation without thresholds preserves every policy ID; add frontier flags to
the full ranked list. With thresholds, require utility mode, a nonempty list of distinct finite
numbers each>=spec.threshold. Use dataclasses.replace and the SAME distribution_cache dict
for evaluate_policies calls; never mutate the caller spec. Policy IDs gain @threshold only
in comparison mode; add stopping_threshold field so equal policy mechanisms stay identifiable.
Pool/exclusion/value labels remain unchanged; only stopping predicate/cost/conditional utility
changes. Sort combined ranked list by cost,p90,id before marking nondomination.

CLI uses this wrapper and accepts `--compare-thresholds 60,100`; show threshold and frontier
membership in table/JSON, preserve all earlier fields and the mandatory helmet command.
No new global cache or copying policy cost formulas into frontier. A test spy can count exact
raw-distribution calls to verify the second threshold reuses the first computation.
Test single-threshold IDs remain backward compatible and malformed/lower/criteria thresholds
return the normal CLI input error. Keep full suite below a minute; do not duplicate expensive
same-input evaluations merely to assert formatting.

Lead baseline from accepted engine, read2026-09-21 (model predictions, invented inputs):
AlchemyScour threshold60:p0.0053171974267639515,mean187.568999463238,p90=431.5,
conditionalutility62.636099876666925; threshold100:p0.00008640408995079098,
mean11573.026213510517,p90=26647.5,conditionalutility100 (within float rounding).
With the constant-utility correction, expected real comparison frontier IDs are
alchemy-scour@60,magic-regal-exalt@60,alchemy-scour@100. All12 reachable records stay visible.
This is an acceptance baseline from our model, not external evidence of game probabilities.

## Report
Focused tests, real bow probabilities/costs/utilities, nondominated IDs, same-distribution
evidence (no two expensive identical draws), timings. No marketlookup or newfactsheets.
