# Spec: bounded fossil-combination policy and planner integration

Worktree: `.worktrees/fossil-spam-policy` (branch `w-fossil-spam-policy`).
May touch ONLY `src/craftoracle/fossil_policies.py`, `src/craftoracle/plan_inputs.py`,
`src/craftoracle/optimizer.py`, `data/loadouts/endgame.json`, `data/prices.example.json`,
`tests/test_fossil_policies.py`, `tests/test_plan_inputs.py`.
Dependencies: accepted fossil adapter AND template optimizer; start only after their merges.
Bounded60minutes. No source research or changes to other action rules.

## Why and facts
GOAL2 answered owner rows6/7 need a usable policy. Read docs/design/family-policies.md's
fossil section and docs/mechanics/fossils_resonators.md. The lead selected a bounded caller
availability domain; the worker implements its mathematics, not new game facts.

## Requirements
1. Optional loadout allowed_fossils array of distinct supported IDs, maximum4, defaultempty.
   Preserve positional Loadout compatibility by appending a default field. Policy needs
   allowed action fossil, Alchemy, all selected fossil availability and corresponding prices.
   Prices keys fossil:<id> and resonator:<socket_count>; every selected fossil costs1 in
   the invented example, resonators1/2/3/4 cost1/2/3/4. Example allowlist[1,12,13,14].
   Unsupported special IDs, duplicates, bools, malformed/overlarge arrays fail explicitly.
   Old loadouts without the field remain valid. A price never grants a permission.
2. Evaluate all nonempty subsets (up to15) using accepted full rare fossil outcome
   distributions with additive mode. Cache by resolved immutable plan/pool and rules,
   fossils, counts/caps, labels; no ActionData identity key. Share identical distributions
   across thresholds/prices. Keep candidate mean audit, selected combination and count.
   No silent omissions: unavailable combinations have explicit reasons, including work limit.
3. Alchemy first with immediate stop, else repeated full Chaotic fossil rerolls, exactly as
   the design. Exact mean/p90 and expected input counts. Conditional final distribution is
   the mixture of early Alchemy and fossil success classes; stage distributions retained.
   Include full recipe price, source/confidence, D21 additive choice, invented-price note,
   scope/four-fossil availability limit and zero item-destruction risk.
4. Integrate one best fossil-spam policy through optimize_policies, before frontier marking.
   Parameters include selected fossil IDs, socket count, additive mode, Alchemy early-stop,
   chosen fixed/offered item_level, search domain. Compatible with optional level search;
   never bypass its target-ID/price assumptions. No change to fixed baseline evaluator.
5. Test meaningful synthetic exact costs and terminal mixture, permissions/missing prices,
   recipe sum and selection of cheapest mean among supplied candidate distributions.
   One shared real helmet/bow fixture exercises the accepted adapter and integration;
   do not rerun all15 large grids per assertion. Tests stay below the global one-minute
   target; avoid unrelated full CLI subprocess repetitions. Explicit caller caches only.

## Numbers to reproduce/report
- Design:a.25,p.5,A2,c3,B0 ->mean6.5,p90 11,CDF8=.8125/CDF11=.90625.
- a1 ->mean/p90 2, fossil0; a0 ->mean8,p90 14; p0,a<1 unavailable.
- Example four available fossils yield15 subsets; recipe costs2/4/6/8 by size.
- Independent lead reference from accepted adapter0de86dd and the design formula:
  Royal Burgonet86 best of these15 combinations is Aberrant1 alone, p=.0001432502308634093,
  recipe price2, mean13961.744067592923. Pristine12+Aberrant1 costs4 and gives
  p=.00010020977755731915, mean39915.79538480682. The15 distributions took0.159minute
  in one process. These are acceptance references, never insert them as implementation.
- Report real selected helmet combination, probability, mean/p90, terminal mass1, candidate
  count, plan time and best overall route before/after; report bow60/100 frontier effects.
- Run focused tests plus affected input tests. Fixed source adapter tests need no duplicate
  re-audit. Final report starts `=== FINAL REPORT ===`, commits/files, questions/limits.
